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
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

try:
    from androidstorage4kivy import SharedStorage, ShareSheet
    ANDROID_STORAGE_AVAILABLE = True
except Exception:
    ANDROID_STORAGE_AVAILABLE = False

APP_NAME = "Nilgiri Dairy App"


# ============================================================
# DATABASE SETUP (Crash-Safe)
# ============================================================

def get_db_path():
    try:
        app = App.get_running_app()
        if app and getattr(app, "user_data_dir", None):
            return os.path.join(app.user_data_dir, "dairy_v2.db")
    except Exception:
        pass
    return "dairy_v2.db"


def get_db():
    conn = sqlite3.connect(get_db_path(), timeout=10)
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
    except Exception:
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

        try:
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
        except Exception:
            customers = []
            entries = {}

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

            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO milk_entries (customer_id, entry_date, session, litres, rate, amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (cid, self.current_date, self.session, l, r, l * r))
                conn.commit()
                conn.close()
            except Exception as exc:
                print(f"Save error: {exc}")

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
        search_term = self.search_in.text.strip().lower()

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, code, name, phone, default_rate FROM customers ORDER BY CAST(code AS INTEGER), id")
            rows = cur.fetchall()
            conn.close()
        except Exception:
            rows = []

        if not rows:
            self.list_layout.add_widget(Label(
                text="No customers yet. Tap '+ Add' to create one.",
                font_size=dp(13), size_hint_y=None, height=dp(50)
            ))
            return

        for cid, code, name, phone, rate in rows:
            code_str = str(code) if code else f"{cid:02d}"
            if search_term and search_term not in name.lower() and search_term not in code_str.lower():
                continue

            milk, paid, due = get_customer_balance(cid)
            rate_disp = f"Rs.{rate:.2f}" if rate else "N/A"
            card_text = f"  [{code_str}]  {name}\n  Phone: {phone or '-'}  |  Rate: {rate_disp}  |  Due: Rs.{due:.2f}"
            btn = make_card_button(card_text, height=64, font=13)
            btn.background_color = (1.0, 0.92, 0.85, 1) if due > 0 else (0.9, 0.95, 0.9, 1)
            btn.bind(on_press=lambda _, c=cid, n=name, cd=code_str, p=phone, r=rate: self.customer_form(c, n, cd, p, r))
            self.list_layout.add_widget(btn)

    def customer_form(self, cid=None, name="", code="", phone="", rate=None):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        box.add_widget(Label(text="Edit Customer" if cid else "Add Customer", font_size=dp(15), bold=True))

        code_in = make_input("Code (e.g. 01)", code)
        name_in = make_input("Full Name *", name)
        phone_in = make_input("Phone", phone)
        rate_in = make_input("Default Rate (Rs/L)", rate if rate else "", numeric=True)

        box.add_widget(code_in)
        box.add_widget(name_in)
        box.add_widget(phone_in)
        box.add_widget(rate_in)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_cancel = make_button("CANCEL", 42, 13, bg_color=(0.5, 0.5, 0.5, 1))
        btn_save = make_button("SAVE", 42, 13, bg_color=(0.18, 0.55, 0.34, 1))
        btns.add_widget(btn_cancel)
        btns.add_widget(btn_save)
        box.add_widget(btns)

        btn_delete = None
        if cid:
            btn_delete = make_button("DELETE CUSTOMER", 40, 12, bg_color=(0.75, 0.15, 0.15, 1))
            box.add_widget(btn_delete)

        popup = Popup(title="Customer", content=box, size_hint=(0.9, 0.68 if cid else 0.58))
        btn_cancel.bind(on_press=popup.dismiss)

        def save_customer(_):
            nm = name_in.text.strip()
            if not nm:
                show_message("Error", "Name is required.")
                return
            cd = code_in.text.strip()
            ph = phone_in.text.strip()
            rt = parse_positive_float(rate_in.text)

            try:
                conn = get_db()
                cur = conn.cursor()
                if cid:
                    cur.execute("UPDATE customers SET code=?, name=?, phone=?, default_rate=? WHERE id=?", (cd, nm, ph, rt, cid))
                else:
                    cur.execute("INSERT INTO customers (code, name, phone, default_rate) VALUES (?, ?, ?, ?)", (cd, nm, ph, rt))
                conn.commit()
                conn.close()
            except Exception as e:
                show_message("Error", f"Could not save: {e}")
                return
            popup.dismiss()
            self.load_customers()

        btn_save.bind(on_press=save_customer)

        if cid and btn_delete:
            def delete_customer(_):
                confirm_box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
                confirm_box.add_widget(Label(
                    text=f"Delete {name}?\nThis will remove all their milk & payment records.",
                    font_size=dp(13)
                ))
                cbtns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
                cb_no = make_button("NO", 42, 13, bg_color=(0.5, 0.5, 0.5, 1))
                cb_yes = make_button("YES, DELETE", 42, 13, bg_color=(0.75, 0.15, 0.15, 1))
                cbtns.add_widget(cb_no)
                cbtns.add_widget(cb_yes)
                confirm_box.add_widget(cbtns)
                confirm_popup = Popup(title="Confirm Delete", content=confirm_box, size_hint=(0.85, 0.4))
                cb_no.bind(on_press=confirm_popup.dismiss)

                def do_delete(_):
                    try:
                        conn = get_db()
                        cur = conn.cursor()
                        cur.execute("DELETE FROM customers WHERE id=?", (cid,))
                        conn.commit()
                        conn.close()
                    except Exception as exc:
                        print(f"Delete error: {exc}")
                    confirm_popup.dismiss()
                    popup.dismiss()
                    self.load_customers()

                cb_yes.bind(on_press=do_delete)
                confirm_popup.open()

            btn_delete.bind(on_press=delete_customer)

        popup.open()


class TodayScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text=f"Today's Milk ({format_date(date.today().isoformat())})",
                              font_size=dp(15), bold=True, color=(0.1, 0.3, 0.1, 1)))
        layout.add_widget(top)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)

        self.summary_bar = Button(
            text="Total: 0.00 L | Rs. 0.00",
            font_size=dp(14), bold=True, size_hint_y=None, height=dp(38),
            background_normal='', background_color=(0.12, 0.37, 0.23, 1), color=(1, 1, 1, 1)
        )
        layout.add_widget(self.summary_bar)
        self.add_widget(layout)

    def on_pre_enter(self):
        self.load_today()

    def load_today(self):
        self.list_layout.clear_widgets()
        today = date.today().isoformat()

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, code, name FROM customers ORDER BY CAST(code AS INTEGER), id")
            customers = cur.fetchall()
            cur.execute("SELECT customer_id, session, litres, amount FROM milk_entries WHERE entry_date=?", (today,))
            rows = cur.fetchall()
            conn.close()
        except Exception:
            customers, rows = [], []

        data = {}
        for cid, session, litres, amount in rows:
            data.setdefault(cid, {})[session] = (litres, amount)

        total_litres = 0.0
        total_amount = 0.0
        any_entries = False

        for cid, code, name in customers:
            sess = data.get(cid, {})
            m = sess.get("Morning")
            e = sess.get("Evening")
            if not m and not e:
                continue

            any_entries = True
            code_str = str(code) if code else f"{cid:02d}"
            parts = []
            day_litres = 0.0
            day_amount = 0.0
            if m:
                parts.append(f"AM: {m[0]:.2f}L")
                day_litres += m[0]
                day_amount += m[1]
            if e:
                parts.append(f"PM: {e[0]:.2f}L")
                day_litres += e[0]
                day_amount += e[1]

            total_litres += day_litres
            total_amount += day_amount

            card_text = f"  [{code_str}]  {name}\n  {'  |  '.join(parts)}  |  Rs.{day_amount:.2f}"
            btn = make_card_button(card_text, height=58, font=13)
            btn.background_color = (0.9, 0.95, 0.9, 1)
            self.list_layout.add_widget(btn)

        if not any_entries:
            self.list_layout.add_widget(Label(
                text="No milk entries recorded today yet.",
                font_size=dp(13), size_hint_y=None, height=dp(50)
            ))

        self.summary_bar.text = f"Today Total: {total_litres:.2f} L | Rs.{total_amount:.2f}"


class ReportsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_customer = None
        self.year = date.today().year
        self.month = date.today().month

        self.layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: self.go_back())
        top.add_widget(back)
        self.title_lbl = Label(text="Reports & Khata", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1))
        top.add_widget(self.title_lbl)
        self.layout.add_widget(top)

        self.search_in = TextInput(hint_text="🔍 Search Customer...", multiline=False, font_size=dp(15), size_hint_y=None, height=dp(44))
        self.search_in.bind(text=lambda *_: self.load_customer_list())
        self.layout.add_widget(self.search_in)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        self.layout.add_widget(scroll)

        self.add_widget(self.layout)

    def go_back(self):
        if self.selected_customer:
            self.selected_customer = None
            self.on_pre_enter()
        else:
            self.manager.current = "home"

    def on_pre_enter(self):
        self.selected_customer = None
        self.title_lbl.text = "Reports & Khata"
        self.search_in.disabled = False
        self.search_in.text = ""
        self.load_customer_list()

    def load_customer_list(self):
        self.list_layout.clear_widgets()
        search_term = self.search_in.text.strip().lower()

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, code, name FROM customers ORDER BY CAST(code AS INTEGER), id")
            customers = cur.fetchall()
            conn.close()
        except Exception:
            customers = []

        if not customers:
            self.list_layout.add_widget(Label(
                text="No customers yet.", font_size=dp(13), size_hint_y=None, height=dp(50)
            ))
            return

        for cid, code, name in customers:
            code_str = str(code) if code else f"{cid:02d}"
            if search_term and search_term not in name.lower() and search_term not in code_str.lower():
                continue
            milk, paid, due = get_customer_balance(cid)
            card_text = f"  [{code_str}]  {name}\n  Total Due: Rs.{due:.2f}"
            btn = make_card_button(card_text, height=58, font=13)
            btn.background_color = (1.0, 0.9, 0.85, 1) if due > 0 else (0.9, 0.95, 0.9, 1)
            btn.bind(on_press=lambda _, c=cid, n=name: self.open_customer_report(c, n))
            self.list_layout.add_widget(btn)

    def open_customer_report(self, cid, name):
        self.selected_customer = cid
        self.title_lbl.text = name
        self.search_in.disabled = True
        self.year, self.month = date.today().year, date.today().month
        self.render_month_report(cid, name)

    def render_month_report(self, cid, name):
        self.list_layout.clear_widgets()

        nav = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_prev = make_button("< Prev", 40, 13, bg_color=(0.3, 0.4, 0.5, 1))
        month_lbl = Label(text=month_title(self.year, self.month), font_size=dp(14), bold=True)
        btn_next = make_button("Next >", 40, 13, bg_color=(0.3, 0.4, 0.5, 1))
        nav.add_widget(btn_prev)
        nav.add_widget(month_lbl)
        nav.add_widget(btn_next)
        self.list_layout.add_widget(nav)

        def go_prev(_):
            self.year, self.month = previous_month(self.year, self.month)
            self.render_month_report(cid, name)

        def go_next(_):
            self.year, self.month = next_month(self.year, self.month)
            self.render_month_report(cid, name)

        btn_prev.bind(on_press=go_prev)
        btn_next.bind(on_press=go_next)

        data = get_customer_month_data(cid, self.year, self.month)

        stats = (
            f"Previous Due: Rs.{data['previous_due']:.2f}\n"
            f"This Month Milk: {data['current_litres']:.2f} L = Rs.{data['current_amount']:.2f}\n"
            f"This Month Paid: Rs.{data['current_paid']:.2f}\n"
            f"TOTAL DUE: Rs.{data['total_due']:.2f}"
        )
        stats_lbl = Label(text=stats, font_size=dp(14), size_hint_y=None, height=dp(100),
                           halign='left', valign='top')
        stats_lbl.bind(size=lambda w, s: setattr(w, 'text_size', (w.width, None)))
        self.list_layout.add_widget(stats_lbl)

        btn_payment = make_button("+ Add Payment", 44, 13, bg_color=(0.18, 0.55, 0.34, 1))
        btn_payment.bind(on_press=lambda _: self.add_payment_popup(cid, name))
        self.list_layout.add_widget(btn_payment)

        if XLSX_AVAILABLE or REPORTLAB_AVAILABLE or AI_SCANNER_AVAILABLE:
            btn_export = make_button("Export Report", 44, 13, bg_color=(0.35, 0.45, 0.55, 1))
            btn_export.bind(on_press=lambda _: self.export_report(cid, name))
            self.list_layout.add_widget(btn_export)

    def add_payment_popup(self, cid, name):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        box.add_widget(Label(text=f"Add Payment - {name}", font_size=dp(15), bold=True))
        amt_in = make_input("Amount *", numeric=True)
        note_in = make_input("Note (optional)")
        box.add_widget(amt_in)
        box.add_widget(note_in)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_cancel = make_button("CANCEL", 42, 13, bg_color=(0.5, 0.5, 0.5, 1))
        btn_save = make_button("SAVE", 42, 13, bg_color=(0.18, 0.55, 0.34, 1))
        btns.add_widget(btn_cancel)
        btns.add_widget(btn_save)
        box.add_widget(btns)

        popup = Popup(title="Payment", content=box, size_hint=(0.85, 0.45))
        btn_cancel.bind(on_press=popup.dismiss)

        def save_payment(_):
            amt = parse_positive_float(amt_in.text)
            if not amt:
                show_message("Error", "Valid amount daalein.")
                return
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("INSERT INTO payments (customer_id, payment_date, amount, note) VALUES (?, ?, ?, ?)",
                            (cid, date.today().isoformat(), amt, note_in.text.strip()))
                conn.commit()
                conn.close()
            except Exception as exc:
                show_message("Error", f"Could not save payment: {exc}")
                return
            popup.dismiss()
            self.render_month_report(cid, name)

        btn_save.bind(on_press=save_payment)
        popup.open()

    def export_report(self, cid, name):
        # Placeholder: hook up export_to_excel / export_to_pdf here once
        # dairy_ai_scanner.py (or a local exporter) is added to the project.
        show_message("Export", "Export feature not wired up yet.\nAdd dairy_ai_scanner.py to enable this.")


class ScanRegisterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="AI Register Scanner", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
        self.layout.add_widget(top)

        if not AI_SCANNER_AVAILABLE:
            self.layout.add_widget(Label(
                text="AI Scanner module not available in this build.\n"
                     "Add 'dairy_ai_scanner.py' to the project to enable this feature.",
                font_size=dp(13)
            ))
        else:
            self.status_lbl = Label(
                text="Select a photo of your paper register to scan.",
                font_size=dp(13), size_hint_y=None, height=dp(60)
            )
            self.layout.add_widget(self.status_lbl)

            self.file_chooser = FileChooserIconView(filters=['*.png', '*.jpg', '*.jpeg'])
            self.layout.add_widget(self.file_chooser)

            btn_scan = make_button("Scan Selected Image", 46, 14, bg_color=(0.80, 0.40, 0.15, 1))
            btn_scan.bind(on_press=self.run_scan)
            self.layout.add_widget(btn_scan)

        self.add_widget(self.layout)

    def run_scan(self, _):
        selection = self.file_chooser.selection
        if not selection:
            show_message("Error", "Pehle ek image select karein.")
            return
        image_path = selection[0]
        self.status_lbl.text = "Scanning... please wait."

        def do_scan():
            try:
                result = scan_dairy_register(image_path)
                msg = f"Scan complete: {result}"
            except Exception as e:
                msg = f"Scan failed: {e}"
            Clock.schedule_once(lambda dt: setattr(self.status_lbl, 'text', msg))

        threading.Thread(target=do_scan, daemon=True).start()


# ============================================================
# APP
# ============================================================

class NilgiriDairyApp(App):
    def build(self):
        self.title = APP_NAME
        self.request_android_permissions()
        init_db()

        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(DailyEntryScreen(name="daily_entry"))
        sm.add_widget(TodayScreen(name="today"))
        sm.add_widget(CustomersScreen(name="customers"))
        sm.add_widget(ReportsScreen(name="reports"))
        sm.add_widget(ScanRegisterScreen(name="scan_register"))
        return sm

    def request_android_permissions(self):
        # On Android 6.0+, declaring permissions in buildozer.spec is not
        # enough - the app must also ask the user at runtime, or features
        # like the file chooser / camera will silently show nothing.
        try:
            from android.permissions import request_permissions, Permission
            perms = [Permission.CAMERA, Permission.WRITE_EXTERNAL_STORAGE]
            try:
                perms.append(Permission.READ_MEDIA_IMAGES)  # Android 13+
            except AttributeError:
                perms.append(Permission.READ_EXTERNAL_STORAGE)  # Older Android
            request_permissions(perms)
        except Exception:
            pass  # Not running on Android (e.g. desktop testing) - ignore


if __name__ == "__main__":
    NilgiriDairyApp().run()
