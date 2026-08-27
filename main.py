import os
import sqlite3
import threading
from calendar import monthrange
from datetime import date, datetime

from kivy.app import App
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserIconView

# Safe Dynamic Imports
try:
    from dairy_ai_scanner import scan_dairy_register, export_to_excel, export_to_pdf
    AI_SCANNER_AVAILABLE = True
except Exception:
    AI_SCANNER_AVAILABLE = False

try:
    from openpyxl import Workbook
    XLSX_AVAILABLE = True
except Exception:
    XLSX_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False

try:
    from androidstorage4kivy import SharedStorage, ShareSheet
    ANDROID_STORAGE_AVAILABLE = True
except Exception:
    ANDROID_STORAGE_AVAILABLE = False

APP_NAME = "Nilgiri Dairy App"


# ============================================================
# DATABASE SETUP (Android 100% Crash-Proof)
# ============================================================

def get_db_path():
    try:
        app = App.get_running_app()
        if app and getattr(app, 'user_data_dir', None):
            return os.path.join(app.user_data_dir, "dairy.db")
    except Exception:
        pass
    return "dairy.db"


def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    try:
        path = get_db_path()
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL,
                phone TEXT NOT NULL DEFAULT '',
                default_rate REAL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS milk_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                entry_date TEXT NOT NULL,
                session TEXT NOT NULL,
                litres REAL NOT NULL,
                rate REAL NOT NULL,
                amount REAL NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE,
                UNIQUE(customer_id, entry_date, session)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                payment_date TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
            )
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_milk_cust_date ON milk_entries(customer_id, entry_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pay_cust_date ON payments(customer_id, payment_date)")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")


# ============================================================
# HELPERS
# ============================================================

def make_button(text, height=50, font=15, bg_color=(0.12, 0.45, 0.25, 1.0)):
    return Button(
        text=text,
        font_size=dp(font),
        size_hint_y=None,
        height=dp(height),
        background_normal='',
        background_color=bg_color,
        color=(1, 1, 1, 1),
        bold=True
    )


def make_card_button(text, height=65, font=13):
    btn = Button(
        text=text,
        font_size=dp(font),
        size_hint_y=None,
        height=dp(height),
        background_normal='',
        background_color=(1, 1, 1, 1),
        color=(0.1, 0.2, 0.1, 1.0),
        halign='left',
        valign='middle'
    )
    btn.bind(size=btn.setter('text_size'))
    return btn


def make_input(hint="", value="", numeric=False):
    return TextInput(
        text=str(value) if value is not None else "",
        hint_text=hint,
        multiline=False,
        font_size=dp(15),
        input_filter="float" if numeric else None,
        size_hint_y=None,
        height=dp(46)
    )


def show_message(title, message):
    box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
    box.add_widget(Label(text=message, font_size=dp(14)))
    close = make_button("OK", 42, 14)
    box.add_widget(close)
    popup = Popup(title=title, content=box, size_hint=(0.85, 0.35))
    close.bind(on_press=popup.dismiss)
    popup.open()


def parse_positive_float(value):
    try:
        n = float(value)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def format_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
    except Exception:
        return str(value)


def month_title(year, month):
    return date(year, month, 1).strftime("%B %Y")


def previous_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def next_month(year, month):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def month_start_end(year, month):
    return (
        date(year, month, 1).isoformat(),
        date(year, month, monthrange(year, month)[1]).isoformat(),
    )


def get_customer_balance(customer_id, upto_date=None):
    try:
        conn = get_db()
        cur = conn.cursor()
        if upto_date:
            cur.execute("SELECT COALESCE(SUM(amount),0) FROM milk_entries WHERE customer_id=? AND entry_date<=?", (customer_id, upto_date))
            milk = cur.fetchone()[0] or 0
            cur.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE customer_id=? AND payment_date<=?", (customer_id, upto_date))
            paid = cur.fetchone()[0] or 0
        else:
            cur.execute("SELECT COALESCE(SUM(amount),0) FROM milk_entries WHERE customer_id=?", (customer_id,))
            milk = cur.fetchone()[0] or 0
            cur.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE customer_id=?", (customer_id,))
            paid = cur.fetchone()[0] or 0
        conn.close()
        return milk, paid, milk - paid
    except Exception:
        return 0, 0, 0


def get_customer_month_data(customer_id, year, month):
    try:
        start_date, end_date = month_start_end(year, month)
        prev_y, prev_m = previous_month(year, month)
        previous_end = date(prev_y, prev_m, monthrange(prev_y, prev_m)[1]).isoformat()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(amount),0), COALESCE(SUM(litres),0) FROM milk_entries WHERE customer_id=? AND entry_date BETWEEN ? AND ?", (customer_id, start_date, end_date))
        current_amount, current_litres = cur.fetchone()

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM milk_entries WHERE customer_id=? AND entry_date<=?", (customer_id, previous_end))
        prev_milk = cur.fetchone()[0] or 0

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE customer_id=? AND payment_date<=?", (customer_id, previous_end))
        prev_paid = cur.fetchone()[0] or 0

        cur.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE customer_id=? AND payment_date BETWEEN ? AND ?", (customer_id, start_date, end_date))
        current_paid = cur.fetchone()[0] or 0
        conn.close()

        previous_due = prev_milk - prev_paid
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


# ============================================================
# SCREENS
# ============================================================

class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", spacing=dp(8))

        header = Button(
            text="🌿  Nilgiri Dairy App",
            font_size=dp(20),
            bold=True,
            size_hint_y=None,
            height=dp(54),
            background_normal='',
            background_color=(0.12, 0.37, 0.23, 1),
            color=(1, 1, 1, 1)
        )
        layout.add_widget(header)

        scroll = ScrollView()
        body = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, padding=[dp(10), dp(6)])
        body.bind(minimum_height=body.setter("height"))

        grid_main = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(200))
        btn_milk_entry = make_button("🥛  Milk Entry\n(Daily Hisaab)", 90, 15, bg_color=(0.18, 0.55, 0.34, 1))
        btn_today_milk = make_button("📅  Today's Milk\n(Aaj Ka Doodh)", 90, 15, bg_color=(0.20, 0.50, 0.40, 1))
        btn_customers = make_button("👥  Customers\n(Grahak List)", 90, 15, bg_color=(0.22, 0.45, 0.55, 1))
        btn_ai_scan = make_button("📷  AI Scanner\n(Register Scan)", 90, 15, bg_color=(0.80, 0.40, 0.15, 1))

        btn_milk_entry.bind(on_press=lambda _: self.open_session_picker())
        btn_today_milk.bind(on_press=lambda _: setattr(self.manager, "current", "today"))
        btn_customers.bind(on_press=lambda _: setattr(self.manager, "current", "customers"))
        btn_ai_scan.bind(on_press=lambda _: setattr(self.manager, "current", "scan_register"))

        grid_main.add_widget(btn_milk_entry)
        grid_main.add_widget(btn_today_milk)
        grid_main.add_widget(btn_customers)
        grid_main.add_widget(btn_ai_scan)
        body.add_widget(grid_main)

        body.add_widget(Label(text="REPORTS & KHATA", font_size=dp(13), bold=True, color=(0.12, 0.37, 0.23, 1), size_hint_y=None, height=dp(22)))

        grid_reports = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(60))
        btn_reports = make_button("📊 Full Reports\n& Khata", 56, 13, bg_color=(0.35, 0.45, 0.40, 1))
        btn_reports.bind(on_press=lambda _: setattr(self.manager, "current", "reports"))
        grid_reports.add_widget(btn_reports)
        body.add_widget(grid_reports)

        scroll.add_widget(body)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def open_session_picker(self):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        box.add_widget(Label(text="Select Milk Entry Session", font_size=dp(16), bold=True))

        btn_m = make_button("☀️  MORNING (सुबह का दूध)", 50, 14, bg_color=(0.95, 0.60, 0.10, 1))
        btn_e = make_button("🌙  EVENING (शाम का दूध)", 50, 14, bg_color=(0.20, 0.35, 0.60, 1))

        box.add_widget(btn_m)
        box.add_widget(btn_e)

        popup = Popup(title="Milk Entry", content=box, size_hint=(0.85, 0.40))

        def select_m(_):
            popup.dismiss()
            screen = self.manager.get_screen("daily_entry")
            screen.set_session("Morning")
            self.manager.current = "daily_entry"

        def select_e(_):
            popup.dismiss()
            screen = self.manager.get_screen("daily_entry")
            screen.set_session("Evening")
            self.manager.current = "daily_entry"

        btn_m.bind(on_press=select_m)
        btn_e.bind(on_press=select_e)
        popup.open()


class DailyEntryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = "Morning"
        self.current_date = date.today().isoformat()

        layout = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))

        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)

        self.title_lbl = Label(text="Morning Milk Entry", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1))
        top.add_widget(self.title_lbl)
        layout.add_widget(top)

        self.search_input = TextInput(
            hint_text="🔍 Search Name or Code...",
            multiline=False,
            font_size=dp(15),
            size_hint_y=None,
            height=dp(44)
        )
        self.search_input.bind(text=lambda *_: self.load_customer_entries())
        layout.add_widget(self.search_input)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)

        self.summary_bar = Button(
            text="Total: 0.00 L | Rs. 0.00",
            font_size=dp(14),
            bold=True,
            size_hint_y=None,
            height=dp(38),
            background_normal='',
            background_color=(0.12, 0.37, 0.23, 1),
            color=(1, 1, 1, 1)
        )
        layout.add_widget(self.summary_bar)
        self.add_widget(layout)

    def set_session(self, session_name):
        self.session = session_name
        self.title_lbl.text = f"{'☀️ Morning' if session_name == 'Morning' else '🌙 Evening'} ({format_date(self.current_date)})"

    def on_pre_enter(self):
        self.load_customer_entries()

    def load_customer_entries(self):
        self.list_layout.clear_widgets()
        search_term = self.search_input.text.strip().lower()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, default_rate FROM customers ORDER BY CAST(code AS INTEGER), id")
        customers = cur.fetchall()

        cur.execute("""
            SELECT customer_id, litres, rate, amount
            FROM milk_entries
            WHERE entry_date=? AND session=?
        """, (self.current_date, self.session))
        entries = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}
        conn.close()

        total_litres = 0.0
        total_amount = 0.0

        for cid, code, name, def_rate in customers:
            code_str = str(code) if code else f"{cid:02d}"
            if search_term and search_term not in name.lower() and search_term not in code_str.lower():
                continue

            entry = entries.get(cid)
            if entry:
                l, r, amt = entry
                total_litres += l
                total_amount += amt
                card_text = f"  [{code_str}]  {name}  (Rate: Rs.{r:.2f})\n  ✓ Done: {l:.2f} L  |  Amount: Rs.{amt:.2f}"
                btn = make_card_button(card_text, height=64, font=13)
                btn.background_color = (0.85, 0.95, 0.85, 1)
            else:
                rate_disp = f"Rs.{def_rate:.2f}" if def_rate else "Manual"
                card_text = f"  [{code_str}]  {name}  (Rate: {rate_disp})\n  [ Tap to enter milk litres... ]"
                btn = make_card_button(card_text, height=64, font=13)

            btn.bind(on_press=lambda _, c=cid, n=name, cd=code_str, dr=def_rate, e=entry: self.open_entry_popup(c, n, cd, dr, e))
            self.list_layout.add_widget(btn)

        self.summary_bar.text = f"Total {self.session}: {total_litres:.2f} L | Rs.{total_amount:.2f}"

    def open_entry_popup(self, cid, name, code_str, def_rate, existing_entry):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        box.add_widget(Label(text=f"[{code_str}] {name}", font_size=dp(15), bold=True))

        init_litres = str(existing_entry[0]) if existing_entry else ""
        init_rate = str(existing_entry[1]) if existing_entry else (str(def_rate) if def_rate else "")

        litres_in = make_input("Enter Litres *", init_litres, numeric=True)
        rate_in = make_input("Enter Rate *", init_rate, numeric=True)
        amt_lbl = Label(text="Amount: Rs. 0.00", font_size=dp(13))

        box.add_widget(litres_in)
        box.add_widget(rate_in)
        box.add_widget(amt_lbl)

        def calc_amt(*_):
            l = parse_positive_float(litres_in.text)
            r = parse_positive_float(rate_in.text)
            amt_lbl.text = f"Amount: Rs. {l * r:.2f}" if l and r else "Amount: Rs. 0.00"

        litres_in.bind(text=calc_amt)
        rate_in.bind(text=calc_amt)
        calc_amt()

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_cancel = make_button("CANCEL", 42, 13, bg_color=(0.5, 0.5, 0.5, 1))
        btn_save = make_button("SAVE", 42, 13, bg_color=(0.18, 0.55, 0.34, 1))
        btns.add_widget(btn_cancel)
        btns.add_widget(btn_save)
        box.add_widget(btns)

        popup = Popup(title=f"{self.session} Entry", content=box, size_hint=(0.85, 0.50))
        btn_cancel.bind(on_press=popup.dismiss)

        def save_entry(_):
            l = parse_positive_float(litres_in.text)
            r = parse_positive_float(rate_in.text)
            if not l or not r:
                show_message("Error", "Valid numbers daalein.")
                return

            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO milk_entries (customer_id, entry_date, session, litres, rate, amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (cid, self.current_date, self.session, l, r, l * r))
            conn.commit()
            conn.close()

            popup.dismiss()
            self.load_customer_entries()

        btn_save.bind(on_press=save_entry)
        popup.open()


class CustomersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)

        top.add_widget(Label(text="Customers", font_size=dp(17), bold=True, color=(0.1, 0.3, 0.1, 1)))

        add_btn = make_button("+ Add", 42, 13, bg_color=(0.18, 0.55, 0.34, 1))
        add_btn.size_hint_x = None
        add_btn.width = dp(75)
        add_btn.bind(on_press=lambda _: self.customer_form())
        top.add_widget(add_btn)
        layout.add_widget(top)

        self.search_in = TextInput(hint_text="🔍 Search Name/Code...", multiline=False, font_size=dp(15), size_hint_y=None, height=dp(44))
        self.search_in.bind(text=lambda *_: self.load_customers())
        layout.add_widget(self.search_in)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)

        self.add_widget(layout)

    def on_pre_enter(self):
        self.load_customers()

    def load_customers(self):
        self.list_layout.clear_widgets()
   
