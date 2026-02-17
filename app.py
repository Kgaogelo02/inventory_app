from flask import Flask, render_template, request, redirect, send_file, jsonify, session, flash, url_for
import sqlite3
import csv
from datetime import datetime, timedelta, timezone
from functools import wraps
import secrets
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

DB_NAME = "database.db"

# South African Time Zone (SAST = UTC+2)
SAST = timezone(timedelta(hours=2))

def get_current_time():
    """Get current time in South African Standard Time (SAST)"""
    return datetime.now(SAST)

# Template filter for formatting timestamps
@app.template_filter('format_datetime')
def format_datetime(value):
    """Format datetime string for display"""
    if value:
        try:
            dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%Y-%m-%d %H:%M')
        except:
            return value
    return ''

@app.template_filter('format_date')
def format_date(value):
    """Format date string for display"""
    if value:
        try:
            dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%Y-%m-%d')
        except:
            return value
    return ''

# -----------------------------------------------------------------------------------------
# DATABASE INITIALIZATION
# -----------------------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Products table
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cost REAL NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL,
            min_stock INTEGER DEFAULT 5,
            category TEXT,
            barcode TEXT UNIQUE,
            supplier_id INTEGER,
            created_at TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
    """)

    # Sales table
    c.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            quantity INTEGER,
            total_amount REAL,
            sale_time TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TEXT
        )
    """)

    # Suppliers table
    c.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            created_at TEXT
        )
    """)

    # Purchase Orders table
    c.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            cost_per_unit REAL,
            total_cost REAL,
            status TEXT DEFAULT 'pending',
            order_date TEXT,
            expected_delivery TEXT,
            received_date TEXT,
            notes TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Stock Alerts table
    c.execute("""
        CREATE TABLE IF NOT EXISTS stock_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            alert_threshold INTEGER DEFAULT 5,
            is_active INTEGER DEFAULT 1,
            last_alert_sent TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Create default Mabutsi user if not exists
    c.execute("SELECT * FROM users WHERE username = 'Mabutsi'")
    if not c.fetchone():
        hashed_pw = generate_password_hash('Mabutsi@12')
        current_time = get_current_time().strftime('%Y-%m-%d %H:%M:%S')
        c.execute("INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
                  ('Mabutsi', hashed_pw, 'Mabutsi', current_time))

    conn.commit()
    conn.close()

# Initialize database when app starts
init_db()

# -----------------------------------------------------------------------------------------
# LOGIN REQUIRED DECORATOR
# -----------------------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------------------------------------------------------------------
# AUTHENTICATION ROUTES
# -----------------------------------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            flash(f'Welcome back, {username}!', 'success')
            return redirect('/')
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)

        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            current_time = get_current_time().strftime('%Y-%m-%d %H:%M:%S')
            c.execute("INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
                      (username, hashed_pw, current_time))
            conn.commit()
            conn.close()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'error')

    return render_template('register.html')

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        # Verify current password
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE id = ?", (session['user_id'],))
        user = c.fetchone()

        if not user or not check_password_hash(user[0], current_password):
            flash('Current password is incorrect!', 'error')
            conn.close()
            return redirect(url_for('change_password'))

        # Check new passwords match
        if new_password != confirm_password:
            flash('New passwords do not match!', 'error')
            conn.close()
            return redirect(url_for('change_password'))

        # Check password strength
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long!', 'error')
            conn.close()
            return redirect(url_for('change_password'))

        # Update password
        hashed_pw = generate_password_hash(new_password)
        c.execute("UPDATE users SET password = ? WHERE id = ?", 
                  (hashed_pw, session['user_id']))
        conn.commit()
        conn.close()

        flash('Password changed successfully! Please log in again.', 'success')
        return redirect(url_for('logout'))

    return render_template('change_password.html')

# -----------------------------------------------------------------------------------------
# DASHBOARD
# -----------------------------------------------------------------------------------------
@app.route('/')
@login_required
def index():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Total products
    c.execute("SELECT COUNT(*) FROM products")
    total_products = c.fetchone()[0]

    # Total sales quantity
    c.execute("SELECT SUM(quantity) FROM sales")
    total_sales = c.fetchone()[0] or 0

    # Daily sales (today in SAST)
    today_date = get_current_time().date()
    c.execute("""
        SELECT 
            SUM(s.quantity),
            SUM(s.total_amount)
        FROM sales s
        WHERE DATE(s.sale_time) = ?
    """, (today_date,))
    daily = c.fetchone()
    daily_items = daily[0] or 0
    daily_value = daily[1] or 0

    # Total profit
    c.execute("""
        SELECT SUM((p.price - p.cost) * s.quantity)
        FROM sales s
        JOIN products p ON s.product_id = p.id
    """)
    total_profit = c.fetchone()[0] or 0

    # Total revenue
    c.execute("SELECT SUM(total_amount) FROM sales")
    total_revenue = c.fetchone()[0] or 0

    # Low stock count
    c.execute("SELECT COUNT(*) FROM products WHERE stock <= min_stock")
    low_stock_count = c.fetchone()[0]

    # Product list with search
    search_query = request.args.get('search', '')
    if search_query:
        c.execute("SELECT * FROM products WHERE name LIKE ? OR category LIKE ?", 
                  (f'%{search_query}%', f'%{search_query}%'))
    else:
        c.execute("SELECT * FROM products ORDER BY name")
    products = c.fetchall()

    # Product sales history
    c.execute("""
        SELECT p.name, SUM(s.quantity), SUM(s.total_amount)
        FROM sales s
        JOIN products p ON s.product_id = p.id
        GROUP BY p.id
        ORDER BY SUM(s.quantity) DESC
        LIMIT 10
    """)
    product_history = c.fetchall()

    # Categories
    c.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
    categories = [row[0] for row in c.fetchall()]

    conn.close() 

    return render_template(
        "index.html",
        products=products,
        total_products=total_products,
        total_sales=total_sales,
        daily_items=daily_items,
        daily_value=daily_value,
        total_profit=total_profit,
        total_revenue=total_revenue,
        low_stock_count=low_stock_count,
        product_history=product_history,
        categories=categories,
        search_query=search_query
    )
   
# -----------------------------------------------------------------------------------------
# ADD PRODUCT
# -----------------------------------------------------------------------------------------
@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        cost = float(request.form['cost'])
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        min_stock = int(request.form.get('min_stock', 5))
        category = request.form.get('category', '')
        barcode = request.form.get('barcode', '')
        supplier_id = request.form.get('supplier_id', None)
        if supplier_id:
            supplier_id = int(supplier_id)

        if price < cost:
            flash('Selling price cannot be less than cost price!', 'error')
            return redirect(url_for('add_product'))

        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            current_time = get_current_time().strftime('%Y-%m-%d %H:%M:%S')
            c.execute(
                "INSERT INTO products (name, cost, price, stock, min_stock, category, barcode, supplier_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, cost, price, stock, min_stock, category, barcode if barcode else None, supplier_id, current_time)
            )
            conn.commit()
            conn.close()
            flash(f'Product "{name}" added successfully!', 'success')
            return redirect('/')
        except sqlite3.IntegrityError:
            flash('Barcode already exists!', 'error')

    # Get suppliers for dropdown
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, name FROM suppliers ORDER BY name")
    suppliers = c.fetchall()
    conn.close()

    return render_template('add_product.html', suppliers=suppliers)

# -----------------------------
# EDIT PRODUCT
# -----------------------------
@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        cost = float(request.form['cost'])
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        min_stock = int(request.form.get('min_stock', 5))
        category = request.form.get('category', '')
        supplier_id = request.form.get('supplier_id', None)
        if supplier_id:
            supplier_id = int(supplier_id)

        if price < cost:
            flash('Selling price cannot be less than cost price!', 'error')
            return redirect(url_for('edit_product', product_id=product_id))

        c.execute("""
            UPDATE products 
            SET name = ?, cost = ?, price = ?, stock = ?, min_stock = ?, category = ?, supplier_id = ?
            WHERE id = ?
        """, (name, cost, price, stock, min_stock, category, supplier_id, product_id))
        conn.commit()
        conn.close()
        flash('Product updated successfully!', 'success')
        return redirect('/')

    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    
    c.execute("SELECT id, name FROM suppliers ORDER BY name")
    suppliers = c.fetchall()
    
    conn.close()

    if not product:
        flash('Product not found!', 'error')
        return redirect('/')

    return render_template('edit_product.html', product=product, suppliers=suppliers)

# -----------------------------------------------------------------------------------
# DELETE PRODUCT
# -----------------------------------------------------------------------------------
@app.route('/delete_product/<int:product_id>')
@login_required
def delete_product(product_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    
    if product:
        c.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        flash(f'Product "{product[0]}" deleted successfully!', 'success')
    else:
        flash('Product not found!', 'error')
    
    conn.close()
    return redirect('/')

# -------------------------------------------------------------------------------------
# ADD SALE
# -------------------------------------------------------------------------------------
@app.route('/add_sale', methods=['GET', 'POST'])
@login_required
def add_sale():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE stock > 0")
    products = c.fetchall()

    if request.method == 'POST':
        product_id = int(request.form['product_id'])
        quantity = int(request.form['quantity'])

        # Check stock availability
        c.execute("SELECT stock, price FROM products WHERE id = ?", (product_id,))
        product_data = c.fetchone()
        
        if not product_data:
            flash('Product not found!', 'error')
            conn.close()
            return redirect(url_for('add_sale'))

        available_stock, price = product_data

        if quantity > available_stock:
            flash(f'Insufficient stock! Only {available_stock} units available.', 'error')
            conn.close()
            return redirect(url_for('add_sale'))

        total_amount = quantity * price

        # Get current SAST time
        current_time = get_current_time().strftime('%Y-%m-%d %H:%M:%S')

        c.execute(
            "INSERT INTO sales (product_id, quantity, total_amount, sale_time) VALUES (?, ?, ?, ?)",
            (product_id, quantity, total_amount, current_time)
        )

        c.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (quantity, product_id)
        )

        conn.commit()
        conn.close()
        flash(f'Sale recorded successfully! Total: R {total_amount:.2f}', 'success')
        return redirect('/')

    conn.close()
    return render_template('sales.html', products=products)

# ----------------------------------------------------------------------------------------
# SALES HISTORY
# ----------------------------------------------------------------------------------------
@app.route('/sales_history')
@login_required
def sales_history():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("""
        SELECT s.id, p.name, s.quantity, s.total_amount, s.sale_time
        FROM sales s
        JOIN products p ON s.product_id = p.id
        ORDER BY s.sale_time DESC
        LIMIT 100
    """)
    sales = c.fetchall()
    conn.close()

    return render_template('sales_history.html', sales=sales)

# -------------------------------------------------------------------------------
# ANALYTICS API (for charts)
# -------------------------------------------------------------------------------
@app.route('/api/sales_chart')
@login_required
def sales_chart():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get date 7 days ago in SAST
    seven_days_ago = (get_current_time() - timedelta(days=7)).date()
    
    # Last 7 days sales
    c.execute("""
        SELECT DATE(sale_time) as date, SUM(total_amount) as revenue
        FROM sales
        WHERE DATE(sale_time) >= ?
        GROUP BY DATE(sale_time)
        ORDER BY date
    """, (seven_days_ago,))
    data = c.fetchall()
    conn.close()

    dates = [row[0] for row in data]
    revenues = [float(row[1]) if row[1] else 0 for row in data]

    return jsonify({'dates': dates, 'revenues': revenues})

@app.route('/api/top_products')
@login_required
def top_products():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("""
        SELECT p.name, SUM(s.quantity) as total_sold
        FROM sales s
        JOIN products p ON s.product_id = p.id
        GROUP BY p.id
        ORDER BY total_sold DESC
        LIMIT 5
    """)
    data = c.fetchall()
    conn.close()

    products = [row[0] for row in data]
    quantities = [row[1] for row in data]

    return jsonify({'products': products, 'quantities': quantities})

# --------------------------------------------------------------------------------
# EXPORT SALES
# --------------------------------------------------------------------------------
@app.route('/export_sales')
@login_required
def export_sales():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT s.sale_time, p.name, s.quantity, p.price,
               s.total_amount as total
        FROM sales s
        JOIN products p ON s.product_id = p.id
        ORDER BY s.sale_time DESC
    """)
    rows = c.fetchall()
    conn.close()

    file_name = "sales_report.csv"
    with open(file_name, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Sale Time', 'Product Name', 'Quantity', 'Price', 'Total'])
        writer.writerows(rows)
    
    return send_file(file_name, as_attachment=True)

# --------------------------------------------------------------------------------------------------------
# EXPORT INVENTORY CSV
# --------------------------------------------------------------------------------------------------------
@app.route('/export')
@login_required
def export():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM products")
    rows = c.fetchall()
    conn.close()

    file_name = "inventory_export.csv"
    with open(file_name, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['ID', 'Name', 'Cost', 'Price', 'Stock', 'Category', 'Barcode', 'Created At'])
        writer.writerows(rows)

    return send_file(file_name, as_attachment=True)

# ----------------------------------------------------------------------------------------------
# ANALYTICS DASHBOARD
# ----------------------------------------------------------------------------------------------
@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html')

# ----------------------------------------------------------------------------------------------
# SUPPLIERS MANAGEMENT
# ----------------------------------------------------------------------------------------------
@app.route('/suppliers')
@login_required
def suppliers():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM suppliers ORDER BY name")
    suppliers = c.fetchall()
    conn.close()
    return render_template('suppliers.html', suppliers=suppliers)

@app.route('/add_supplier', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if request.method == 'POST':
        name = request.form['name']
        contact_person = request.form.get('contact_person', '')
        email = request.form.get('email', '')
        phone = request.form.get('phone', '')
        address = request.form.get('address', '')

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        current_time = get_current_time().strftime('%Y-%m-%d %H:%M:%S')
        c.execute(
            "INSERT INTO suppliers (name, contact_person, email, phone, address, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, contact_person, email, phone, address, current_time)
        )
        conn.commit()
        conn.close()
        flash(f'Supplier "{name}" added successfully!', 'success')
        return redirect(url_for('suppliers'))

    return render_template('add_supplier.html')

@app.route('/edit_supplier/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        contact_person = request.form.get('contact_person', '')
        email = request.form.get('email', '')
        phone = request.form.get('phone', '')
        address = request.form.get('address', '')

        c.execute("""
            UPDATE suppliers 
            SET name = ?, contact_person = ?, email = ?, phone = ?, address = ?
            WHERE id = ?
        """, (name, contact_person, email, phone, address, supplier_id))
        conn.commit()
        conn.close()
        flash('Supplier updated successfully!', 'success')
        return redirect(url_for('suppliers'))

    c.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
    supplier = c.fetchone()
    conn.close()

    if not supplier:
        flash('Supplier not found!', 'error')
        return redirect(url_for('suppliers'))

    return render_template('edit_supplier.html', supplier=supplier)

@app.route('/delete_supplier/<int:supplier_id>')
@login_required
def delete_supplier(supplier_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT name FROM suppliers WHERE id = ?", (supplier_id,))
    supplier = c.fetchone()
    
    if supplier:
        c.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        conn.commit()
        flash(f'Supplier "{supplier[0]}" deleted successfully!', 'success')
    else:
        flash('Supplier not found!', 'error')
    
    conn.close()
    return redirect(url_for('suppliers'))

# --------------------------------------------------------------------------------
# PURCHASE ORDERS
# --------------------------------------------------------------------------------
@app.route('/purchase_orders')
@login_required
def purchase_orders():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT po.*, s.name as supplier_name, p.name as product_name
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        JOIN products p ON po.product_id = p.id
        ORDER BY po.order_date DESC
    """)
    orders = c.fetchall()
    conn.close()
    return render_template('purchase_orders.html', orders=orders)

@app.route('/create_purchase_order', methods=['GET', 'POST'])
@login_required
def create_purchase_order():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == 'POST':
        supplier_id = int(request.form['supplier_id'])
        product_id = int(request.form['product_id'])
        quantity = int(request.form['quantity'])
        cost_per_unit = float(request.form['cost_per_unit'])
        expected_delivery = request.form.get('expected_delivery', '')
        notes = request.form.get('notes', '')

        total_cost = quantity * cost_per_unit
        current_time = get_current_time().strftime('%Y-%m-%d %H:%M:%S')

        c.execute("""
            INSERT INTO purchase_orders 
            (supplier_id, product_id, quantity, cost_per_unit, total_cost, 
             order_date, expected_delivery, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (supplier_id, product_id, quantity, cost_per_unit, total_cost,
              current_time, expected_delivery, notes))
        
        conn.commit()
        conn.close()
        flash(f'Purchase order created successfully! Total: R{total_cost:.2f}', 'success')
        return redirect(url_for('purchase_orders'))

    # Get suppliers and products for dropdowns
    c.execute("SELECT id, name FROM suppliers ORDER BY name")
    suppliers = c.fetchall()
    c.execute("SELECT id, name, stock, min_stock FROM products ORDER BY name")
    products = c.fetchall()
    conn.close()

    return render_template('create_purchase_order.html', suppliers=suppliers, products=products)

@app.route('/receive_purchase_order/<int:order_id>')
@login_required
def receive_purchase_order(order_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get order details
    c.execute("""
        SELECT product_id, quantity, status 
        FROM purchase_orders 
        WHERE id = ?
    """, (order_id,))
    order = c.fetchone()
    
    if not order:
        flash('Purchase order not found!', 'error')
        conn.close()
        return redirect(url_for('purchase_orders'))
    
    if order[2] == 'received':
        flash('This order has already been received!', 'warning')
        conn.close()
        return redirect(url_for('purchase_orders'))
    
    product_id, quantity, status = order
    
    # Update product stock
    c.execute("""
        UPDATE products 
        SET stock = stock + ? 
        WHERE id = ?
    """, (quantity, product_id))
    
    # Update order status
    current_time = get_current_time().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("""
        UPDATE purchase_orders 
        SET status = 'received', received_date = ?
        WHERE id = ?
    """, (current_time, order_id))
    
    conn.commit()
    conn.close()
    
    flash(f'Purchase order received! Stock updated (+{quantity} units)', 'success')
    return redirect(url_for('purchase_orders'))

@app.route('/cancel_purchase_order/<int:order_id>')
@login_required
def cancel_purchase_order(order_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("UPDATE purchase_orders SET status = 'cancelled' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    
    flash('Purchase order cancelled', 'info')
    return redirect(url_for('purchase_orders'))

# --------------------------------------------------------------------------------------------
# STOCK ALERTS
# --------------------------------------------------------------------------------------------
@app.route('/stock_alerts')
@login_required
def stock_alerts():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get products with low stock
    c.execute("""
        SELECT p.id, p.name, p.stock, p.min_stock, p.category, s.name as supplier_name
        FROM products p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.stock <= p.min_stock
        ORDER BY p.stock ASC
    """)
    low_stock_products = c.fetchall()
    
    # Get all stock alert settings
    c.execute("""
        SELECT sa.*, p.name, p.stock, p.min_stock
        FROM stock_alerts sa
        JOIN products p ON sa.product_id = p.id
        ORDER BY p.name
    """)
    alert_settings = c.fetchall()
    
    conn.close()
    return render_template('stock_alerts.html', 
                         low_stock_products=low_stock_products,
                         alert_settings=alert_settings)

@app.route('/set_stock_alert/<int:product_id>', methods=['POST'])
@login_required
def set_stock_alert(product_id):
    threshold = int(request.form.get('threshold', 5))
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Check if alert exists
    c.execute("SELECT id FROM stock_alerts WHERE product_id = ?", (product_id,))
    existing = c.fetchone()
    
    if existing:
        c.execute("""
            UPDATE stock_alerts 
            SET alert_threshold = ?, is_active = 1
            WHERE product_id = ?
        """, (threshold, product_id))
    else:
        c.execute("""
            INSERT INTO stock_alerts (product_id, alert_threshold, is_active)
            VALUES (?, ?, 1)
        """, (product_id, threshold))
    
    conn.commit()
    conn.close()
    
    flash('Stock alert updated!', 'success')
    return redirect(url_for('stock_alerts'))

# --------------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)

