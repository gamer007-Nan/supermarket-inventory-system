from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required

from models import db, Product, Transaction, Detection, Alert

detection_bp = Blueprint("detection", __name__, url_prefix="/api/detection")

# Lazy-loaded so the app can boot even before a model file is present.
_yolo_model = None


def get_yolo_model():
    """Loads YOLOv8 once, pinned to CPU inference (no GPU in Codespaces)."""
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO  # imported lazily to keep app startup light

        _yolo_model = YOLO(current_app.config["YOLO_MODEL_PATH"])
    return _yolo_model


def run_inference(frame, camera_id):
    """
    Runs YOLOv8 on a single frame and returns raw shelf-exit detections.
    `frame` is a numpy BGR image (e.g. from cv2.VideoCapture.read()).
    Returns a list of dicts: [{vision_class, confidence}, ...]
    """
    model = get_yolo_model()
    conf_threshold = current_app.config["YOLO_CONF_THRESHOLD"]

    results = model.predict(source=frame, device="cpu", conf=conf_threshold, verbose=False)

    detections = []
    for result in results:
        for box in result.boxes:
            class_id = int(box.cls[0])
            class_name = result.names[class_id]
            confidence = float(box.conf[0])
            detections.append({"vision_class": class_name, "confidence": confidence})
    return detections


# ---------------------------------------------------------------------
# Correlation engine (the critical business rule)
#
#   1. A shelf-exit detection ALONE must never trigger an alert.
#   2. Look for a transaction of the SAME product (matched by SKU via
#      vision_class -> Product.vision_class) within ±90 seconds.
#   3. Match found  -> legitimate, no alert.
#   4. No match     -> suspicious, real-time alert generated.
# ---------------------------------------------------------------------
def correlate_detection(detection: Detection) -> Alert | None:
    window = timedelta(seconds=current_app.config["CORRELATION_WINDOW_SECONDS"])
    start = detection.detected_at - window
    end = detection.detected_at + window

    query = Transaction.query.filter(
        Transaction.scanned_at >= start,
        Transaction.scanned_at <= end,
    )
    # Match by product identity (SKU), not just the raw vision class label.
    if detection.product_id is not None:
        query = query.filter(Transaction.product_id == detection.product_id)
    else:
        # No product could be resolved from vision_class at all -> can't match.
        query = query.filter(db.false())

    match = query.order_by(
        db.func.abs(db.func.timestampdiff(db.text("SECOND"), Transaction.scanned_at, detection.detected_at))
    ).first()

    if match:
        detection.correlation_status = "matched"
        detection.matched_transaction_id = match.id
        db.session.commit()
        return None

    detection.correlation_status = "unmatched"
    db.session.commit()

    alert = Alert(
        detection_id=detection.id,
        product_id=detection.product_id,
        severity="high" if detection.confidence >= 0.8 else "medium",
        status="open",
        message=(
            f"Unmatched shelf exit for '{detection.vision_class}' on camera "
            f"{detection.camera_id}: no POS scan within "
            f"{current_app.config['CORRELATION_WINDOW_SECONDS']}s."
        ),
    )
    db.session.add(alert)
    db.session.commit()
    return alert


@detection_bp.route("/events", methods=["POST"])
@login_required
def submit_detection():
    """
    Ingests a shelf-exit event (from the YOLOv8 pipeline) and immediately
    runs it through the correlation engine.
    Expected JSON: { vision_class, camera_id, confidence, detected_at? }
    """
    data = request.get_json(force=True)
    vision_class = data.get("vision_class")
    camera_id = data.get("camera_id")
    confidence = data.get("confidence")

    if not all([vision_class, camera_id]) or confidence is None:
        return jsonify({"error": "vision_class, camera_id and confidence are required"}), 400

    detected_at = data.get("detected_at")
    detected_at = datetime.fromisoformat(detected_at) if detected_at else datetime.utcnow()

    product = Product.query.filter_by(vision_class=vision_class).first()

    detection = Detection(
        product_id=product.id if product else None,
        vision_class=vision_class,
        camera_id=camera_id,
        confidence=confidence,
        detected_at=detected_at,
    )
    db.session.add(detection)
    db.session.commit()

    alert = correlate_detection(detection)

    return (
        jsonify(
            {
                "detection_id": detection.id,
                "correlation_status": detection.correlation_status,
                "alert_created": alert is not None,
                "alert_id": alert.id if alert else None,
            }
        ),
        201,
    )
