import os
import json
import math
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from urllib.parse import quote, urlsplit

from flask import Flask, render_template, request, redirect, url_for, flash, session, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "haven_delivery.db"))

app = Flask(__name__)
IS_PRODUCTION = os.environ.get("RENDER", "").lower() == "true" or os.environ.get("FLASK_ENV", "").lower() == "production"
_secret_key = os.environ.get("SECRET_KEY")
if IS_PRODUCTION and not _secret_key:
    raise RuntimeError("Set a strong SECRET_KEY environment variable before running in production.")
app.config["SECRET_KEY"] = _secret_key or "local-development-only-" + secrets.token_hex(24)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION

def load_business_config():
    config_path = os.path.join(BASE_DIR, "business_config.json")
    with open(config_path, "r", encoding="utf-8") as config_file:
        return json.load(config_file)

BUSINESS_CONFIG = load_business_config()
BUSINESS_NAME = BUSINESS_CONFIG["business_name"]
WHATSAPP_NUMBER = BUSINESS_CONFIG["whatsapp_number"]
DELIVERY_STATUSES = ["Pending", "Confirmed", "Picked Up", "In Transit", "Delivered", "Cancelled"]
SERVICE_TYPES = ["Restaurant food", "Pharmacy delivery", "Parcel/document", "Other"]

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db_dir = os.path.dirname(os.path.abspath(DATABASE))
    os.makedirs(db_dir, exist_ok=True)
    db = sqlite3.connect(DATABASE)
    db.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'customer',
        created_at TEXT NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tracking_code TEXT UNIQUE NOT NULL,
        customer_id INTEGER,
        customer_name TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        customer_email TEXT,
        service_type TEXT NOT NULL,
        pickup_address TEXT NOT NULL,
        dropoff_address TEXT NOT NULL,
        package_details TEXT NOT NULL,
        preferred_time TEXT,
        delivery_fee REAL NOT NULL DEFAULT 0,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'Pending',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(customer_id) REFERENCES users(id) ON DELETE SET NULL
    )""")
    db.commit()
    # Optional first-run admin account. Change credentials immediately after setup.
    admin_email = os.environ.get("HAVEN_ADMIN_EMAIL", "").strip().lower()
    admin_password = os.environ.get("HAVEN_ADMIN_PASSWORD", "")
    if IS_PRODUCTION and (not admin_email or len(admin_password) < 12):
        db.close()
        raise RuntimeError("Set HAVEN_ADMIN_EMAIL and HAVEN_ADMIN_PASSWORD (at least 12 characters) before running in production.")
    if not admin_email:
        admin_email = "admin@havendelivery.local"
    if not admin_password:
        admin_password = "ChangeMe123!"
    existing = db.execute("SELECT id FROM users WHERE email = ?", (admin_email,)).fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (name,email,phone,password_hash,role,created_at) VALUES (?,?,?,?,?,?)",
            ("Haven Administrator", admin_email, "0000000000", generate_password_hash(admin_password), "admin", datetime.now().isoformat(timespec="seconds"))
        )
        db.commit()
    db.close()

init_db()

def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]

app.jinja_env.globals["csrf_token"] = csrf_token
app.jinja_env.globals["business_name"] = BUSINESS_NAME
app.jinja_env.globals["whatsapp_number"] = WHATSAPP_NUMBER
app.jinja_env.globals["delivery_statuses"] = DELIVERY_STATUSES

@app.before_request
def protect_post_requests():
    if request.method == "POST":
        sent = request.form.get("_csrf_token", "")
        expected = session.get("_csrf_token", "")
        if not sent or not expected or not secrets.compare_digest(sent, expected):
            abort(400, description="Your form session expired. Go back, refresh the page, and try again.")

@app.context_processor
def inject_globals():
    return {
        "current_user": get_current_user(),
        "year": datetime.now().year,
        "business_config": BUSINESS_CONFIG
    }

def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute("SELECT id,name,email,phone,role FROM users WHERE id = ?", (user_id,)).fetchone()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if not user or user["role"] != "admin":
            flash("Administrator access is required.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def calculate_fee(pickup, dropoff, service):
    # The business owner has not supplied final rates. Store zero until an admin confirms
    # the fee, and describe it as "to be confirmed" throughout the customer-facing pages.
    return 0.0

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        if not name or not email or not phone or len(password) < 8:
            flash("Complete every field. Your password must be at least 8 characters.", "error")
            return render_template("register.html")
        try:
            db = get_db()
            cur = db.execute(
                "INSERT INTO users (name,email,phone,password_hash,role,created_at) VALUES (?,?,?,?,?,?)",
                (name, email, phone, generate_password_hash(password), "customer", datetime.now().isoformat(timespec="seconds"))
            )
            db.commit()
            session.clear()
            session["user_id"] = cur.lastrowid
            csrf_token()
            flash("Your account has been created.", "success")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("That email address is already registered. Please log in.", "error")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            csrf_token()
            flash("Welcome back.", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            next_url = request.args.get("next", "")
            parsed_next = urlsplit(next_url)
            if next_url and not parsed_next.scheme and not parsed_next.netloc and next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("login.html")

@app.post("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    orders = get_db().execute("SELECT * FROM orders WHERE customer_id = ? ORDER BY id DESC", (user["id"],)).fetchall()
    return render_template("dashboard.html", orders=orders)

@app.route("/book", methods=["GET", "POST"])
def book_delivery():
    user = get_current_user()
    if request.method == "POST":
        name = request.form.get("customer_name", "").strip()
        phone = request.form.get("customer_phone", "").strip()
        email = request.form.get("customer_email", "").strip()
        service = request.form.get("service_type", "").strip()
        pickup = request.form.get("pickup_address", "").strip()
        dropoff = request.form.get("dropoff_address", "").strip()
        details = request.form.get("package_details", "").strip()
        preferred_time = request.form.get("preferred_time", "").strip()
        notes = request.form.get("notes", "").strip()
        if not all([name, phone, service, pickup, dropoff, details]) or service not in SERVICE_TYPES:
            flash("Please complete all required fields.", "error")
            return render_template("book.html", services=SERVICE_TYPES, form=request.form)
        fee = calculate_fee(pickup, dropoff, service)
        tracking = "HDE-" + secrets.token_hex(12).upper()
        now = datetime.now().isoformat(timespec="seconds")
        db = get_db()
        cur = db.execute("""INSERT INTO orders
            (tracking_code,customer_id,customer_name,customer_phone,customer_email,service_type,pickup_address,dropoff_address,package_details,preferred_time,delivery_fee,notes,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (tracking, user["id"] if user else None, name, phone, email, service, pickup, dropoff, details, preferred_time, fee, notes, "Pending", now, now))
        db.commit()
        order_id = cur.lastrowid
        message = f"Hello Haven Delivery Express. I submitted a delivery request. Tracking: {tracking}. Customer: {name}. Pickup: {pickup}. Destination: {dropoff}. Service: {service}. Please confirm the delivery fee before dispatch."
        wa_link = f"https://wa.me/{WHATSAPP_NUMBER}?text={quote(message)}"
        flash(f"Booking submitted! Your tracking code is {tracking}. Save it to check the delivery status.", "success")
        return render_template("booking_success.html", tracking=tracking, order_id=order_id, fee=fee, wa_link=wa_link)
    initial = {}
    if user:
        initial = {"customer_name": user["name"], "customer_phone": user["phone"], "customer_email": user["email"]}
    return render_template("book.html", services=SERVICE_TYPES, form=initial)

@app.route("/track", methods=["GET", "POST"])
def track_order():
    order = None
    code = request.values.get("code", "").strip().upper()
    if code:
        order = get_db().execute("SELECT tracking_code,service_type,delivery_fee,status,created_at,updated_at FROM orders WHERE tracking_code = ?", (code,)).fetchone()
        if not order:
            flash("We couldn't find that tracking code. Check it and try again.", "error")
    return render_template("track.html", order=order, code=code)

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    orders = db.execute("SELECT * FROM orders ORDER BY CASE status WHEN 'Pending' THEN 0 WHEN 'Confirmed' THEN 1 WHEN 'Picked Up' THEN 2 WHEN 'In Transit' THEN 3 ELSE 4 END, id DESC").fetchall()
    stats = {
        "total": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "pending": db.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending'").fetchone()[0],
        "active": db.execute("SELECT COUNT(*) FROM orders WHERE status IN ('Confirmed','Picked Up','In Transit')").fetchone()[0],
        "delivered": db.execute("SELECT COUNT(*) FROM orders WHERE status = 'Delivered'").fetchone()[0],
    }
    return render_template("admin.html", orders=orders, stats=stats)

@app.post("/admin/order/<int:order_id>/update")
@admin_required
def update_order(order_id):
    status = request.form.get("status", "")
    fee_raw = request.form.get("delivery_fee", "").strip()
    if status not in DELIVERY_STATUSES:
        flash("Invalid delivery status.", "error")
        return redirect(url_for("admin_dashboard"))
    try:
        fee = float(fee_raw)
        if not math.isfinite(fee) or fee < 0:
            raise ValueError
    except (TypeError, ValueError):
        flash("Enter a valid non-negative delivery fee.", "error")
        return redirect(url_for("admin_dashboard"))
    db = get_db()
    db.execute("UPDATE orders SET status = ?, delivery_fee = ?, updated_at = ? WHERE id = ?",
               (status, fee, datetime.now().isoformat(timespec="seconds"), order_id))
    db.commit()
    flash(f"Order #{order_id} updated.", "success")
    return redirect(url_for("admin_dashboard"))

@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=getattr(error, "description", "Bad request.")), 400

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", host="127.0.0.1", port=int(os.environ.get("PORT", 5000)))
