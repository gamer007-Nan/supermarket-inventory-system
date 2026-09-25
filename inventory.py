from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from models import db, Product, Stock, Transaction
from modules.auth import roles_required

inventory_bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")


@inventory_bp.route("/products", methods=["GET"])
@login_required
def list_products():
    products = Product.query.all()
    return jsonify(
        [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "vision_class": p.vision_class,
                "quantity": p.stock.quantity if p.stock else 0,
            }
            for p in products
        ]
    )


@inventory_bp.route("/products", methods=["POST"])
@roles_required("admin")
def create_product():
    data = request.get_json(force=True)
    required = ["sku", "name", "vision_class"]
    if not all(data.get(f) for f in required):
        return jsonify({"error": f"required fields: {required}"}), 400
    if Product.query.filter_by(sku=data["sku"]).first():
        return jsonify({"error": "sku already exists"}), 409

    product = Product(
        sku=data["sku"],
        name=data["name"],
        vision_class=data["vision_class"],
        price=data.get("price", 0),
    )
    db.session.add(product)
    db.session.flush()  # get product.id before commit

    stock = Stock(product_id=product.id, quantity=data.get("initial_quantity", 0))
    db.session.add(stock)
    db.session.commit()
    return jsonify({"id": product.id, "sku": product.sku}), 201


@inventory_bp.route("/transactions", methods=["POST"])
@login_required
def record_transaction():
    """
    Records a POS scan and atomically decrements stock.
    This is the event stream the correlation engine matches
    shelf-exit detections against.
    """
    data = request.get_json(force=True)
    sku = data.get("sku")
    quantity = int(data.get("quantity", 1))
    register_id = data.get("register_id")

    if not sku or quantity <= 0:
        return jsonify({"error": "sku and a positive quantity are required"}), 400

    product = Product.query.filter_by(sku=sku).first()
    if not product:
        return jsonify({"error": "unknown sku"}), 404

    stock = Stock.query.filter_by(product_id=product.id).with_for_update().first()
    if not stock or stock.quantity < quantity:
        return jsonify({"error": "insufficient stock"}), 409

    now = datetime.utcnow()
    txn = Transaction(
        product_id=product.id,
        user_id=current_user.id,
        quantity=quantity,
        scanned_at=now,
        register_id=register_id,
    )
    stock.quantity -= quantity
    stock.updated_at = now

    db.session.add(txn)
    db.session.commit()

    return (
        jsonify(
            {
                "transaction_id": txn.id,
                "product_id": product.id,
                "quantity": quantity,
                "remaining_stock": stock.quantity,
                "scanned_at": now.isoformat(),
            }
        ),
        201,
    )


@inventory_bp.route("/stock/<sku>", methods=["GET"])
@login_required
def get_stock(sku):
    product = Product.query.filter_by(sku=sku).first()
    if not product or not product.stock:
        return jsonify({"error": "not found"}), 404
    return jsonify({"sku": sku, "quantity": product.stock.quantity})
