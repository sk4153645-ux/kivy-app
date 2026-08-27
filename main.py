import os
import sqlite3
import threading
from calendar import monthrange
from datetime import date, datetime

from kivy.app import App
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.core.window import Window
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

# Safe AI Scanner Import
try:
    from dairy_ai_scanner import scan_dairy_register, export_to_excel, export_to_pdf
    AI_SCANNER_AVAILABLE = True
except Exception:
    AI_SCANNER_AVAILABLE = False

APP_NAME = "Nilgiri Dairy App"

# Safe Storage / Export Imports
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


# ============================================================
# DATABASE SETUP (Crash-Safe)
# ============================================================

def get_db_path():
    try:
        app = App.get_running_app()
        if app and hasattr(app, 'user_data_dir'):
            return os.path.join(app.user_data_dir, "dairy.db")
    except Exception:
        pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "dairy.db")


def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    try:
        os.makedirs(os.path.dirname(get_db_path()), exist_ok=True)
    except Exception:
        pass
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


# ============================================================
# UI HELPERS & STYLING
# ============================================================

def make_button(text, height=50, font=16, bg_color=(0.12, 0.45, 0.25, 1.0)):
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


def make_card_button(text, height=70, font=14):
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
        font_size=dp(16),
        input_filter="float" if numeric else None,
        size_hint_y=None,
        height=dp(48),
        background_color=(1, 1, 1, 1),
        foreground_color=(0.1, 0.1, 0.1, 1.0)
    )


def show_message(title, message):
    box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
    box.add_widget(Label(text=message, font_size=dp(15), color=(0.1, 0.1, 0.1, 1)))
    close = make_button("OK", 45, 15)
    box.add_widget(close)
    popup = Popup(title=title, content=box, size_hint=(0.88, 0.38))
    close.bind(on_press=popup.dismiss)
    popup.open()


def confirm_action(title, message, callback):
    box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
    box.add_widget(Label(text=message, font_size=dp(15), color=(0.1, 0.1, 0.1, 1)))
    btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
    no = make_button("CANCEL", 46, 14, bg_color=(0.5, 0.5, 0.5, 1))
    yes = make_button("YES", 46, 14, bg_color=(0.8, 0.2, 0.2, 1))
    btns.add_widget(no)
    btns.add_widget(yes)
    box.add_widget(btns)
    popup = Popup(title=title, content=box, size_hint=(0.88, 0.38))
    no.bind(on_press=popup.dismiss)

    def do_yes(_):
        popup.dismiss()
        callback()

    yes.bind(on_press=do_yes)
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
        return value


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


# ============================================================
# ACCOUNTING & CALCULATIONS
# ============================================================

def get_customer_balance(customer_id, upto_date=None):
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


def get_customer_month_data(customer_id, year, month):
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
    total_due = previous_due + current_amount - current_paid

    return {
        "previous_due": previous_due,
        "current_litres": current_litres or 0,
        "current_amount": current_amount or 0,
        "current_paid": current_paid or 0,
        "total_due": total_due,
    }


def safe_filename(value):
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    return "".join(c for c in value.replace(" ", "_") if c in allowed) or "report"


def share_or_open_file(path, share=False):
    if ANDROID_STORAGE_AVAILABLE:
        try:
            storage = SharedStorage()
            shared = storage.copy_to_shared(path, collection="DOCUMENTS", filepath=os.path.basename(path))
            if shared:
                if share:
                    ShareSheet().share_file(shared)
                else:
                    ShareSheet().view_file(shared)
                return True
        except Exception:
            pass
    try:
        import webbrowser
        webbrowser.open("file://" + path)
        return True
    except Exception:
        return False


# ============================================================
# SCREENS
# ============================================================

class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", spacing=dp(10))

        header = BoxLayout(size_hint_y=None, height=dp(60), padding=[dp(16), dp(8)])
        header.canvas.before.clear()
        with header.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(0.12, 0.37, 0.23, 1)
            self.rect = Rectangle(size=header.size, pos=header.pos)
            header.bind(size=lambda *_: setattr(self.rect, 'size', header.size),
                        pos=lambda *_: setattr(self.rect, 'pos', header.pos))

        header.add_widget(Label(text="Nilgiri Dairy App", font_size=dp(22), bold=True, color=(1, 1, 1, 1)))
        layout.add_widget(header)

        scroll = ScrollView(padding=[dp(12), dp(8)])
        body = BoxLayout(orientation="vertical", spacing=dp(14), size_hint_y=None, padding=[dp(12), dp(8)])
        body.bind(minimum_height=body.setter("height"))

        grid_main = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(210))
        btn_milk_entry = make_button("🥛  Milk Entry\n(Daily Hisaab)", 95, 16, bg_color=(0.18, 0.55, 0.34, 1))
        btn_today_milk = make_button("📅  Today's Milk\n(Aaj Ka Doodh)", 95, 16, bg_color=(0.20, 0.50, 0.40, 1))
        btn_customers = make_button("👥  Customers\n(Grahak List)", 95, 16, bg_color=(0.22, 0.45, 0.55, 1))
        btn_ai_scan = make_button("📷  AI Scanner\n(Register Scan)", 95, 16, bg_color=(0.80, 0.40, 0.15, 1))

        btn_milk_entry.bind(on_press=lambda _: self.open_session_picker())
        btn_today_milk.bind(on_press=lambda _: setattr(self.manager, "current", "today"))
        btn_customers.bind(on_press=lambda _: setattr(self.manager, "current", "customers"))
        btn_ai_scan.bind(on_press=lambda _: setattr(self.manager, "current", "scan_register"))

        grid_main.add_widget(btn_milk_entry)
        grid_main.add_widget(btn_today_milk)
        grid_main.add_widget(btn_customers)
        grid_main.add_widget(btn_ai_scan)
        body.add_widget(grid_main)

        body.add_widget(Label(text="REGISTERS & BILLING", font_size=dp(14), bold=True, color=(0.2, 0.4, 0.2, 1), size_hint_y=None, height=dp(25)))

        grid_reports = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(70))
        btn_reports = make_button("📊 Full Reports\n& Khata", 60, 14, bg_color=(0.35, 0.45, 0.40, 1))
        btn_reports.bind(on_press=lambda _: setattr(self.manager, "current", "reports"))
        grid_reports.add_widget(btn_reports)
        body.add_widget(grid_reports)

        scroll.add_widget(body)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def open_session_picker(self):
        box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        box.add_widget(Label(text="Select Milk Entry Session", font_size=dp(18), bold=True, color=(0.1, 0.3, 0.1, 1)))

        btn_m = make_button("☀️  MORNING MILK (सुबह का दूध)", 60, 16, bg_color=(0.95, 0.60, 0.10, 1))
        btn_e = make_button("🌙  EVENING MILK (शाम का दूध)", 60, 16, bg_color=(0.20, 0.35, 0.60, 1))

        box.add_widget(btn_m)
        box.add_widget(btn_e)

        popup = Popup(title="Milk Entry", content=box, size_hint=(0.90, 0.45))

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

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = make_button("< Back", 44, 14, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)

        self.title_lbl = Label(text="Morning Milk Entry", font_size=dp(17), bold=True, color=(0.1, 0.3, 0.1, 1))
        top.add_widget(self.title_lbl)
        layout.add_widget(top)

        self.search_input = TextInput(
            hint_text="🔍 Search Name or Code (e.g. 01, Ramesh)...",
            multiline=False,
            font_size=dp(16),
            size_hint_y=None,
            height=dp(46),
            background_color=(1, 1, 1, 1)
        )
        self.search_input.bind(text=lambda *_: self.load_customer_entries())
        layout.add_widget(self.search_input)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)

        self.summary_bar = Label(
            text="Total: 0.00 L | Rs. 0.00",
            font_size=dp(15),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(40)
        )
        self.summary_bar.canvas.before.clear()
        with self.summary_bar.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(0.12, 0.37, 0.23, 1)
            self.s_rect = Rectangle(size=self.summary_bar.size, pos=self.summary_bar.pos)
            self.summary_bar.bind(size=lambda *_: setattr(self.s_rect, 'size', self.summary_bar.size),
                                  pos=lambda *_: setattr(self.s_rect, 'pos', self.summary_bar.pos))

        layout.add_widget(self.summary_bar)
        self.add_widget(layout)

    def set_session(self, session_name):
        self.session = session_name
        self.title_lbl.text = f"{'☀️ Morning' if session_name == 'Morning' else '🌙 Evening'} Entry ({format_date(self.current_date)})"

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
                card_text = f"  [{code_str}]  {name}  (Rate: Rs.{r:.2f})\n  ✓ Status: {l:.2f} L  |  Amount: Rs.{amt:.2f}"
                btn = make_card_button(card_text, height=68, font=13)
                btn.background_color = (0.85, 0.95, 0.85, 1)
            else:
                rate_disp = f"Rs.{def_rate:.2f}" if def_rate else "Manual"
                card_text = f"  [{code_str}]  {name}  (Rate: {rate_disp})\n  [ Tap to enter milk litres... ]"
                btn = make_card_button(card_text, height=68, font=13)

            btn.bind(on_press=lambda _, c=cid, n=name, cd=code_str, dr=def_rate, e=entry: self.open_entry_popup(c, n, cd, dr, e))
            self.list_layout.add_widget(btn)

        self.summary_bar.text = f"Total {self.session} Milk: {total_litres:.2f} L  |  Total: Rs.{total_amount:.2f}"

    def open_entry_popup(self, cid, name, code_str, def_rate, existing_entry):
        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        box.add_widget(Label(text=f"Update Entry: [{code_str}] {name}", font_size=dp(17), bold=True, color=(0.1, 0.3, 0.1, 1)))

        init_litres = str(existing_entry[0]) if existing_entry else ""
        init_rate = str(existing_entry[1]) if existing_entry else (str(def_rate) if def_rate else "")

        litres_in = make_input("Enter Milk (Litres) *", init_litres, numeric=True)
        rate_in = make_input("Enter Rate per Litre *", init_rate, numeric=True)
        amt_lbl = Label(text="Calculated Amount: Rs. 0.00", font_size=dp(15), color=(0.1, 0.2, 0.1, 1))

        box.add_widget(litres_in)
        box.add_widget(rate_in)
        box.add_widget(amt_lbl)

        def calc_amt(*_):
            l = parse_positive_float(litres_in.text)
            r = parse_positive_float(rate_in.text)
            amt_lbl.text = f"Calculated Amount: Rs. {l * r:.2f}" if l and r else "Calculated Amount: Rs. 0.00"

        litres_in.bind(text=calc_amt)
        rate_in.bind(text=calc_amt)
        calc_amt()

        btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        btn_cancel = make_button("CANCEL", 46, 14, bg_color=(0.5, 0.5, 0.5, 1))
        btn_save = make_button("SAVE ENTRY", 46, 14, bg_color=(0.18, 0.55, 0.34, 1))
        btns.add_widget(btn_cancel)
        btns.add_widget(btn_save)
        box.add_widget(btns)

        popup = Popup(title=f"{self.session} Entry", content=box, size_hint=(0.92, 0.58))
        btn_cancel.bind(on_press=popup.dismiss)

        def save_entry(_):
            l = parse_positive_float(litres_in.text)
            r = parse_positive_float(rate_in.text)
            if not l or not r:
                show_message("Error", "Valid Litres aur Rate daalein.")
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

        top = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(6))
        back = make_button("< Back", 46, 14, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)

        top.add_widget(Label(text="Customers List", font_size=dp(19), bold=True, color=(0.1, 0.3, 0.1, 1)))

        add_btn = make_button("+ Add New", 46, 14, bg_color=(0.18, 0.55, 0.34, 1))
        add_btn.size_hint_x = None
        add_btn.width = dp(95)
        add_btn.bind(on_press=lambda _: self.customer_form())
        top.add_widget(add_btn)
        layout.add_widget(top)

        self.search_in = TextInput(
            hint_text="🔍 Search customer name, code or mobile...",
            multiline=False,
            font_size=dp(16),
            size_hint_y=None,
            height=dp(46),
            background_color=(1, 1, 1, 1)
        )
        self.search_in.bind(text=lambda *_: self.load_customers())
        layout.add_widget(self.search_in)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)

        self.add_widget(layout)

    def on_pre_enter(self):
        self.load_customers()

    def load_customers(self):
        self.list_layout.clear_widgets()
        term = self.search_in.text.strip().lower()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name, phone, default_rate FROM customers ORDER BY CAST(code AS INTEGER), id")
        rows = cur.fetchall()
        conn.close()

        for cid, code, name, phone, def_rate in rows:
            code_str = str(code) if code else f"{cid:02d}"
            if term and term not in name.lower() and term not in phone.lower() and term not in code_str.lower():
                continue

            milk_tot, paid_tot, balance = get_customer_balance(cid)
            rate_disp = f"Rs.{def_rate:.2f}/L" if def_rate else "Manual"
            card_text = (
                f"  [{code_str}]  {name}  |  📞 {phone}\n"
                f"  Rate: {rate_disp}  |  Milk: Rs.{milk_tot:.0f}  |  DENA HAI: Rs.{balance:.2f}"
            )
            btn = make_card_button(card_text, height=72, font=13)
            btn.bind(on_press=lambda _, i=cid: self.open_customer_detail(i))
            self.list_layout.add_widget(btn)

        if not self.list_layout.children:
            self.list_layout.add_widget(Label(text="No customers found.", color=(0.3, 0.3, 0.3, 1), size_hint_y=None, height=dp(50)))

    def open_customer_detail(self, cid):
        screen = self.manager.get_screen("customer_detail")
        screen.load_customer(cid)
        self.manager.current = "customer_detail"

    def customer_form(self, customer_id=None):
        editing = customer_id is not None
        existing = None

        if editing:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT code, name, phone, default_rate FROM customers WHERE id=?", (customer_id,))
            existing = cur.fetchone()
            conn.close()

        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(8))
        code_in = make_input("Serial / Code No. (e.g. 01, 02)", existing[0] if existing else "")
        name_in = make_input("Customer Name *", existing[1] if existing else "")
        phone_in = make_input("Mobile Number", existing[2] if existing else "")
        rate_in = make_input("Default Rate per Litre (Optional)", existing[3] if existing and existing[3] else "", numeric=True)

        box.add_widget(code_in)
        box.add_widget(name_in)
        box.add_widget(phone_in)
        box.add_widget(rate_in)

        save = make_button("SAVE CUSTOMER", 50, 16, bg_color=(0.18, 0.55, 0.34, 1))
        box.add_widget(save)

        if editing:
            delete = make_button("DELETE CUSTOMER", 46, 14, bg_color=(0.8, 0.2, 0.2, 1))
            box.add_widget(delete)

        popup = Popup(title="Edit Customer" if editing else "Add New Customer", content=box, size_hint=(0.92, 0.65))

        def save_cust(_):
            name = name_in.text.strip()
            code = code_in.text.strip()
            phone = phone_in.text.strip()
            if not name:
                show_message("Required", "Customer name required hai.")
                return

            rate = parse_positive_float(rate_in.text) if rate_in.text.strip() else None

            conn = get_db()
            cur = conn.cursor()
            if editing:
                cur.execute("UPDATE customers SET code=?, name=?, phone=?, default_rate=? WHERE id=?", (code, name, phone, rate, customer_id))
            else:
                cur.execute("INSERT INTO customers(code, name, phone, default_rate) VALUES(?, ?, ?, ?)", (code, name, phone, rate))
            conn.commit()
            conn.close()

            popup.dismiss()
            self.load_customers()

        save.bind(on_press=save_cust)

        if editing:
            def do_delete():
                conn = get_db()
                cur = conn.cursor()
                cur.execute("DELETE FROM customers WHERE id=?", (customer_id,))
                conn.commit()
                conn.close()
                popup.dismiss()
                self.load_customers()
                self.manager.current = "customers"

            delete.bind(on_press=lambda _: confirm_action("Delete Customer", "Customer aur saara record delete hoga.\nSure?", do_delete))

        popup.open()


class CustomerDetailScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = None
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = make_button("< Back", 44, 14, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "customers"))
        top.add_widget(back)

        self.title_lbl = Label(text="Customer Khata", font_size=dp(18), bold=True, color=(0.1, 0.3, 0.1, 1))
        top.add_widget(self.title_lbl)

        edit = make_button("Edit", 44, 13, bg_color=(0.3, 0.5, 0.4, 1))
        edit.size_hint_x = None
        edit.width = dp(60)
        edit.bind(on_press=lambda _: self.manager.get_screen("customers").customer_form(self.customer_id))
        top.add_widget(edit)
        layout.add_widget(top)

        self.summary_card = Label(text="", font_size=dp(13), size_hint_y=None, height=dp(72), color=(0.1, 0.2, 0.1, 1))
        layout.add_widget(self.summary_card)

        actions = GridLayout(cols=3, size_hint_y=None, height=dp(52), spacing=dp(6))
        m = make_button("+ Morning", 50, 13, bg_color=(0.90, 0.55, 0.10, 1))
        e = make_button("+ Evening", 50, 13, bg_color=(0.20, 0.35, 0.60, 1))
        p = make_button("+ Jama/Pay", 50, 13, bg_color=(0.18, 0.55, 0.34, 1))
        m.bind(on_press=lambda _: self.entry_popup("Morning"))
        e.bind(on_press=lambda _: self.entry_popup("Evening"))
        p.bind(on_press=lambda _: self.payment_popup())
        actions.add_widget(m)
        actions.add_widget(e)
        actions.add_widget(p)
        layout.add_widget(actions)

        layout.add_widget(Label(text="TRANSACTION HISTORY", font_size=dp(13), bold=True, color=(0.2, 0.4, 0.2, 1), size_hint_y=None, height=dp(25)))
        scroll = ScrollView()
        self.history_grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.history_grid.bind(minimum_height=self.history_grid.setter("height"))
        scroll.add_widget(self.history_grid)
        layout.add_widget(scroll)

        self.add_widget(layout)

    def load_customer(self, cid):
        self.customer_id = cid
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT code, name, phone, default_rate FROM customers WHERE id=?", (cid,))
        customer = cur.fetchone()

        cur.execute("SELECT id, entry_date, session, litres, rate, amount FROM milk_entries WHERE customer_id=? ORDER BY entry_date DESC, id DESC LIMIT 150", (cid,))
        milk = cur.fetchall()

        cur.execute("SELECT id, payment_date, amount, note FROM payments WHERE customer_id=? ORDER BY payment_date DESC, id DESC LIMIT 150", (cid,))
        payments = cur.fetchall()
        conn.close()

        if not customer:
            return

        code_str, name, phone, def_rate = customer
        self.title_lbl.text = f"[{code_str or cid}] {name}"
        milk_tot, paid_tot, balance = get_customer_balance(cid)

        self.summary_card.text = (
            f"Phone: {phone or 'N/A'} | Default Rate: Rs.{def_rate or 0:.2f}\n"
            f"Total Milk: Rs.{milk_tot:.2f} | Total Paid: Rs.{paid_tot:.2f}\n"
            f"DENA HAI: Rs.{balance:.2f}"
        )

        self.history_grid.clear_widgets()
        events = [("milk", r) for r in milk] + [("payment", r) for r in payments]
        events.sort(key=lambda x: (x[1][1], x[1][0]), reverse=True)

        for typ, row in events:
            if typ == "milk":
                eid, edate, session, litres, rate, amount = row
                row_box = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(3))
                row_box.add_widget(Label(
                    text=f"{format_date(edate)} | {session} | {litres:.2f}L x Rs.{rate:.2f} = Rs.{amount:.2f}",
                    color=(0.1, 0.2, 0.1, 1),
                    font_size=dp(12)
                ))
                del_btn = make_button("X", 40, 11, bg_color=(0.8, 0.3, 0.3, 1))
                del_btn.size_hint_x = None
                del_btn.width = dp(38)
                del_btn.bind(on_press=lambda _, i=eid: self.delete_entry("milk_entries", i))
                row_box.add_widget(del_btn)
                self.history_grid.add_widget(row_box)
            else:
                pid, pdate, amount, note = row
                row_box = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(3))
                row_box.add_widget(Label(
                    text=f"{format_date(pdate)} | JAMA / PAYMENT | Rs.{amount:.2f} ({note})",
                    color=(0.1, 0.4, 0.1, 1),
                    font_size=dp(12),
                    bold=True
                ))
                del_btn = make_button("X", 40, 11, bg_color=(0.8, 0.3, 0.3, 1))
                del_btn.size_hint_x = None
                del_btn.width = dp(38)
                del_btn.bind(on_press=lambda _, i=pid: self.delete_entry("payments", i))
                row_box.add_widget(del_btn)
                self.history_grid.add_widget(row_box)

    def delete_entry(self, table, entry_id):
        def do_del():
            conn = get_db()
            conn.execute(f"DELETE FROM {table} WHERE id=?", (entry_id,))
            conn.commit()
            conn.close()
            self.load_customer(self.customer_id)

        confirm_action("Delete Record", "Yeh entry delete karni hai?", do_del)

    def entry_popup(self, session):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        date_in = make_input("Date YYYY-MM-DD", date.today().isoformat())
        litres_in = make_input("Litres *", "", numeric=True)

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT default_rate FROM customers WHERE id=?", (self.customer_id,))
        dr = cur.fetchone()[0]
        conn.close()

        rate_in = make_input("Rate *", str(dr) if dr else "", numeric=True)
        box.add_widget(date_in)
        box.add_widget(litres_in)
        box.add_widget(rate_in)

        save = make_button("SAVE", 48, 15, bg_color=(0.18, 0.55, 0.34, 1))
        box.add_widget(save)
        popup = Popup(title=f"Add {session} Milk", content=box, size_hint=(0.9, 0.56))

        def save_m(_):
            l = parse_positive_float(litres_in.text)
            r = parse_positive_float(rate_in.text)
            edate = date_in.text.strip()
            if not l or not r:
                return

            conn = get_db()
            conn.execute("""
                INSERT OR REPLACE INTO milk_entries (customer_id, entry_date, session, litres, rate, amount)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (self.customer_id, edate, session, l, r, l * r))
            conn.commit()
            conn.close()
            popup.dismiss()
            self.load_customer(self.customer_id)

        save.bind(on_press=save_m)
        popup.open()

    def payment_popup(self):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        date_in = make_input("Date YYYY-MM-DD", date.today().isoformat())
        amt_in = make_input("Amount (Rs.) *", "", numeric=True)
        note_in = make_input("Note (Optional)")
        box.add_widget(date_in)
        box.add_widget(amt_in)
        box.add_widget(note_in)

        save = make_button("SAVE PAYMENT", 48, 15, bg_color=(0.18, 0.55, 0.34, 1))
        box.add_widget(save)
        popup = Popup(title="Jama / Payment Entry", content=box, size_hint=(0.9, 0.56))

        def save_p(_):
            amt = parse_positive_float(amt_in.text)
            pdate = date_in.text.strip()
            if not amt:
                return

            conn = get_db()
            conn.execute("INSERT INTO payments(customer_id, payment_date, amount, note) VALUES(?, ?, ?, ?)",
                         (self.customer_id, pdate, amt, note_in.text.strip()))
            conn.commit()
            conn.close()
            popup.dismiss()
            self.load_customer(self.customer_id)

        save.bind(on_press=save_p)
        popup.open()


class ScanRegisterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.row_inputs = []

        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = make_button("< Back", 44, 14, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="AI Register Scanner", font_size=dp(18), bold=True, color=(0.1, 0.3, 0.1, 1)))
        layout.add_widget(top)

        btns = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        pick = make_button("Select Image", 46, 14, bg_color=(0.20, 0.50, 0.40, 1))
        pick.bind(on_press=lambda _: self.open_file_chooser())
        save_db = make_button("Save to DB", 46, 14, bg_color=(0.18, 0.55, 0.34, 1))
        save_db.bind(on_press=lambda _: self.save_scanned_to_db())
        btns.add_widget(pick)
        btns.add_widget(save_db)
        layout.add_widget(btns)

        cbox = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        cbox.add_widget(Label(text="Assign Customer:", size_hint_x=0.4, color=(0.1, 0.2, 0.1, 1)))
        self.cust_spinner = Spinner(text="Select Customer", values=[], size_hint_x=0.6)
        cbox.add_widget(self.cust_spinner)
        layout.add_widget(cbox)

        self.status_lbl = Label(text="Select dairy hisaab photo to scan", font_size=dp(13), color=(0.2, 0.4, 0.2, 1), size_hint_y=None, height=dp(28))
        layout.add_widget(self.status_lbl)

        hd = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(2))
        for h in ["Date", "M-Qty", "M-Rate", "E-Qty", "E-Rate"]:
            hd.add_widget(Label(text=f"[b]{h}[/b]", markup=True, color=(0.1, 0.3, 0.1, 1), font_size=dp(12)))
        layout.add_widget(hd)

        scroll = ScrollView()
        self.table_grid = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.table_grid.bind(minimum_height=self.table_grid.setter("height"))
        scroll.add_widget(self.table_grid)
        layout.add_widget(scroll)

        self.add_widget(layout)

    def on_pre_enter(self):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name FROM customers ORDER BY CAST(code AS INTEGER), id")
        rows = cur.fetchall()
        conn.close()
        self.cust_map = {f"[{code or cid}] {name}": cid for cid, code, name in rows}
        self.cust_spinner.values = list(self.cust_map.keys()) if self.cust_map else ["No Customers"]

    def open_file_chooser(self):
        box = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        chooser = FileChooserIconView(filters=["*.jpg", "*.jpeg", "*.png", "*.webp"])
        box.add_widget(chooser)

        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        c = make_button("CANCEL", 44, 14, bg_color=(0.5, 0.5, 0.5, 1))
        ok = make_button("SCAN PHOTO", 44, 14, bg_color=(0.18, 0.55, 0.34, 1))
        btns.add_widget(c)
        btns.add_widget(ok)
        box.add_widget(btns)

        popup = Popup(title="Choose Register Photo", content=box, size_hint=(0.95, 0.9))
        c.bind(on_press=popup.dismiss)

        def do_scan(_):
            if chooser.selection:
                path = chooser.selection[0]
                popup.dismiss()
                self.status_lbl.text = "Google AI se Scan chal raha hai... Kripya rukein."
                threading.Thread(target=self._scan_thread, args=(path,)).start()

        ok.bind(on_press=do_scan)
        popup.open()

    def _scan_thread(self, image_path):
        if not AI_SCANNER_AVAILABLE:
            Clock.schedule_once(lambda dt: show_message("Error", "dairy_ai_scanner.py file nahi mili."))
            return
        records = scan_dairy_register(image_path)
        Clock.schedule_once(lambda dt: self.populate_scanned(records))

    def populate_scanned(self, records):
        self.table_grid.clear_widgets()
        self.row_inputs = []

        if not records:
            self.status_lbl.text = "Koi text recognize nahi hua."
            return

        self.status_lbl.text = f"Total {len(records)} entries mili! (Red = Overwritten/Doubtful)"

        for row in records:
            doubtful = row.get("doubtful_fields", [])
            row_box = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(2))

            def field(val, name):
                ti = TextInput(text=str(val or ""), multiline=False, font_size=dp(12))
                if name in doubtful:
                    ti.background_color = (1.0, 0.65, 0.65, 1.0)
                return ti

            d = field(row.get("date", ""), "date")
            mq = field(row.get("morning_qty", ""), "morning_qty")
            mr = field(row.get("morning_rate", ""), "morning_rate")
            eq = field(row.get("evening_qty", ""), "evening_qty")
            er = field(row.get("evening_rate", ""), "evening_rate")

            row_box.add_widget(d)
            row_box.add_widget(mq)
            row_box.add_widget(mr)
            row_box.add_widget(eq)
            row_box.add_widget(er)

            self.row_inputs.append((d, mq, mr, eq, er))
            self.table_grid.add_widget(row_box)

    def save_scanned_to_db(self):
        sel = self.cust_spinner.text
        if sel not in self.cust_map:
            show_message("Select Customer", "Pehle customer chunein.")
            return

        cid = self.cust_map[sel]
        conn = get_db()
        cur = conn.cursor()
        saved = 0

        for d, mq, mr, eq, er in self.row_inputs:
            raw_d = d.text.strip()
            try:
                if "/" in raw_d:
                    p = raw_d.split("/")
                    edate = f"{date.today().year}-{int(p[1]):02d}-{int(p[0]):02d}"
                else:
                    edate = raw_d
            except Exception:
                edate = date.today().isoformat()

            m_lit = parse_positive_float(mq.text)
            m_rat = parse_positive_float(mr.text)
            if m_lit and m_rat:
                cur.execute("""
                    INSERT OR REPLACE INTO milk_entries(customer_id, entry_date, session, litres, rate, amount)
                    VALUES(?, ?, 'Morning', ?, ?, ?)
                """, (cid, edate, m_lit, m_rat, m_lit * m_rat))
                saved += 1

            e_lit = parse_positive_float(eq.text)
            e_rat = parse_positive_float(er.text)
            if e_lit and e_rat:
                cur.execute("""
                    INSERT OR REPLACE INTO milk_entries(customer_id, entry_date, session, litres, rate, amount)
                    VALUES(?, ?, 'Evening', ?, ?, ?)
                """, (cid, edate, e_lit, e_rat, e_lit * e_rat))
                saved += 1

        conn.commit()
        conn.close()
        show_message("Saved", f"{saved} entries successfully save ho gayi!")


class TodayMilkScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = make_button("< Back", 44, 14, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="Today's Milk Entries", font_size=dp(18), bold=True, color=(0.1, 0.3, 0.1, 1)))
        layout.add_widget(top)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)

        self.add_widget(layout)

    def on_pre_enter(self):
        self.list_layout.clear_widgets()
        today = date.today().isoformat()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT c.code, c.name, m.session, m.litres, m.rate, m.amount
            FROM milk_entries m
            JOIN customers c ON m.customer_id=c.id
            WHERE m.entry_date=?
            ORDER BY m.id DESC
        """, (today,))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            self.list_layout.add_widget(Label(text="Aaj ki koi entry nahi mili.", color=(0.3, 0.3, 0.3, 1), size_hint_y=None, height=dp(50)))
            return

        tot_amt = 0
        tot_l = 0
        for code, name, session, l, r, amt in rows:
            tot_amt += amt
            tot_l += l
            card = f"  [{code or '-'}]  {name}  |  {session}\n  {l:.2f} L  x  Rs.{r:.2f}  =  Rs.{amt:.2f}"
            self.list_layout.add_widget(make_card_button(card, height=58, font=13))

        self.list_layout.add_widget(Label(
            text=f"TOTAL: {tot_l:.2f} L | Rs. {tot_amt:.2f}",
            bold=True, font_size=dp(15), color=(0.1, 0.3, 0.1, 1),
            size_hint_y=None, height=dp(45)
        ))


class ReportsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.year = date.today().year
        self.month = date.today().month

        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = make_button("< Back", 44, 14, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        self.month_lbl = Label(text=month_title(self.year, self.month), font_size=dp(17), bold=True, color=(0.1, 0.3, 0.1, 1))
        top.add_widget(self.month_lbl)
        layout.add_widget(top)

        scroll = ScrollView()
        self.report_list = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.report_list.bind(minimum_height=self.report_list.setter("height"))
        scroll.add_widget(self.report_list)
        layout.add_widget(scroll)

        self.add_widget(layout)

    def on_pre_enter(self):
        self.report_list.clear_widgets()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, code, name FROM customers ORDER BY CAST(code AS INTEGER), id")
        custs = cur.fetchall()
        conn.close()

        for cid, code, name in custs:
            d = get_customer_month_data(cid, self.year, self.month)
            card = (
                f"  [{code or cid}] {name}\n"
                f"  Prev: Rs.{d['previous_due']:.0f} | Milk: Rs.{d['current_amount']:.0f} | Paid: Rs.{d['current_paid']:.0f} | DENA: Rs.{d['total_due']:.0f}"
            )
            btn = make_card_button(card, height=64, font=13)
            btn.bind(on_press=lambda _, i=cid: self.open_khata(i))
            self.report_list.add_widget(btn)

    def open_khata(self, cid):
        screen = self.manager.get_screen("customer_detail")
        screen.load_customer(cid)
        self.manager.current = "customer_detail"


# ============================================================
# MAIN APP CLASS
# ============================================================

class NilgiriDairyApp(App):
    title = APP_NAME

    def on_start(self):
        try:
            Window.clearcolor = (0.94, 0.97, 0.95, 1.0)
        except Exception:
            pass

    def build(self):
        init_db()
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(DailyEntryScreen(name="daily_entry"))
        sm.add_widget(CustomersScreen(name="customers"))
        sm.add_widget(CustomerDetailScreen(name="customer_detail"))
        sm.add_widget(ScanRegisterScreen(name="scan_register"))
        sm.add_widget(TodayMilkScreen(name="today"))
        sm.add_widget(ReportsScreen(name="reports"))
        return sm


if __name__ == "__main__":
    NilgiriDairyApp().run()
