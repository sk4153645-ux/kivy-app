# database.py - Central Brain: SQLite Engine, Hardware Drivers, SMS/WhatsApp & Calculations
import os
import re
import sqlite3
import urllib.parse
from calendar import monthrange
from datetime import date, datetime

DB_FILENAME = "dairy_v2.db"

# ============================================================
# 1. DATABASE INITIALIZATION & SCHEMA SETUP
# ============================================================

def get_db_path():
    # On Android, the working directory is not reliably writable.
    # Always store the database under the app's private, writable
    # user_data_dir when running under Kivy; fall back to a local
    # file for desktop testing.
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app and getattr(app, "user_data_dir", None):
            return os.path.join(app.user_data_dir, DB_FILENAME)
    except Exception:
        pass
    return DB_FILENAME


def get_export_dir():
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app and getattr(app, "user_data_dir", None):
            path = os.path.join(app.user_data_dir, "exports")
        else:
            path = "exports"
    except Exception:
        path = "exports"
    os.makedirs(path, exist_ok=True)
    return path


def get_db():
    conn = sqlite3.connect(get_db_path(), timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    path = get_db_path()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    conn = get_db()
    cur = conn.cursor()

    # 1. App Configuration & Hardware Settings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    defaults = {
        "language": "hi",
        "dairy_name": "Nilgiri Dairy Collection",
        "dairy_phone": "",
        "printer_mac": "",
        "analyzer_mac": "",
        "cow_fat_factor": "6.5",
        "cow_snf_factor": "1.5",
        "buff_fat_factor": "7.2",
        "buff_snf_factor": "1.8",
        "auto_sms": "0",
        "auto_whatsapp": "0"
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

    cur.execute("CREATE INDEX IF NOT EXISTS idx_pur_farmer ON milk_purchases(farmer_id, entry_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fpay_f ON farmer_payments(farmer_id, payment_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sl_cust ON milk_entries(customer_id, entry_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cpay_c ON payments(customer_id, payment_date)")

    conn.commit()
    conn.close()


# ============================================================
# 2. SETTINGS & RATE CALCULATION ENGINE
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
        print(f"Settings Error: {e}")


def calculate_milk_rate(fat, snf, milk_type="Cow", manual_rate=None):
    if manual_rate and manual_rate > 0:
        return manual_rate

    try:
        cow_fat = float(get_setting("cow_fat_factor", "6.5"))
        cow_snf = float(get_setting("cow_snf_factor", "1.5"))
        buff_fat = float(get_setting("buff_fat_factor", "7.2"))
        buff_snf = float(get_setting("buff_snf_factor", "1.8"))
    except Exception:
        cow_fat, cow_snf, buff_fat, buff_snf = 6.5, 1.5, 7.2, 1.8

    if fat > 0 and snf > 0:
        if milk_type == "Cow":
            return round((fat * cow_fat) + (snf * cow_snf), 2)
        return round((fat * buff_fat) + (snf * buff_snf), 2)
    elif fat > 0:
        return round(fat * 8.5, 2)

    return 40.0 if milk_type == "Cow" else 55.0


# ============================================================
# 3. MONTH HELPERS (shared by farmer + customer reports)
# ============================================================

def month_start_end(year, month):
    return (
        date(year, month, 1).isoformat(),
        date(year, month, monthrange(year, month)[1]).isoformat(),
    )


def previous_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


# ============================================================
# 4. FARMERS & BUY MILK OPERATIONS
# ============================================================

def get_farmer_by_code(code):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, name, milk_type, default_rate, phone FROM farmers WHERE code=? OR id=?", (code, code))
        row = cur.fetchone()
        conn.close()
        return row
    except Exception:
        return None


def get_farmer_due_balance(farmer_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM milk_purchases WHERE farmer_id=?", (farmer_id,))
        bill = cur.fetchone()[0] or 0.0
        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM farmer_payments WHERE farmer_id=?", (farmer_id,))
        paid = cur.fetchone()[0] or 0.0
        conn.close()
        return bill - paid
    except Exception:
        return 0.0


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


def save_farmer(fid, code, name, phone, milk_type, rate):
    try:
        conn = get_db()
        cur = conn.cursor()
        now_iso = datetime.utcnow().isoformat()
        if fid:
            cur.execute("""
                UPDATE farmers SET code=?, name=?, phone=?, milk_type=?, default_rate=?, updated_at=?, is_synced=0
                WHERE id=?
            """, (code, name, phone, milk_type, rate, now_iso, fid))
        else:
            cur.execute("""
                INSERT INTO farmers (code, name, phone, milk_type, default_rate, updated_at, is_synced)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (code, name, phone, milk_type, rate, now_iso))
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


def get_farmer_month_data(farmer_id, year, month):
    try:
        start_date, end_date = month_start_end(year, month)
        prev_y, prev_m = previous_month(year, month)
        previous_end = date(prev_y, prev_m, monthrange(prev_y, prev_m)[1]).isoformat()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(amount),0), COALESCE(SUM(litres),0)
            FROM milk_purchases WHERE farmer_id=? AND entry_date BETWEEN ? AND ?
        """, (farmer_id, start_date, end_date))
        current_amount, current_litres = cur.fetchone()

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM milk_purchases WHERE farmer_id=? AND entry_date<=?", (farmer_id, previous_end))
        prev_bill = cur.fetchone()[0] or 0

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM farmer_payments WHERE farmer_id=? AND payment_date<=?", (farmer_id, previous_end))
        prev_paid = cur.fetchone()[0] or 0

        cur.execute("""
            SELECT COALESCE(SUM(amount),0) FROM farmer_payments
            WHERE farmer_id=? AND payment_date BETWEEN ? AND ?
        """, (farmer_id, start_date, end_date))
        current_paid = cur.fetchone()[0] or 0
        conn.close()

        previous_due = prev_bill - prev_paid
        total_due = previous_due + (current_amount or 0) - (current_paid or 0)

        return {
            "previous_due": previous_due,
            "current_litres": current_litres or 0,
            "current_amount": current_amount or 0,
            "current_paid": current_paid or 0,
            "total_due": total_due,
        }
    except Exception:
        return {"previous_due": 0, "current_litres": 0, "current_amount": 0, "current_paid": 0, "total_due": 0}


def get_farmer_month_entries(farmer_id, year, month):
    try:
        start_date, end_date = month_start_end(year, month)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT entry_date, litres, rate, amount FROM milk_purchases
            WHERE farmer_id=? AND entry_date BETWEEN ? AND ? ORDER BY entry_date
        """, (farmer_id, start_date, end_date))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


# ============================================================
# 5. CUSTOMERS & SELL MILK OPERATIONS
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


def get_customer_month_data(customer_id, year, month):
    try:
        start_date, end_date = month_start_end(year, month)
        prev_y, prev_m = previous_month(year, month)
        previous_end = date(prev_y, prev_m, monthrange(prev_y, prev_m)[1]).isoformat()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(amount),0), COALESCE(SUM(litres),0)
            FROM milk_entries WHERE customer_id=? AND entry_date BETWEEN ? AND ?
        """, (customer_id, start_date, end_date))
        current_amount, current_litres = cur.fetchone()

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM milk_entries WHERE customer_id=? AND entry_date<=?", (customer_id, previous_end))
        prev_sale = cur.fetchone()[0] or 0

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE customer_id=? AND payment_date<=?", (customer_id, previous_end))
        prev_paid = cur.fetchone()[0] or 0

        cur.execute("""
            SELECT COALESCE(SUM(amount),0) FROM payments
            WHERE customer_id=? AND payment_date BETWEEN ? AND ?
        """, (customer_id, start_date, end_date))
        current_paid = cur.fetchone()[0] or 0
        conn.close()

        previous_due = prev_sale - prev_paid
        total_due = previous_due + (current_amount or 0) - (current_paid or 0)

        return {
            "previous_due": previous_due,
            "current_litres": current_litres or 0,
            "current_amount": current_amount or 0,
            "current_paid": current_paid or 0,
            "total_due": total_due,
        }
    except Exception:
        return {"previous_due": 0, "current_litres": 0, "current_amount": 0, "current_paid": 0, "total_due": 0}


def get_customer_month_entries(customer_id, year, month):
    try:
        start_date, end_date = month_start_end(year, month)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT entry_date, litres, rate, amount FROM milk_entries
            WHERE customer_id=? AND entry_date BETWEEN ? AND ? ORDER BY entry_date
        """, (customer_id, start_date, end_date))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


# ============================================================
# 6. WHATSAPP & NATIVE SMS COMMUNICATION ENGINE
# ============================================================

def format_collection_message(shift, name, mtype, litres, fat, snf, rate, amount, due_balance):
    dairy_name = get_setting("dairy_name", "NILGIRI DAIRY").strip()
    msg = (
        f"🌿 *{dairy_name.upper()}*\n"
        f"Namaste *{name}* Ji,\n"
        f"Aapka doodh safalta-purvak jama ho gaya hai:\n"
        f"--------------------------------\n"
        f"📅 Date: {datetime.now().strftime('%d-%m-%Y')} ({shift})\n"
        f"🥛 Quantity: {litres:.2f} L ({mtype})\n"
        f"🧪 Fat: {fat:.1f}% | SNF: {snf:.1f}\n"
        f"💰 Rate: ₹{rate:.2f} /L\n"
        f"💵 Total Amount: ₹{amount:.2f}\n"
        f"📊 Kul Baaki Balance: ₹{due_balance:.2f}\n"
        f"--------------------------------\n"
        f"Dhanyawad! Keep Clean Milk."
    )
    return msg


def send_native_sms(phone, message_text):
    """Sends background direct offline SMS using Android Telephony Manager."""
    clean_phone = re.sub(r'\D', '', str(phone))
    if len(clean_phone) < 10:
        return False, "Kisan ka valid phone number nahi mila."

    if len(clean_phone) == 10:
        clean_phone = "+91" + clean_phone
    elif not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

    try:
        from jnius import autoclass
        SmsManager = autoclass('android.telephony.SmsManager')
        sms = SmsManager.getDefault()
        sms.sendTextMessage(clean_phone, None, message_text, None, None)
        return True, "SMS sent successfully!"
    except Exception as e:
        return False, f"SMS Dispatch Error: {e}"


def open_whatsapp_chat(phone, message_text):
    """Opens WhatsApp chat with pre-filled message intent."""
    clean_phone = re.sub(r'\D', '', str(phone))
    if len(clean_phone) < 10:
        return False, "Kisan ka valid WhatsApp number nahi mila."

    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone

    encoded_text = urllib.parse.quote(message_text)
    wa_url = f"https://wa.me/{clean_phone}?text={encoded_text}"

    try:
        import webbrowser
        webbrowser.open(wa_url)
        return True, "Opening WhatsApp..."
    except Exception as e:
        return False, f"WhatsApp Error: {e}"


# ============================================================
# 7. HARDWARE PARSERS & BLUETOOTH THERMAL PRINTER
# ============================================================

def parse_analyzer_packet(raw_str):
    """Extracts Fat and SNF from Lactoscan/EkoMilk continuous string."""
    fat, snf = 0.0, 0.0
    try:
        fat_match = re.search(r'(?:FAT|F)[:=]\s*(\d+\.?\d*)', raw_str, re.IGNORECASE)
        snf_match = re.search(r'(?:SNF|S)[:=]\s*(\d+\.?\d*)', raw_str, re.IGNORECASE)
        if fat_match:
            fat = float(fat_match.group(1))
        if snf_match:
            snf = float(snf_match.group(1))
    except Exception:
        pass
    return fat, snf


def parse_weight_packet(raw_str):
    """Extracts numeric weight from weighing scale serial stream."""
    try:
        match = re.search(r'([+]?\d+\.\d+)', raw_str)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return 0.0


def print_collection_slip(shift, name, code, mtype, litres, fat, snf, rate, amount):
    mac = get_setting("printer_mac", "").strip()
    if not mac:
        return False, "Printer MAC address set nahi hai."

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
            return False, "Phone ka Bluetooth band hai."

        device = adapter.getRemoteDevice(mac)
        spp_uuid = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
        socket = device.createRfcommSocketToServiceRecord(spp_uuid)
        socket.connect()

        out_stream = socket.getOutputStream()
        out_stream.write(b'\x1b@')  # ESC/POS Initialize
        out_stream.write(receipt_text.encode('utf-8'))
        out_stream.flush()
        socket.close()
        return True, "Slip Printed!"
    except Exception as e:
        return False, f"Print error: {e}"
