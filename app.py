import os
import sqlite3
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import datetime

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'images')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'jfif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_NAME = os.path.join(app.root_path, "store.db")

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                image TEXT NOT NULL,
                description TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_price REAL NOT NULL,
                order_details TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------- HTML PAGE ROUTES -----------------

# Customer Page
@app.route("/")
def home():
    return render_template("index.html")

# Admin Dashboard Page
@app.route("/admin")
def admin():
    return render_template("admin.html")

# ----------------- API ENDPOINTS -----------------

@app.route("/api/products", methods=["GET"])
def get_products():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products ORDER BY id DESC")
        products = [dict(row) for row in cursor.fetchall()]
    return jsonify(products)

@app.route("/api/products/edit/<int:product_id>", methods=["POST"])
def edit_product(product_id):
    name = request.form.get("name")
    category = request.form.get("category")
    price = request.form.get("price")
    description = request.form.get("description")

    file = request.files.get("image")
    image_url = None

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        image_url = f"/static/images/{filename}"

    with get_db() as conn:
        cursor = conn.cursor()
        if image_url:
            cursor.execute('''
                UPDATE products
                SET name = ?, category = ?, price = ?, description = ?, image = ?
                WHERE id = ?
            ''', (name, category, float(price), description, image_url, product_id))
        else:
            cursor.execute('''
                UPDATE products
                SET name = ?, category = ?, price = ?, description = ?
                WHERE id = ?
            ''', (name, category, float(price), description, product_id))
        conn.commit()

    return jsonify({"status": "success", "message": "Dress updated successfully!"})

@app.route("/api/checkout", methods=["POST"])
def checkout():
    order_data = request.json
    total = order_data.get("total", 0)
    items = order_data.get("items", [])
    shipping_info = order_data.get("shipping", {})

    items_summary = ", ".join([f"{item['name']} (x{item['quantity']})" for item in items])
    
    # Calculate realistic delivery dates
    today = datetime.date.today()
    shipping_speed = shipping_info.get("speed", "express")
    
    if shipping_speed == "express":
        est_min = today + datetime.timedelta(days=3)
        est_max = today + datetime.timedelta(days=5)
        shipping_cost = 15.0 if total < 150 else 0.0
    else:  # standard global delivery
        est_min = today + datetime.timedelta(days=7)
        est_max = today + datetime.timedelta(days=12)
        shipping_cost = 0.0

    delivery_window = f"{est_min.strftime('%b %d')} – {est_max.strftime('%b %d, %Y')}"
    
    final_tax = round(total * 0.05, 2)
    final_total = round(total + final_tax + shipping_cost, 2)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (total_price, order_details)
            VALUES (?, ?)
        ''', (final_total, items_summary))
        order_id = cursor.lastrowid
        conn.commit()

    return jsonify({
        "status": "success",
        "message": "Order placed successfully!",
        "receipt": {
            "order_id": f"RA-{order_id + 1000}",
            "date": datetime.datetime.now().strftime("%B %d, %Y - %I:%M %p"),
            "items": items,
            "subtotal": total,
            "shipping_cost": shipping_cost,
            "tax": final_tax,
            "total": final_total,
            "shipping": shipping_info,
            "delivery_window": delivery_window
        }
    })

@app.route("/api/orders", methods=["GET"])
def get_orders():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY id DESC")
        orders = [dict(row) for row in cursor.fetchall()]
    return jsonify(orders)

if __name__ == "__main__":
    app.run(debug=True)