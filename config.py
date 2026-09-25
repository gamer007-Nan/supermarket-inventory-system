import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
    MYSQL_DB = os.environ.get("MYSQL_DB", "inventory_theft_system")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Correlation engine (critical business rule) ---
    # A shelf-exit detection is only legitimate if a transaction for the
    # SAME product (SKU / class) exists within this many seconds of it.
    CORRELATION_WINDOW_SECONDS = int(os.environ.get("CORRELATION_WINDOW_SECONDS", 90))

    # YOLOv8 (CPU inference, no GPU in Codespaces)
    YOLO_MODEL_PATH = os.environ.get("YOLO_MODEL_PATH", "models/yolov8n.pt")
    YOLO_DEVICE = "cpu"
    YOLO_CONF_THRESHOLD = float(os.environ.get("YOLO_CONF_THRESHOLD", 0.5))
