# SCI22CSC138 — AI-Powered Inventory Management & Anti-Theft System

Phase 1 scaffold: environment, Flask app factory, and MySQL schema.

## Setup (GitHub Codespaces, no GPU)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit MySQL credentials

# create the database + tables
mysql -u root -p < schema.sql

python app.py           # http://localhost:5000
```

## Structure

```
app.py               # Flask app factory, blueprint registration
config.py             # env-driven config, correlation window (90s), YOLO settings
models.py             # SQLAlchemy models (User, Product, Stock, Transaction, Detection, Alert)
schema.sql             # raw MySQL DDL (equivalent to models.py, for direct import)
modules/
  auth.py              # login/register, role-based access control (staff/admin)
  inventory.py          # product CRUD, transaction recording + stock decrement
  detection.py          # YOLOv8 CPU inference + the ±90s correlation engine
  alerts.py             # alert listing, resolution, summary stats
templates/dashboard.html  # Phase 4 placeholder
static/style.css
```

## Correlation engine (core business rule)

A shelf-exit detection never triggers an alert by itself. `modules/detection.py:correlate_detection`
looks for a transaction on the **same product** within `CORRELATION_WINDOW_SECONDS` (default 90s,
set in `.env`) of the detection timestamp:

- Match found → `detection.correlation_status = "matched"`, no alert.
- No match → `detection.correlation_status = "unmatched"`, an `Alert` row is created.

Product identity is resolved via `Product.vision_class`, which maps a YOLOv8 class label to a SKU —
this is what ties the CV detection to the correct transaction row, not just the raw class name.

## Next phases

- Phase 2 (done here): auth + inventory modules.
- Phase 3 (done here): YOLOv8 inference stub + correlation engine — wire a real camera/video loop
  into `modules/detection.run_inference` and call `/api/detection/events` per detected exit.
- Phase 4: build out `templates/dashboard.html` to poll `/api/inventory/products` and `/api/alerts`.
- Phase 5/6: audit + synthetic test data (recommend a `seed.py` and a `tests/` folder using pytest
  to hit the 100% inventory accuracy target and measure precision/recall against simulated theft).
