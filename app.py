from flask import Flask, render_template
from flask_login import LoginManager

from config import Config
from models import db, User
from modules.auth import auth_bp
from modules.inventory import inventory_bp
from modules.detection import detection_bp
from modules.alerts import alerts_bp

login_manager = LoginManager()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    app.register_blueprint(auth_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(detection_bp)
    app.register_blueprint(alerts_bp)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
