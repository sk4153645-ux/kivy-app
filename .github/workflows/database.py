# database.py - Central Brain, SQLite Queries, Calculations & Bluetooth Hardware Driver
import os
import sqlite3
from datetime import date, datetime

DB_NAME = "dairy_v2.db"

# ============================================================
# 1. CORE CONNECTION & DATABASE INITIALIZATION
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # 1. App Configuration & Hardware Settings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Seed default values
    defaults = {
        "language": "hi",
        "dairy_name": "Nilgiri Dairy Collection",
        "dairy_phone": "",
        "printer_mac": "",
        "analyzer_mac": "",
        "cow_fat_factor": "6.5",
        "cow_snf_factor": "1.5",
        "buff_fat_factor": "7.2",
        "buff_snf_factor": "1.8"
    }
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)", (k, v))

    # 2. Farmers Master Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS farmers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            milk_type TEXT NOT NULL DEFAULT 'Cow',
            default_rate REAL DEFAULT 0.0,
            updated_at TEXT DEFAULT '',
            is_synced INTEGER DEFAULT 0
        )
    """)

    # 3. Milk Inward Collection (Purchases from Farmers)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS milk_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            shift TEXT NOT NULL,
            milk_type TEXT NOT NULL DEFAULT 'Cow',
            litres REAL NOT NULL,
            fat REAL DEFAULT 0.0,
            snf REAL DEFAULT 0.0,
            rate REAL NOT NULL,
            amount REAL NOT NULL,
            updated_at TEXT DEFAULT '',
            is_synced INTEGER DEFAULT 0,
            FOREIGN KEY(farmer_id) REFERENCES farmers(id) ON DELETE CASCADE
        )
    """)

    # 4. Farmer Payments Ledger (Cash Paid to Farmers)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS farmer_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL,
            payment_date TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            updated_at TEXT DEFAULT '',
            is_synced INTEGER DEFAULT 0,
            FOREIGN KEY(farmer_id) REFERENCES farmers(id) ON DELETE CASCADE
        )
    """)

    # 5. Retail Customers Master Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            default_rate REAL DEFAULT 0.0,
            updated_at TEXT DEFAULT '',
            is_synced INTEGER DEFAULT 0
        )
    """)

    # 6. Milk Outward Sales (Sales to Retail Customers)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS milk_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            session TEXT NOT NULL,
            litres REAL NOT NULL,
            rate REAL NOT NULL,
            amount REAL NOT NULL,
            updated_at TEXT DEFAULT '',
            is_synced INTEGER DEFAULT 0,
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE,
            UNIQUE(customer_id, entry_date, session)
        )
    """)

    # 7. Customer Payments Ledger (Cash Received from Customers)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            payment_date TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            updated_at TEXT DEFAULT '',
            is_synced INTEGER DEFAULT 0,
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)

    # Search Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pur_farmer ON milk_purchases(farmer_id, entry_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fpay_f ON farmer_payments(farmer_id, payment_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sl_cust ON milk_entries(customer_id, entry_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cpay_c ON payments(customer_id, payment_date)")

    conn.commit()
    conn.close()


# ============================================================
# 2. SETTINGS & RATE CALCULATOR ENGINE
# ============================================================

def get_setting(key, default=""):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key=?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        return default

def set_setting(key, val):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, str(val)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Setting save error: {e}")

def calculate_milk_rate(fat, snf, milk_type="Cow", manual_rate=None):
    if manual_rate and manual_rate > 0:
        return manual_rate
    
    cow_fat = float(get_setting("cow_fat_factor", "6.5"))
    cow_snf = float(get_setting("cow_snf_factor", "1.5"))
    buff_fat = float(get_setting("buff_fat_factor", "7.2"))
    buff_snf = float(get_setting("buff_snf_factor", "1.8"))

    if fat > 0 and snf > 0:
        if milk_type == "Cow":
            return round((fat * cow_fat) + (snf * cow_snf), 2)
        return round((fat * buff_fat) + (snf * buff_snf), 2)
    elif fat > 0:
        return round(fat * 8.5, 2)
    
    return 40.0 if milk_type == "Cow" else 55.0


# ============================================================
# 3. FARMERS & BUY MILK OPERATIONS
# ============================================================

def get_farmer_by_code(code):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, name, milk_type, default_rate FROM farmers WHERE code=? OR id=?", (code, code))
        row = cur.fetchone()
        conn.close()
        return row
    except Exception:
        return None

def save_buy_entry(fid, shift, milk_type, litres, fat, snf, rate, amount):
    try:
        conn = get_db()
        cur = conn.cursor()
        now_iso = datetime.utcnow().isoformat()
        cur.execute("""
            INSERT INTO milk_purchases (farmer_id, entry_date, shift, milk_type, litres, fat, snf, rate, amount, updated_at, is_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (fid, date.today().isoformat(), shift, milk_type, litres, fat, snf, rate, amount, now_iso))
        conn.commit()
        conn.close()
        return True, "Entry Saved"
    except Exception as e:
        return False, str(e)

def get_today_collection():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT f.code, f.name, p.shift, p.milk_type, p.litres, p.fat, p.snf, p.rate, p.amount
            FROM milk_purchases p
            JOIN farmers f ON f.id = p.farmer_id
            WHERE p.entry_date=?
            ORDER BY p.id DESC
        """, (date.today().isoformat(),))
        rows = cur.fetchall()
        conn.close()

        total_l = sum(r[4] for r in rows)
        total_a = sum(r[8] for r in rows)
        return rows, total_l, total_a
    except Exception:
        return [], 0.0, 0.0

def get_farmers_with_balance():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, phone, milk_type, default_rate FROM farmers ORDER BY CAST(code AS INTEGER), id")
        farmers = cur.fetchall()

        result = []
        for fid, code, name, phone, mtype, rate in farmers:
            cd_str = str(code) if code else f"{fid:02d}"
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM milk_purchases WHERE farmer_id=?", (fid,))
            bill = cur.fetchone()[0] or 0.0
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM farmer_payments WHERE farmer_id=?", (fid,))
            paid = cur.fetchone()[0] or 0.0
            due = bill - paid
            result.append((fid, cd_str, name, phone, mtype, rate, due))
        
        conn.close()
        return result
    except Exception:
        return []

def save_farmer(fid, code, name, phone, rate):
    try:
        conn = get_db()
        cur = conn.cursor()
        now_iso = datetime.utcnow().isoformat()
        if fid:
            cur.execute("UPDATE farmers SET code=?, name=?, phone=?, default_rate=?, updated_at=?, is_synced=0 WHERE id=?", (code, name, phone, rate, now_iso, fid))
        else:
            cur.execute("INSERT INTO farmers (code, name, phone, milk_type, default_rate, updated_at, is_synced) VALUES (?, ?, ?, 'Cow', ?, ?, 0)", (code, name, phone, rate, now_iso))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def save_farmer_payment(fid, amount, note):
    try:
        conn = get_db()
        cur = conn.cursor()
        now_iso = datetime.utcnow().isoformat()
        cur.execute("""
            INSERT INTO farmer_payments (farmer_id, payment_date, amount, note, updated_at, is_synced)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (fid, date.today().isoformat(), amount, note, now_iso))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# ============================================================
# 4. CUSTOMERS & SELL MILK OPERATIONS
# ============================================================

def get_customer_sales_status(session):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, default_rate FROM customers ORDER BY CAST(code AS INTEGER), id")
        customers = cur.fetchall()

        cur.execute("SELECT customer_id, litres, rate, amount FROM milk_entries WHERE entry_date=? AND session=?", (date.today().isoformat(), session))
        entries = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}
        conn.close()

        result = []
        for cid, code, name, def_rate in customers:
            cd_str = str(code) if code else f"{cid:02d}"
            result.append((cid, cd_str, name, def_rate, entries.get(cid)))
        return result
    except Exception:
        return []

def save_customer_sale(cid, session, litres, rate):
    try:
        conn = get_db()
        cur = conn.cursor()
        now_iso = datetime.utcnow().isoformat()
        cur.execute("""
            INSERT OR REPLACE INTO milk_entries (customer_id, entry_date, session, litres, rate, amount, updated_at, is_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (cid, date.today().isoformat(), session, litres, rate, litres * rate, now_iso))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def get_customers_with_balance():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, phone, default_rate FROM customers ORDER BY CAST(code AS INTEGER), id")
        customers = cur.fetchall()

        result = []
        for cid, code, name, phone, rate in customers:
            cd_str = str(code) if code else f"{cid:02d}"
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM milk_entries WHERE customer_id=?", (cid,))
            sale = cur.fetchone()[0] or 0.0
            cur.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE customer_id=?", (cid,))
            rec = cur.fetchone()[0] or 0.0
            due = sale - rec
            result.append((cid, cd_str, name, phone, rate, due))
        conn.close()
        return result
    except Exception:
        return []

def save_customer(cid, code, name, phone, rate):
    try:
        conn = get_db()
        cur = conn.cursor()
        now_iso = datetime.utcnow().isoformat()
        if cid:
            cur.execute("UPDATE customers SET code=?, name=?, phone=?, default_rate=?, updated_at=?, is_synced=0 WHERE id=?", (code, name, phone, rate, now_iso, cid))
        else:
            cur.execute("INSERT INTO customers (code, name, phone, default_rate, updated_at, is_synced) VALUES (?, ?, ?, ?, ?, 0)", (code, name, phone, rate, now_iso))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def save_customer_payment(cid, amount, note):
    try:
        conn = get_db()
        cur = conn.cursor()
        now_iso = datetime.utcnow().isoformat()
        cur.execute("""
            INSERT INTO payments (customer_id, payment_date, amount, note, updated_at, is_synced)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (cid, date.today().isoformat(), amount, note, now_iso))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# ============================================================
# 5. BLUETOOTH THERMAL PRINTER HARDWARE DRIVER
# ============================================================

def print_collection_slip(shift, name, code, mtype, litres, fat, snf, rate, amount):
    mac = get_setting("printer_mac", "")
    if not mac:
        return False, "Printer MAC address not set."

    dairy = get_setting("dairy_name", "NILGIRI DAIRY")
    phone = get_setting("dairy_phone", "")

    receipt_text = f"""
================================
     {dairy.upper()}
   Phone: {phone}
================================
Date: {datetime.now().strftime('%d-%m-%Y %I:%M %p')}
Shift: {shift.upper()}
Farmer: [{code}] {name}
Milk: {mtype.upper()}
--------------------------------
Qty:     {litres:.2f} L
Fat:     {fat:.1f} %
SNF:     {snf:.1f}
Rate:    Rs. {rate:.2f} /L
--------------------------------
TOTAL:   Rs. {amount:.2f}
================================
    Thank You For Clean Milk!
\n\n\n
"""

    try:
        from jnius import autoclass
        BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
        UUID = autoclass('java.util.UUID')

        adapter = BluetoothAdapter.getDefaultAdapter()
        if not adapter or not adapter.isEnabled():
            return False, "Phone Bluetooth is turned OFF."

        device = adapter.getRemoteDevice(mac)
        spp_uuid = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
        socket = device.createRfcommSocketToServiceRecord(spp_uuid)
        socket.connect()

        out_stream = socket.getOutputStream()
        # ESC/POS Init & Data Feed
        out_stream.write(b'\x1b@')
        out_stream.write(receipt_text.encode('utf-8'))
        out_stream.flush()
        socket.close()
        return True, "Printed"
    except Exception as e:
        return False, f"Print error: {e}"
