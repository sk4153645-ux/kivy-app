import os
import sqlite3
from calendar import monthrange
from datetime import date, datetime

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup

APP_NAME = "Dairy Hisaab"

# Optional desktop/Android report libraries.
try:
    from openpyxl import Workbook
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from androidstorage4kivy import SharedStorage, ShareSheet
    ANDROID_STORAGE_AVAILABLE = True
except ImportError:
    ANDROID_STORAGE_AVAILABLE = False


# ============================================================
# DATABASE
# ============================================================

def get_db_path():
    app = App.get_running_app()
    if app:
        return os.path.join(app.user_data_dir, "dairy.db")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "dairy.db")


def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(get_db_path()), exist_ok=True)
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_milk_customer_date
        ON milk_entries(customer_id, entry_date)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_payment_customer_date
        ON payments(customer_id, payment_date)
    """)

    conn.commit()
    conn.close()


# ============================================================
# HELPERS
# ============================================================

def make_button(text, height=52, font=17):
    return Button(text=text, font_size=dp(font), size_hint_y=None, height=dp(height))


def make_input(hint="", value="", numeric=False):
    return TextInput(
        text=str(value) if value is not None else "",
        hint_text=hint,
        multiline=False,
        font_size=dp(17),
        input_filter="float" if numeric else None,
        size_hint_y=None,
        height=dp(50),
    )


def show_message(title, message):
    box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
    box.add_widget(Label(text=message, font_size=dp(16)))
    close = make_button("OK", 50, 17)
    box.add_widget(close)
    popup = Popup(title=title, content=box, size_hint=(0.9, 0.45))
    close.bind(on_press=popup.dismiss)
    popup.open()


def confirm_action(title, message, callback):
    box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
    box.add_widget(Label(text=message, font_size=dp(16)))
    buttons = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(8))
    no = make_button("CANCEL", 50, 15)
    yes = make_button("YES", 50, 15)
    buttons.add_widget(no)
    buttons.add_widget(yes)
    box.add_widget(buttons)
    popup = Popup(title=title, content=box, size_hint=(0.9, 0.42))
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


def valid_phone(phone):
    value = phone.strip().replace(" ", "").replace("-", "")
    if value.startswith("+91"):
        value = value[3:]
    elif value.startswith("91") and len(value) == 12:
        value = value[2:]
    return len(value) == 10 and value.isdigit() and value[0] in "6789"


def normalize_phone(phone):
    value = phone.strip().replace(" ", "").replace("-", "")
    if value.startswith("+91"):
        return value
    if value.startswith("91") and len(value) == 12:
        return "+" + value
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


def period_range(year, month, name):
    last = monthrange(year, month)[1]
    if name == "1-10":
        return 1, min(10, last)
    if name == "11-20":
        return 11, min(20, last)
    return 21, last


def period_dates(year, month, name):
    a, b = period_range(year, month, name)
    return date(year, month, a).isoformat(), date(year, month, b).isoformat()


# ============================================================
# ACCOUNTING
# ============================================================

def get_customer_balance(customer_id, upto_date=None):
    conn = get_db()
    cur = conn.cursor()

    if upto_date:
        cur.execute(
            "SELECT COALESCE(SUM(amount),0) FROM milk_entries "
            "WHERE customer_id=? AND entry_date<=?",
            (customer_id, upto_date),
        )
        milk = cur.fetchone()[0] or 0
        cur.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payments "
            "WHERE customer_id=? AND payment_date<=?",
            (customer_id, upto_date),
        )
        paid = cur.fetchone()[0] or 0
    else:
        cur.execute(
            "SELECT COALESCE(SUM(amount),0) FROM milk_entries WHERE customer_id=?",
            (customer_id,),
        )
        milk = cur.fetchone()[0] or 0
        cur.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payments WHERE customer_id=?",
            (customer_id,),
        )
        paid = cur.fetchone()[0] or 0

    conn.close()
    return milk, paid, milk - paid


def get_customer_month_data(customer_id, year, month):
    start_date, end_date = month_start_end(year, month)
    prev_y, prev_m = previous_month(year, month)
    previous_end = date(prev_y, prev_m, monthrange(prev_y, prev_m)[1]).isoformat()

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COALESCE(SUM(amount),0), COALESCE(SUM(litres),0) "
        "FROM milk_entries WHERE customer_id=? AND entry_date BETWEEN ? AND ?",
        (customer_id, start_date, end_date),
    )
    current_amount, current_litres = cur.fetchone()

    cur.execute(
        "SELECT COALESCE(SUM(amount),0) FROM milk_entries "
        "WHERE customer_id=? AND entry_date<=?",
        (customer_id, previous_end),
    )
    prev_milk = cur.fetchone()[0] or 0

    cur.execute(
        "SELECT COALESCE(SUM(amount),0) FROM payments "
        "WHERE customer_id=? AND payment_date<=?",
        (customer_id, previous_end),
    )
    prev_paid = cur.fetchone()[0] or 0

    cur.execute(
        "SELECT COALESCE(SUM(amount),0) FROM payments "
        "WHERE customer_id=? AND payment_date BETWEEN ? AND ?",
        (customer_id, start_date, end_date),
    )
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


# ============================================================
# EXPORT
# ============================================================

def safe_filename(value):
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    return "".join(c for c in value.replace(" ", "_") if c in allowed) or "report"


def share_or_open_file(path, share=False):
    if ANDROID_STORAGE_AVAILABLE:
        try:
            storage = SharedStorage()
            shared = storage.copy_to_shared(
                path, collection="DOCUMENTS", filepath=os.path.basename(path)
            )
            if shared:
                if share:
                    ShareSheet().share_file(shared)
                else:
                    ShareSheet().view_file(shared)
                return True
        except Exception as exc:
            print("Android file error:", exc)

    try:
        import webbrowser
        webbrowser.open("file://" + path)
        return True
    except Exception:
        return False


def generate_customer_xlsx(customer_id, year, month):
    if not XLSX_AVAILABLE:
        raise RuntimeError("openpyxl installed nahi hai.")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, phone FROM customers WHERE id=?", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        conn.close()
        raise RuntimeError("Customer not found.")

    name, phone = customer
    start_date, end_date = month_start_end(year, month)

    cur.execute("""
        SELECT entry_date, session, litres, rate, amount
        FROM milk_entries
        WHERE customer_id=? AND entry_date BETWEEN ? AND ?
        ORDER BY entry_date, session
    """, (customer_id, start_date, end_date))
    rows = cur.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Milk Hisaab"

    ws.append(["DAIRY HISAAB"])
    ws.append(["Customer", name])
    ws.append(["Mobile", phone])
    ws.append(["Month", month_title(year, month)])
    ws.append([])
    ws.append(["Date", "Morning L", "Morning Rate", "Evening L",
               "Evening Rate", "Day Amount"])

    grouped = {}
    for edate, session, litres, rate, amount in rows:
        grouped.setdefault(edate, {})[session] = (litres, rate, amount)

    total_l = 0
    total_amount = 0

    for edate in sorted(grouped):
        m = grouped[edate].get("Morning")
        e = grouped[edate].get("Evening")
        ml, mr, ma = m if m else (0, 0, 0)
        el, er, ea = e if e else (0, 0, 0)
        day_amount = ma + ea
        total_l += ml + el
        total_amount += day_amount
        ws.append([format_date(edate), ml, mr, el, er, day_amount])

    ws.append([])
    ws.append(["TOTAL", total_l, "", "", "", total_amount])

    for col in ws.columns:
        width = max(len(str(cell.value or "")) for cell in col) + 2
        ws.column_dimensions[col[0].column_letter].width = min(width, 28)

    app = App.get_running_app()
    path = os.path.join(
        app.user_data_dir,
        f"{safe_filename(name)}_{year}_{month:02d}.xlsx"
    )
    wb.save(path)
    return path


def generate_all_customers_xlsx(year, month):
    if not XLSX_AVAILABLE:
        raise RuntimeError("openpyxl installed nahi hai.")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone FROM customers ORDER BY name")
    customers = cur.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "All Customers"
    ws.append(["Customer", "Mobile", "Previous Due",
               "Current Milk Amount", "Paid This Month", "Total Due"])

    for cid, name, phone in customers:
        d = get_customer_month_data(cid, year, month)
        ws.append([
            name, phone, d["previous_due"], d["current_amount"],
            d["current_paid"], d["total_due"]
        ])

    for col in ws.columns:
        width = max(len(str(cell.value or "")) for cell in col) + 2
        ws.column_dimensions[col[0].column_letter].width = min(width, 28)

    app = App.get_running_app()
    path = os.path.join(
        app.user_data_dir, f"All_Customers_{year}_{month:02d}.xlsx"
    )
    wb.save(path)
    return path


def generate_customer_pdf(customer_id, year, month):
    if not PDF_AVAILABLE:
        raise RuntimeError("reportlab installed nahi hai.")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, phone FROM customers WHERE id=?", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        conn.close()
        raise RuntimeError("Customer not found.")

    name, phone = customer
    start_date, end_date = month_start_end(year, month)
    cur.execute("""
        SELECT entry_date, session, litres, rate, amount
        FROM milk_entries
        WHERE customer_id=? AND entry_date BETWEEN ? AND ?
        ORDER BY entry_date, session
    """, (customer_id, start_date, end_date))
    rows = cur.fetchall()
    conn.close()

    data = get_customer_month_data(customer_id, year, month)
    app = App.get_running_app()
    path = os.path.join(
        app.user_data_dir, f"{safe_filename(name)}_{year}_{month:02d}.pdf"
    )

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        path, pagesize=landscape(A4),
        rightMargin=8*mm, leftMargin=8*mm,
        topMargin=8*mm, bottomMargin=8*mm
    )

    story = [
        Paragraph("<b>DAIRY HISAAB</b>", styles["Title"]),
        Paragraph(
            f"<b>Customer:</b> {name} | <b>Mobile:</b> {phone} | "
            f"<b>Month:</b> {month_title(year, month)}",
            styles["Normal"]
        ),
        Spacer(1, 8)
    ]

    table_data = [["Date", "Morning L", "Morning Rate",
                   "Evening L", "Evening Rate", "Day Amount"]]
    grouped = {}

    for edate, session, litres, rate, amount in rows:
        grouped.setdefault(edate, {})[session] = (litres, rate, amount)

    for edate in sorted(grouped):
        m = grouped[edate].get("Morning")
        e = grouped[edate].get("Evening")
        ml, mr, ma = m if m else (0, 0, 0)
        el, er, ea = e if e else (0, 0, 0)
        table_data.append([
            format_date(edate), f"{ml:.2f}", f"Rs. {mr:.2f}",
            f"{el:.2f}", f"Rs. {er:.2f}", f"Rs. {ma+ea:.2f}"
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D32")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(table)
    story.append(Spacer(1, 10))

    summary = [
        ["Previous Due", f"Rs. {data['previous_due']:.2f}"],
        ["Current Milk", f"{data['current_litres']:.2f} L"],
        ["Current Amount", f"Rs. {data['current_amount']:.2f}"],
        ["Paid This Month", f"Rs. {data['current_paid']:.2f}"],
        ["TOTAL DENA HAI", f"Rs. {data['total_due']:.2f}"],
    ]
    st = Table(summary, colWidths=[55*mm, 55*mm])
    st.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ]))
    story.append(st)
    doc.build(story)
    return path


# ============================================================
# HOME
# ============================================================

class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        box = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        box.add_widget(Label(text="DAIRY HISAAB", font_size=dp(28),
                             bold=True, size_hint_y=None, height=dp(70)))

        for text, target in [
            ("CUSTOMERS", "customers"),
            ("TODAY'S MILK", "today"),
            ("REPORTS", "reports"),
        ]:
            b = make_button(text, 65, 20)
            b.bind(on_press=lambda _, t=target: setattr(self.manager, "current", t))
            box.add_widget(b)

        self.add_widget(box)


# ============================================================
# CUSTOMERS
# ============================================================

class CustomersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(5))
        back = make_button("< Back", 48, 14)
        back.size_hint_x = None
        back.width = dp(80)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="CUSTOMERS", font_size=dp(20), bold=True))
        add = make_button("+ Add", 48, 14)
        add.size_hint_x = None
        add.width = dp(82)
        add.bind(on_press=lambda _: self.customer_form())
        top.add_widget(add)
        self.layout.add_widget(top)

        self.search = TextInput(
            hint_text="Search name or mobile", multiline=False,
            font_size=dp(17), size_hint_y=None, height=dp(48)
        )
        self.search.bind(text=lambda *_: self.load_customers())
        self.layout.add_widget(self.search)

        scroll = ScrollView()
        self.customer_list = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.customer_list.bind(minimum_height=self.customer_list.setter("height"))
        scroll.add_widget(self.customer_list)
        self.layout.add_widget(scroll)
        self.add_widget(self.layout)

    def on_pre_enter(self):
        self.load_customers()

    def load_customers(self):
        self.customer_list.clear_widgets()
        term = self.search.text.strip().lower()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.name, c.phone, c.default_rate,
                   COALESCE(SUM(m.amount),0)
            FROM customers c
            LEFT JOIN milk_entries m ON c.id=m.customer_id
            GROUP BY c.id
            ORDER BY c.name
        """)
        rows = cur.fetchall()
        conn.close()

        for cid, name, phone, rate, milk_total in rows:
            if term and term not in name.lower() and term not in phone.lower():
                continue

            _, _, balance = get_customer_balance(cid)
            rate_text = f"Rs. {rate:.2f}/L" if rate is not None else "Manual"
            text = (
                f"{name} | {phone}\n"
                f"Rate: {rate_text} | Milk: Rs. {milk_total:.2f} | "
                f"Dena: Rs. {balance:.2f}"
            )
            b = make_button(text, 76, 13)
            b.bind(on_press=lambda _, i=cid: self.open_customer(i))
            self.customer_list.add_widget(b)

        if not self.customer_list.children:
            self.customer_list.add_widget(
                Label(text="No customers found.", font_size=dp(17),
                      size_hint_y=None, height=dp(55))
            )

    def open_customer(self, cid):
        screen = self.manager.get_screen("customer_detail")
        screen.load_customer(cid)
        self.manager.current = "customer_detail"

    def customer_form(self, customer_id=None):
        editing = customer_id is not None
        existing = None

        if editing:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT name, phone, default_rate FROM customers WHERE id=?",
                (customer_id,)
            )
            existing = cur.fetchone()
            conn.close()

        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(7))
        name_in = make_input("Name *", existing[0] if existing else "")
        phone_in = make_input("Mobile Number *", existing[1] if existing else "")
        rate_in = make_input(
            "Default Rate (Optional)",
            existing[2] if existing and existing[2] is not None else "",
            numeric=True
        )
        box.add_widget(name_in)
        box.add_widget(phone_in)
        box.add_widget(rate_in)

        save = make_button("SAVE", 52, 17)
        box.add_widget(save)

        if editing:
            delete = make_button("DELETE CUSTOMER", 48, 14)
            box.add_widget(delete)

        popup = Popup(
            title="Edit Customer" if editing else "Add Customer",
            content=box, size_hint=(0.92, 0.62)
        )

        def save_customer(_):
            name = name_in.text.strip()
            phone = normalize_phone(phone_in.text)
            if not name:
                show_message("Required", "Customer name required hai.")
                return
            if not valid_phone(phone):
                show_message("Invalid Mobile", "Valid 10 digit Indian mobile number enter karein.")
                return

            rate = None
            if rate_in.text.strip():
                rate = parse_positive_float(rate_in.text)
                if rate is None:
                    show_message("Invalid Rate", "Rate valid positive number hona chahiye.")
                    return

            conn = get_db()
            cur = conn.cursor()
            if editing:
                cur.execute(
                    "UPDATE customers SET name=?, phone=?, default_rate=? WHERE id=?",
                    (name, phone, rate, customer_id)
                )
            else:
                cur.execute(
                    "INSERT INTO customers(name,phone,default_rate) VALUES(?,?,?)",
                    (name, phone, rate)
                )
            conn.commit()
            conn.close()
            popup.dismiss()
            self.load_customers()

            if editing:
                detail = self.manager.get_screen("customer_detail")
                detail.load_customer(customer_id)

        save.bind(on_press=save_customer)

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

            delete.bind(
                on_press=lambda _: confirm_action(
                    "Delete Customer",
                    "Customer aur uski milk/payment history delete ho jayegi.\nSure?",
                    do_delete
                )
            )

        popup.open()


# ============================================================
# CUSTOMER DETAIL
# ============================================================

class CustomerDetailScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = None

        self.layout = BoxLayout(orientation="vertical", padding=dp(7), spacing=dp(5))
        top = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(4))

        back = make_button("< Back", 46, 14)
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "customers"))
        top.add_widget(back)

        self.title = Label(text="Customer", font_size=dp(19), bold=True)
        top.add_widget(self.title)

        edit = make_button("Edit", 46, 14)
        edit.size_hint_x = None
        edit.width = dp(62)
        edit.bind(on_press=lambda _: self.edit_customer())
        top.add_widget(edit)
        self.layout.add_widget(top)

        self.summary = Label(text="", font_size=dp(13),
                             size_hint_y=None, height=dp(78))
        self.layout.add_widget(self.summary)

        actions = GridLayout(cols=3, size_hint_y=None, height=dp(60), spacing=dp(4))
        m = make_button("MORNING", 56, 12)
        e = make_button("EVENING", 56, 12)
        p = make_button("PAYMENT", 56, 12)
        m.bind(on_press=lambda _: self.entry_popup("Morning"))
        e.bind(on_press=lambda _: self.entry_popup("Evening"))
        p.bind(on_press=lambda _: self.payment_popup())
        actions.add_widget(m)
        actions.add_widget(e)
        actions.add_widget(p)
        self.layout.add_widget(actions)

        export = GridLayout(cols=2, size_hint_y=None, height=dp(45), spacing=dp(4))
        x = make_button("EXCEL", 42, 13)
        pdf = make_button("PDF", 42, 13)
        x.bind(on_press=lambda _: self.export_xlsx())
        pdf.bind(on_press=lambda _: self.export_pdf())
        export.add_widget(x)
        export.add_widget(pdf)
        self.layout.add_widget(export)

        self.layout.add_widget(Label(text="MILK + PAYMENT HISTORY",
                                     font_size=dp(14), bold=True,
                                     size_hint_y=None, height=dp(28)))

        scroll = ScrollView()
        self.history = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.history.bind(minimum_height=self.history.setter("height"))
        scroll.add_widget(self.history)
        self.layout.add_widget(scroll)
        self.add_widget(self.layout)

    def load_customer(self, cid):
        self.customer_id = cid
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name, phone, default_rate FROM customers WHERE id=?", (cid,))
        customer = cur.fetchone()
        conn.close()

        if not customer:
            self.manager.current = "customers"
            return

        self.title.text = customer[0]
        self.load_history()

    def load_history(self):
        self.history.clear_widgets()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name, phone, default_rate FROM customers WHERE id=?",
                    (self.customer_id,))
        customer = cur.fetchone()

        cur.execute("""
            SELECT id, entry_date, session, litres, rate, amount
            FROM milk_entries
            WHERE customer_id=?
            ORDER BY entry_date DESC, id DESC
            LIMIT 200
        """, (self.customer_id,))
        milk = cur.fetchall()

        cur.execute("""
            SELECT id, payment_date, amount, note
            FROM payments
            WHERE customer_id=?
            ORDER BY payment_date DESC, id DESC
            LIMIT 200
        """, (self.customer_id,))
        payments = cur.fetchall()
        conn.close()

        milk_total, paid_total, balance = get_customer_balance(self.customer_id)
        rate = customer[2] if customer and customer[2] is not None else None

        self.summary.text = (
            f"Phone: {customer[1] if customer else ''} | "
            f"Default Rate: {rate if rate is not None else 'Manual'}\n"
            f"Milk Amount: Rs. {milk_total:.2f} | Paid: Rs. {paid_total:.2f} | "
            f"DENA HAI: Rs. {balance:.2f}"
        )

        events = []
        for row in milk:
            events.append(("milk", row))
        for row in payments:
            events.append(("payment", row))

        events.sort(key=lambda x: (x[1][1], x[1][0]), reverse=True)

        if not events:
            self.history.add_widget(Label(
                text="No history yet.", font_size=dp(15),
                size_hint_y=None, height=dp(45)
            ))
            return

        for typ, row in events:
            if typ == "milk":
                eid, edate, session, litres, rate, amount = row
                box = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(3))
                box.add_widget(Label(
                    text=f"{format_date(edate)} | {session}\n"
                         f"{litres:.2f} L × Rs.{rate:.2f} = Rs.{amount:.2f}",
                    font_size=dp(11)
                ))
                edit = make_button("Edit", 46, 11)
                delete = make_button("Del", 46, 11)
                edit.size_hint_x = delete.size_hint_x = None
                edit.width = dp(48)
                delete.width = dp(42)
                edit.bind(on_press=lambda _, i=eid: self.entry_popup(None, i))
                delete.bind(on_press=lambda _, i=eid: self.delete_milk(i))
                box.add_widget(edit)
                box.add_widget(delete)
                self.history.add_widget(box)
            else:
                pid, pdate, amount, note = row
                box = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(3))
                box.add_widget(Label(
                    text=f"{format_date(pdate)} | PAYMENT\n"
                         f"Paid: Rs.{amount:.2f} {note}",
                    font_size=dp(11)
                ))
                delete = make_button("Del", 44, 11)
                delete.size_hint_x = None
                delete.width = dp(45)
                delete.bind(on_press=lambda _, i=pid: self.delete_payment(i))
                box.add_widget(delete)
                self.history.add_widget(box)

    def edit_customer(self):
        self.manager.get_screen("customers").customer_form(self.customer_id)

    def entry_popup(self, session="Morning", entry_id=None):
        editing = entry_id is not None
        conn = get_db()
        cur = conn.cursor()

        existing = None
        if editing:
            cur.execute("""
                SELECT entry_date, session, litres, rate
                FROM milk_entries WHERE id=? AND customer_id=?
            """, (entry_id, self.customer_id))
            existing = cur.fetchone()

        cur.execute("SELECT default_rate FROM customers WHERE id=?",
                    (self.customer_id,))
        rate_row = cur.fetchone()
        conn.close()

        if editing and not existing:
            show_message("Error", "Entry not found.")
            return

        sel_session = existing[1] if editing else session
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        date_in = make_input(
            "Date YYYY-MM-DD",
            existing[0] if editing else date.today().isoformat()
        )
        litres_in = make_input(
            "Litres *", existing[2] if editing else "", numeric=True
        )
        default_rate = rate_row[0] if rate_row else None
        rate_in = make_input(
            "Rate per Litre *",
            existing[3] if editing else (default_rate or ""),
            numeric=True
        )
        amount = Label(text="Amount: Rs. 0.00", font_size=dp(17),
                       size_hint_y=None, height=dp(32))

        box.add_widget(Label(
            text=f"{'Edit' if editing else 'Add'} {sel_session} Entry",
            font_size=dp(18), bold=True, size_hint_y=None, height=dp(32)
        ))
        box.add_widget(date_in)
        box.add_widget(Label(text=f"Session: {sel_session}",
                             size_hint_y=None, height=dp(28)))
        box.add_widget(litres_in)
        box.add_widget(rate_in)
        box.add_widget(amount)

        save = make_button("SAVE", 52, 17)
        box.add_widget(save)

        popup = Popup(title="Milk Entry", content=box, size_hint=(0.92, 0.72))

        def calc(*_):
            l = parse_positive_float(litres_in.text)
            r = parse_positive_float(rate_in.text)
            amount.text = f"Amount: Rs. {l*r:.2f}" if l and r else "Amount: Rs. 0.00"

        litres_in.bind(text=calc)
        rate_in.bind(text=calc)
        calc()

        def save_entry(_):
            l = parse_positive_float(litres_in.text)
            r = parse_positive_float(rate_in.text)
            if l is None or r is None:
                show_message("Error", "Litres aur Rate valid positive numbers hone chahiye.")
                return

            edate = date_in.text.strip()
            try:
                datetime.strptime(edate, "%Y-%m-%d")
            except ValueError:
                show_message("Invalid Date", "Date YYYY-MM-DD format mein honi chahiye.")
                return

            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT id FROM milk_entries
                WHERE customer_id=? AND entry_date=? AND session=?
            """, (self.customer_id, edate, sel_session))
            duplicate = cur.fetchone()

            if duplicate and (not editing or duplicate[0] != entry_id):
                conn.close()
                show_message("Duplicate",
                             f"{sel_session} entry already exists for {format_date(edate)}.")
                return

            amt = l * r
            if editing:
                cur.execute("""
                    UPDATE milk_entries
                    SET entry_date=?, session=?, litres=?, rate=?, amount=?
                    WHERE id=? AND customer_id=?
                """, (edate, sel_session, l, r, amt, entry_id, self.customer_id))
            else:
                cur.execute("""
                    INSERT INTO milk_entries
                    (customer_id, entry_date, session, litres, rate, amount)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (self.customer_id, edate, sel_session, l, r, amt))

            conn.commit()
            conn.close()
            popup.dismiss()
            self.load_history()

        save.bind(on_press=save_entry)
        popup.open()

    def delete_milk(self, entry_id):
        def do_delete():
            conn = get_db()
            conn.execute("DELETE FROM milk_entries WHERE id=?", (entry_id,))
            conn.commit()
            conn.close()
            self.load_history()

        confirm_action("Delete Entry", "Milk entry delete karni hai?", do_delete)

    def payment_popup(self):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(7))
        date_in = make_input("Payment Date YYYY-MM-DD", date.today().isoformat())
        amount_in = make_input("Amount *", "", numeric=True)
        note_in = make_input("Note (optional)")
        save = make_button("SAVE PAYMENT", 52, 16)

        box.add_widget(date_in)
        box.add_widget(amount_in)
        box.add_widget(note_in)
        box.add_widget(save)

        popup = Popup(title="Payment / Jama", content=box, size_hint=(0.92, 0.58))

        def save_payment(_):
            amount = parse_positive_float(amount_in.text)
            if amount is None:
                show_message("Invalid Amount", "Payment amount valid hona chahiye.")
                return

            pdate = date_in.text.strip()
            try:
                datetime.strptime(pdate, "%Y-%m-%d")
            except ValueError:
                show_message("Invalid Date", "Date YYYY-MM-DD format mein honi chahiye.")
                return

            conn = get_db()
            conn.execute("""
                INSERT INTO payments(customer_id,payment_date,amount,note)
                VALUES(?,?,?,?)
            """, (self.customer_id, pdate, amount, note_in.text.strip()))
            conn.commit()
            conn.close()
            popup.dismiss()
            self.load_history()

        save.bind(on_press=save_payment)
        popup.open()

    def delete_payment(self, payment_id):
        def do_delete():
            conn = get_db()
            conn.execute("DELETE FROM payments WHERE id=?", (payment_id,))
            conn.commit()
            conn.close()
            self.load_history()

        confirm_action("Delete Payment", "Payment delete karni hai?", do_delete)

    def export_xlsx(self):
        try:
            path = generate_customer_xlsx(
                self.customer_id, date.today().year, date.today().month
            )
            share_or_open_file(path, share=False)
        except Exception as exc:
            show_message("Excel Error", str(exc))

    def export_pdf(self):
        try:
            path = generate_customer_pdf(
                self.customer_id, date.today().year, date.today().month
            )
            share_or_open_file(path, share=False)
        except Exception as exc:
            show_message("PDF Error", str(exc))


# ============================================================
# REPORTS
# ============================================================

class ReportsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.year = date.today().year
        self.month = date.today().month

        self.layout = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(5))

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = make_button("< Back", 46, 14)
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        self.month_lbl = Label(text=month_title(self.year, self.month),
                               font_size=dp(17), bold=True)
        top.add_widget(self.month_lbl)
        self.layout.add_widget(top)

        months = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))
        prev = make_button("<", 40, 15)
        nxt = make_button(">", 40, 15)
        prev.bind(on_press=lambda _: self.change_month(-1))
        nxt.bind(on_press=lambda _: self.change_month(1))
        months.add_widget(prev)
        months.add_widget(Label(text="Change Month", font_size=dp(14)))
        months.add_widget(nxt)
        self.layout.add_widget(months)

        exports = GridLayout(cols=2, size_hint_y=None, height=dp(42), spacing=dp(4))
        excel = make_button("ALL EXCEL", 40, 13)
        pdf = make_button("ALL PDF", 40, 13)
        excel.bind(on_press=lambda _: self.export_excel())
        pdf.bind(on_press=lambda _: self.export_pdf())
        exports.add_widget(excel)
        exports.add_widget(pdf)
        self.layout.add_widget(exports)

        scroll = ScrollView()
        self.report_list = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.report_list.bind(minimum_height=self.report_list.setter("height"))
        scroll.add_widget(self.report_list)
        self.layout.add_widget(scroll)
        self.add_widget(self.layout)

    def on_pre_enter(self):
        self.load_report()

    def change_month(self, delta):
        if delta < 0:
            self.year, self.month = previous_month(self.year, self.month)
        else:
            self.year, self.month = next_month(self.year, self.month)
        self.month_lbl.text = month_title(self.year, self.month)
        self.load_report()

    def load_report(self):
        self.report_list.clear_widgets()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, name, phone FROM customers ORDER BY name")
        customers = cur.fetchall()
        conn.close()

        if not customers:
            self.report_list.add_widget(Label(
                text="No customers found.", size_hint_y=None, height=dp(50)
            ))
            return

        totals = [0, 0, 0, 0]

        for cid, name, phone in customers:
            d = get_customer_month_data(cid, self.year, self.month)
            totals[0] += d["previous_due"]
            totals[1] += d["current_amount"]
            totals[2] += d["current_paid"]
            totals[3] += d["total_due"]

            b = make_button(
                f"{name} | Prev Due: Rs.{d['previous_due']:.0f} | "
                f"Current: Rs.{d['current_amount']:.0f} | "
                f"Paid: Rs.{d['current_paid']:.0f} | "
                f"DENA: Rs.{d['total_due']:.0f}",
                62, 12
            )
            b.bind(on_press=lambda _, i=cid: self.open_customer(i))
            self.report_list.add_widget(b)

        self.report_list.add_widget(
            Label(
                text=f"TOTAL | Prev Due Rs.{totals[0]:.0f} | "
                     f"Current Rs.{totals[1]:.0f} | Paid Rs.{totals[2]:.0f} | "
                     f"DENA Rs.{totals[3]:.0f}",
                bold=True, font_size=dp(13),
                size_hint_y=None, height=dp(45)
            )
        )

    def open_customer(self, cid):
        screen = self.manager.get_screen("customer_report")
        screen.load_customer(cid, self.year, self.month)
        self.manager.current = "customer_report"

    def export_excel(self):
        try:
            path = generate_all_customers_xlsx(self.year, self.month)
            share_or_open_file(path, share=False)
        except Exception as exc:
            show_message("Excel Error", str(exc))

    def export_pdf(self):
        if not PDF_AVAILABLE:
            show_message("PDF", "reportlab installed nahi hai.")
            return
        try:
            # PDF for all customers: create it directly here.
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, name, phone FROM customers ORDER BY name")
            customers = cur.fetchall()
            conn.close()

            app = App.get_running_app()
            path = os.path.join(
                app.user_data_dir,
                f"All_Customers_{self.year}_{self.month:02d}.pdf"
            )

            styles = getSampleStyleSheet()
            doc = SimpleDocTemplate(
                path, pagesize=landscape(A4),
                rightMargin=8*mm, leftMargin=8*mm,
                topMargin=8*mm, bottomMargin=8*mm
            )
            data = [["Customer", "Mobile", "Previous Due",
                     "Current", "Paid", "TOTAL DENA"]]

            for cid, name, phone in customers:
                d = get_customer_month_data(cid, self.year, self.month)
                data.append([
                    name, phone, f"Rs.{d['previous_due']:.2f}",
                    f"Rs.{d['current_amount']:.2f}",
                    f"Rs.{d['current_paid']:.2f}",
                    f"Rs.{d['total_due']:.2f}"
                ])

            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2E7D32")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.white),
                ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                ("ALIGN", (2,1), (-1,-1), "RIGHT"),
            ]))
            doc.build([
                Paragraph("<b>DAIRY HISAAB - ALL CUSTOMERS</b>", styles["Title"]),
                Paragraph(month_title(self.year, self.month), styles["Normal"]),
                Spacer(1, 8),
                table
            ])
            share_or_open_file(path, share=False)
        except Exception as exc:
            show_message("PDF Error", str(exc))


class CustomerReportScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = None
        self.year = date.today().year
        self.month = date.today().month

        box = BoxLayout(orientation="vertical", padding=dp(7), spacing=dp(5))
        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = make_button("< Back", 46, 14)
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "reports"))
        top.add_widget(back)
        self.title = Label(text="Report", font_size=dp(18), bold=True)
        top.add_widget(self.title)
        box.add_widget(top)

        exports = GridLayout(cols=2, size_hint_y=None, height=dp(42), spacing=dp(4))
        x = make_button("EXCEL", 40, 13)
        p = make_button("PDF", 40, 13)
        x.bind(on_press=lambda _: self.export_xlsx())
        p.bind(on_press=lambda _: self.export_pdf())
        exports.add_widget(x)
        exports.add_widget(p)
        box.add_widget(exports)

        scroll = ScrollView()
        self.content = BoxLayout(orientation="vertical", size_hint_y=None,
                                 spacing=dp(6), padding=dp(4))
        self.content.bind(minimum_height=self.content.setter("height"))
        scroll.add_widget(self.content)
        box.add_widget(scroll)
        self.add_widget(box)

    def load_customer(self, cid, year=None, month=None):
        self.customer_id = cid
        if year is not None and month is not None:
            self.year, self.month = year, month

        self.content.clear_widgets()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name, phone FROM customers WHERE id=?", (cid,))
        customer = cur.fetchone()
        conn.close()

        if not customer:
            return

        name, phone = customer
        self.title.text = f"{name} - {month_title(self.year, self.month)}"
        d = get_customer_month_data(cid, self.year, self.month)

        self.content.add_widget(Label(
            text=f"Phone: {phone}\nPrevious Due: Rs.{d['previous_due']:.2f}\n"
                 f"Current Milk: {d['current_litres']:.2f} L = Rs.{d['current_amount']:.2f}\n"
                 f"Paid This Month: Rs.{d['current_paid']:.2f}\n"
                 f"TOTAL DENA HAI: Rs.{d['total_due']:.2f}",
            font_size=dp(14), size_hint_y=None, height=dp(125)
        ))

        self.content.add_widget(Label(
            text="10-DAY PERIOD SUMMARY",
            bold=True, font_size=dp(14), size_hint_y=None, height=dp(28)
        ))

        conn = get_db()
        cur = conn.cursor()
        start, end = month_start_end(self.year, self.month)
        cur.execute("""
            SELECT entry_date, litres, amount FROM milk_entries
            WHERE customer_id=? AND entry_date BETWEEN ? AND ?
        """, (cid, start, end))
        rows = cur.fetchall()
        conn.close()

        for period in ["1-10", "11-20", "21-End"]:
            a, b = period_dates(self.year, self.month, period)
            litres = sum(r[1] for r in rows if a <= r[0] <= b)
            amount = sum(r[2] for r in rows if a <= r[0] <= b)
            self.content.add_widget(Label(
                text=f"{period}: {litres:.2f} L | Rs.{amount:.2f}",
                font_size=dp(13), size_hint_y=None, height=dp(28)
            ))

    def export_xlsx(self):
        try:
            path = generate_customer_xlsx(
                self.customer_id, self.year, self.month
            )
            share_or_open_file(path, share=False)
        except Exception as exc:
            show_message("Excel Error", str(exc))

    def export_pdf(self):
        try:
            path = generate_customer_pdf(
                self.customer_id, self.year, self.month
            )
            share_or_open_file(path, share=False)
        except Exception as exc:
            show_message("PDF Error", str(exc))


# ============================================================
# TODAY
# ============================================================

class TodayMilkScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        box = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(5))
        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = make_button("< Back", 46, 14)
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="TODAY'S MILK", font_size=dp(19), bold=True))
        box.add_widget(top)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        box.add_widget(scroll)
        self.add_widget(box)

    def on_pre_enter(self):
        self.load_today()

    def load_today(self):
        self.list_layout.clear_widgets()
        today = date.today().isoformat()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT c.name, m.session, m.litres, m.rate, m.amount
            FROM milk_entries m
            JOIN customers c ON m.customer_id=c.id
            WHERE m.entry_date=?
            ORDER BY m.id DESC
        """, (today,))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            self.list_layout.add_widget(Label(
                text="Aaj ki koi entry nahi hai.",
                font_size=dp(16), size_hint_y=None, height=dp(50)
            ))
            return

        total = 0
        for name, session, litres, rate, amount in rows:
            total += amount
            self.list_layout.add_widget(Label(
                text=f"{name} | {session} | {litres:.2f} L × Rs.{rate:.2f} = Rs.{amount:.2f}",
                font_size=dp(13), size_hint_y=None, height=dp(38)
            ))

        self.list_layout.add_widget(Label(
            text=f"TODAY TOTAL: Rs.{total:.2f}",
            bold=True, font_size=dp(15),
            size_hint_y=None, height=dp(45)
        ))


# ============================================================
# APP
# ============================================================

class DairyApp(App):
    title = APP_NAME

    def build(self):
        init_db()
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(CustomersScreen(name="customers"))
        sm.add_widget(CustomerDetailScreen(name="customer_detail"))
        sm.add_widget(TodayMilkScreen(name="today"))
        sm.add_widget(ReportsScreen(name="reports"))
        sm.add_widget(CustomerReportScreen(name="customer_report"))
        return sm


if __name__ == "__main__":
    DairyApp().run()
