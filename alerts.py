from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from models import db, Alert

alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@alerts_bp.route("", methods=["GET"])
@login_required
def list_alerts():
    status = request.args.get("status")
    query = Alert.query
    if status:
        query = query.filter_by(status=status)
    alerts = query.order_by(Alert.created_at.desc()).all()

    return jsonify(
        [
            {
                "id": a.id,
                "detection_id": a.detection_id,
                "product": a.product.name if a.product else None,
                "severity": a.severity,
                "status": a.status,
                "message": a.message,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ]
    )


@alerts_bp.route("/<int:alert_id>/resolve", methods=["POST"])
@login_required
def resolve_alert(alert_id):
    data = request.get_json(force=True) or {}
    outcome = data.get("status", "resolved")
    if outcome not in ("resolved", "false_positive", "acknowledged"):
        return jsonify({"error": "status must be resolved, false_positive or acknowledged"}), 400

    alert = Alert.query.get_or_404(alert_id)
    alert.status = outcome
    alert.resolved_by = current_user.id
    alert.resolved_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"id": alert.id, "status": alert.status})


@alerts_bp.route("/summary", methods=["GET"])
@login_required
def summary():
    open_count = Alert.query.filter_by(status="open").count()
    resolved_count = Alert.query.filter_by(status="resolved").count()
    false_positive_count = Alert.query.filter_by(status="false_positive").count()
    return jsonify(
        {
            "open": open_count,
            "resolved": resolved_count,
            "false_positive": false_positive_count,
        }
    )
