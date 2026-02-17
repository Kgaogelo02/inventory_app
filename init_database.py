#!/usr/bin/env python3
"""
Database Initialization Script
Run this ONCE to create all database tables
"""

import sqlite3
from datetime import datetime, timedelta, timezone

DB_NAME = "database.db"
SAST = timezone(timedelta(hours=2))

def get_current_time():
    return datetime.now(SAST)

def init_database():
    print("=" * 50)
    print("  Database Initialization")
    print("=" * 50)
    print()
    
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        print("📦 Creating products table...")
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
        print("   ✅ Products table created")
        
        print("💰 Creating sales table...")
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
        print("   ✅ Sales table created")
        
        print("👤 Creating users table...")
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TEXT
            )
        """)
        print("   ✅ Users table created")
        
        print("🚚 Creating suppliers table...")
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
        print("   ✅ Suppliers table created")
        
        print("📋 Creating purchase_orders table...")
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
        print("   ✅ Purchase orders table created")
        
        print("🔔 Creating stock_alerts table...")
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
        print("   ✅ Stock alerts table created")
        
        # Create default admin user
        print("👨‍💼 Creating default admin user...")
        c.execute("SELECT * FROM users WHERE username = 'admin'")
        if not c.fetchone():
            from werkzeug.security import generate_password_hash
            hashed_pw = generate_password_hash('admin123')
            current_time = get_current_time().strftime('%Y-%m-%d %H:%M:%S')
            c.execute("INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
                      ('admin', hashed_pw, 'admin', current_time))
            print("   ✅ Admin user created (username: admin, password: admin123)")
        else:
            print("   ℹ️  Admin user already exists")
        
        conn.commit()
        conn.close()
        
        print()
        print("=" * 50)
        print("✅ SUCCESS! Database initialized")
        print("=" * 50)
        print()
        print("All tables created:")
        print("  - products")
        print("  - sales")
        print("  - users")
        print("  - suppliers")
        print("  - purchase_orders")
        print("  - stock_alerts")
        print()
        print("Default login:")
        print("  Username: Mabutsi")
        print("  Password: Mabutsi@02")
        print()
        print("You can now run: python app.py")
        print()
        
        return True
        
    except Exception as e:
        print()
        print("❌ ERROR:", e)
        print()
        return False

if __name__ == '__main__':
    print()
    init_database()