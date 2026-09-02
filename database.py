# database.py - Production Schema, Transactions, Audit Trail & Khata
import sqlite3
import datetime

DB_NAME = "dairy.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # User Auth & Session
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_session (
            id INTEGER PRIMARY KEY,
            email TEXT,
            user_id TEXT,
            token TEXT,
            dairy_name TEXT,
            phone TEXT,
            is_logged_in INTEGER DEFAULT 0
        )
    ''')

    # Farmers Master
    cur.execute('''
        CREATE TABLE IF NOT EXISTS farmers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            milk_type TEXT DEFAULT 'Cow',
            rate_type TEXT DEFAULT 'fat_snf',
            fixed_rate REAL DEFAULT 0.0,
            is_synced INTEGER DEFAULT 0
        )
    ''')

    # Milk Purchases
    cur.execute('''
        CREATE TABLE IF NOT EXISTS milk_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            shift TEXT NOT NULL,
            farmer_code TEXT NOT NULL,
            milk_type TEXT NOT NULL,
            litres REAL NOT NULL,
            fat REAL DEFAULT 0.0,
            snf REAL DEFAULT 0.0,
            rate REAL NOT NULL,
            total_amount REAL NOT NULL,
            is_synced INTEGER DEFAULT 0
        )
    ''')

    # Customers Master
    cur.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT,
            rate_per_litre REAL DEFAULT 50.0,
            is_synced INTEGER DEFAULT 0
        )
    ''')

    # Retail Sales
    cur.execute('''
        CREATE TABLE IF NOT EXISTS retail_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            shift TEXT NOT NULL,
            customer_code TEXT NOT NULL,
            milk_type TEXT DEFAULT 'Cow',
            litres REAL NOT NULL,
            rate REAL NOT NULL,
            total_amount REAL NOT NULL,
            is_synced INTEGER DEFAULT 0
        )
    ''')

    # Farmer Payments (Settlements)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS farmer_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            farmer_code TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_mode TEXT DEFAULT 'Cash',
            note TEXT,
            is_synced INTEGER DEFAULT 0
        )
    ''')

    # Customer Payments
    cur.execute('''
        CREATE TABLE IF NOT EXISTS customer_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            customer_code TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_mode TEXT DEFAULT 'Cash',
            note TEXT,
            is_synced INTEGER DEFAULT 0
        )
    ''')

    # Audit Trail Log (Phase 3 Compliance)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            table_name TEXT NOT NULL,
            record_id INTEGER,
            details TEXT
        )
    ''')

    # App Settings
    cur.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    defaults = [
        ('dairy_name', 'Nilgiri Dairy Collection'),
        ('dairy_phone', ''),
        ('printer_mac', ''),
        ('analyzer_mac', ''),
        ('auto_sms', '0'),
        ('auto_whatsapp', '0')
    ]
    for k, v in defaults:
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

# Session Helpers
def save_session(email, user_id, token, dairy_name, phone):
    conn = get_db()
    try:
        with conn:
            conn.execute("DELETE FROM user_session")
            conn.execute(
                "INSERT INTO user_session (email, user_id, token, dairy_name, phone, is_logged_in) VALUES (?, ?, ?, ?, ?, 1)",
                (email, user_id, token, dairy_name, phone)
            )
    finally:
        conn.close()

def clear_session():
    conn = get_db()
    with conn:
        conn.execute("UPDATE user_session SET is_logged_in = 0")
    conn.close()

def is_user_logged_in():
    conn = get_db()
    row = conn.execute("SELECT is_logged_in FROM user_session WHERE is_logged_in = 1").fetchone()
    conn.close()
    return bool(row)

# Settings Helpers
def save_setting(key, value):
    conn = get_db()
    with conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.close()

def get_setting(key, default=""):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

# Audit Logger
def log_audit(action, table_name, record_id, details=""):
    conn = get_db()
    with conn:
        conn.execute(
            "INSERT INTO audit_logs (timestamp, action, table_name, record_id, details) VALUES (?, ?, ?, ?, ?)",
            (datetime.datetime.now().isoformat(), action, table_name, record_id, details)
        )
    conn.close()

# Shift Summary (Cow & Buffalo Split)
def get_shift_summary(date_str, shift_str):
    conn = get_db()
    query = '''
        SELECT 
            milk_type,
            COUNT(*) as count,
            SUM(litres) as total_litres,
            SUM(litres * fat) / CASE WHEN SUM(litres)=0 THEN 1 ELSE SUM(litres) END as avg_fat,
            SUM(litres * snf) / CASE WHEN SUM(litres)=0 THEN 1 ELSE SUM(litres) END as avg_snf,
            SUM(total_amount) as total_amount
        FROM milk_purchases
        WHERE date = ? AND shift = ?
        GROUP BY milk_type
    '''
    rows = conn.execute(query, (date_str, shift_str)).fetchall()
    conn.close()

    summary = {
        "Cow": {"litres": 0.0, "avg_fat": 0.0, "amount": 0.0, "count": 0},
        "Buffalo": {"litres": 0.0, "avg_fat": 0.0, "amount": 0.0, "count": 0}
    }
    for r in rows:
        mtype = r["milk_type"]
        if mtype in summary:
            summary[mtype] = {
                "litres": round(r["total_litres"] or 0.0, 2),
                "avg_fat": round(r["avg_fat"] or 0.0, 2),
                "amount": round(r["total_amount"] or 0.0, 2),
                "count": r["count"] or 0
            }
    return summary

# Farmer Khata Calculation (Running Balance)
def get_farmer_khata_balance(farmer_code):
    conn = get_db()
    purchases = conn.execute("SELECT SUM(total_amount) as total FROM milk_purchases WHERE farmer_code = ?", (farmer_code,)).fetchone()["total"] or 0.0
    paid = conn.execute("SELECT SUM(amount) as total FROM farmer_payments WHERE farmer_code = ?", (farmer_code,)).fetchone()["total"] or 0.0
    conn.close()
    return round(purchases - paid, 2)
