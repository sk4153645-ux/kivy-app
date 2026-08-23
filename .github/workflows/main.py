import os
import re
import sqlite3
from calendar import monthrange
from datetime import date, datetime
from xml.sax.saxutils import escape

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
from kivy.uix.filechooser import FileChooserIconView


APP_NAME = "Dairy Hisaab"


# ============================================================
# OPTIONAL PDF / OCR / ANDROID IMPORTS
# ============================================================

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


try:
    from androidstorage4kivy import SharedStorage, ShareSheet
    ANDROID_STORAGE_AVAILABLE = True
except ImportError:
    ANDROID_STORAGE_AVAILABLE = False


try:
    from PIL import Image, ImageOps, ImageFilter
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


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


def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


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

    if not column_exists(cur, "customers", "phone"):
        cur.execute("ALTER TABLE customers ADD COLUMN phone TEXT NOT NULL DEFAULT ''")

    if not column_exists(cur, "customers", "default_rate"):
        cur.execute("ALTER TABLE customers ADD COLUMN default_rate REAL")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS milk_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            session TEXT NOT NULL,
            litres REAL NOT NULL,
            rate REAL NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_milk_customer_date ON milk_entries(customer_id, entry_date)")

    conn.commit()
    conn.close()


# ============================================================
# GENERAL HELPERS & IMPROVED OCR ENGINE
# ============================================================

_OCR_DIGIT_FIXES = {
    "O": "0", "o": "0", "D": "0",
    "l": "1", "I": "1", "|": "1",
    "S": "5", "s": "5",
    "B": "8",
    "Z": "2",
}

_LITRES_MIN, _LITRES_MAX = 0.1, 60.0
_RATE_MIN, _RATE_MAX = 10.0, 200.0


def _fix_ocr_digits(token):
    return "".join(_OCR_DIGIT_FIXES.get(ch, ch) for ch in token)


def preprocess_register_image(image_path):
    try:
        from PIL import Image, ImageOps, ImageFilter
    except ImportError:
        return None

    try:
        img = Image.open(image_path).convert("L")
        img = ImageOps.autocontrast(img)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        img = img.point(lambda p: 255 if p > 150 else 0)
        return img
    except Exception:
        return None


def _tokenize_line(line):
    cleaned = re.sub(r"[^\dA-Za-z.\s-]", " ", line)
    nums = []
    for tok in cleaned.split():
        fixed = _fix_ocr_digits(tok).strip(".-")
        if not fixed:
            continue
        try:
            nums.append(float(fixed))
        except ValueError:
            continue
    return nums


def _valid_day(day_val, year, month):
    if not (1 <= day_val <= 31):
        return False
    return day_val <= monthrange(year, month)[1]


def _plausible_litres(value):
    return value is not None and _LITRES_MIN <= value <= _LITRES_MAX


def _plausible_rate(value):
    return value is not None and _RATE_MIN <= value <= _RATE_MAX


def parse_register_sheet_ocr(image_path, target_year, target_month, default_rate=None):
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return [], [], "OCR library not installed."

    try:
        pre = preprocess_register_image(image_path)
        img = pre if pre is not None else Image.open(image_path)

        # Allow common letters so digit fixer works
        custom_config = r"--psm 6 -c tessedit_char_whitelist=0123456789.-OoDlISsBZ|"
        raw_text = pytesseract.image_to_string(img, config=custom_config)

        parsed_entries = []
        warnings = []
        seen_days = set()

        for line_no, line in enumerate(raw_text.splitlines(), start=1):
            if not line.strip():
                continue

            nums = _tokenize_line(line)
            if len(nums) < 2:
                continue

            day_val = int(nums[0])
            if not _valid_day(day_val, target_year, target_month):
                warnings.append(f"Line {line_no}: '{line.strip()}' - invalid day '{nums[0]}'.")
                continue

            try:
                entry_date = date(target_year, target_month, day_val).isoformat()
            except ValueError:
                warnings.append(f"Line {line_no}: '{line.strip()}' - could not build date.")
                continue

            if entry_date in seen_days:
                warnings.append(f"Line {line_no}: duplicate row for {entry_date}, keeping later one.")
            seen_days.add(entry_date)

            rest = nums[1:]
            m_l = m_r = e_l = e_r = None

            if len(rest) == 1:
                m_l = rest[0]
            elif len(rest) == 2:
                m_l, e_l = rest
            elif len(rest) == 3:
                m_l, m_r, e_l = rest
            elif len(rest) >= 4:
                m_l, m_r, e_l, e_r = rest[:4]
                if len(rest) > 4:
                    warnings.append(f"Line {line_no}: extra numbers past 5th ignored.")

            needs_rate_review = False

            if m_l is not None and m_r is None:
                m_r = default_rate if default_rate else 0.0
                needs_rate_review = needs_rate_review or not default_rate
            if e_l is not None and e_r is None:
                e_r = default_rate if default_rate else 0.0
                needs_rate_review = needs_rate_review or not default_rate

            for label, val in (("morning litres", m_l), ("evening litres", e_l)):
                if val and val > 0 and not _plausible_litres(val):
                    warnings.append(f"{entry_date}: {label} = {val} out of range.")
            for label, val in (("morning rate", m_r), ("evening rate", e_r)):
                if val and not _plausible_rate(val):
                    warnings.append(f"{entry_date}: {label} = Rs.{val} out of range.")

            parsed_entries.append({
                "date": entry_date,
                "morn_l": m_l or 0.0,
                "morn_r": m_r or 0.0,
                "eve_l": e_l or 0.0,
                "eve_r": e_r or 0.0,
                "needs_rate_review": needs_rate_review,
                "source_line": line.strip(),
            })

        return parsed_entries, warnings, None

    except Exception as e:
        return [], [], str(e)


def make_button(text, height=55, font=18):
    return Button(
        text=text,
        font_size=dp(font),
        size_hint_y=None,
        height=dp(height)
    )


def make_input(hint="", value="", numeric=False):
    return TextInput(
        text=str(value) if value is not None else "",
        hint_text=hint,
        multiline=False,
        font_size=dp(18),
        input_filter="float" if numeric else None,
        size_hint_y=None,
        height=dp(52)
    )


def show_message(title, message):
    box = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
    box.add_widget(Label(text=message, font_size=dp(17), halign="center", valign="middle"))
    close = make_button("OK", 52, 18)
    box.add_widget(close)
    popup = Popup(title=title, content=box, size_hint=(0.88, 0.42))
    close.bind(on_press=popup.dismiss)
    popup.open()


def confirm_action(title, message, callback):
    box = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))
    box.add_widget(Label(text=message, font_size=dp(17), halign="center"))
    buttons = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
    cancel = make_button("CANCEL", 52, 16)
    yes = make_button("YES", 52, 16)
    buttons.add_widget(cancel)
    buttons.add_widget(yes)
    box.add_widget(buttons)

    popup = Popup(title=title, content=box, size_hint=(0.88, 0.42))
    cancel.bind(on_press=popup.dismiss)

    def yes_action(instance):
        popup.dismiss()
        callback()

    yes.bind(on_press=yes_action)
    popup.open()


def parse_positive_float(value):
    try:
        number = float(value)
        return number if number > 0 else None
    except (TypeError, ValueError):
        return None


def format_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        return value


def valid_phone(phone):
    val = phone.strip().replace(" ", "").replace("-", "")
    if val.startswith("+91"):
        val = val[3:]
    elif val.startswith("91") and len(val) == 12:
        val = val[2:]
    return len(val) == 10 and val.isdigit() and val[0] in "6789"


def normalize_phone(phone):
    val = phone.strip().replace(" ", "").replace("-", "")
    if val.startswith("+91"):
        return val
    if val.startswith("91") and len(val) == 12:
        return "+" + val
    return val


def month_title(year, month):
    return date(year, month, 1).strftime("%B %Y")


def previous_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


def next_month(year, month):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def month_start_end(year, month):
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return first.isoformat(), last.isoformat()


def period_range(year, month, period_name):
    last_day = monthrange(year, month)[1]
    if period_name == "1-10":
        return 1, min(10, last_day)
    if period_name == "11-20":
        return 11, min(20, last_day)
    return 21, last_day


def period_dates(year, month, period_name):
    start_day, end_day = period_range(year, month, period_name)
    return date(year, month, start_day).isoformat(), date(year, month, end_day).isoformat()


# ============================================================
# BALANCE / ACCOUNTING
# ============================================================

def get_customer_month_data(customer_id, year, month):
    start_date, end_date = month_start_end(year, month)
    prev_y, prev_m = previous_month(year, month)
    previous_end = date(prev_y, prev_m, monthrange(prev_y, prev_m)[1]).isoformat()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(amount), 0) FROM milk_entries WHERE customer_id=? AND entry_date <= ?", (customer_id, previous_end))
    previous_amount = cur.fetchone()[0] or 0

    cur.execute("SELECT COALESCE(SUM(litres), 0), COALESCE(SUM(amount), 0) FROM milk_entries WHERE customer_id=? AND entry_date BETWEEN ? AND ?", (customer_id, start_date, end_date))
    current_litres, current_amount = cur.fetchone()
    current_litres = current_litres or 0
    current_amount = current_amount or 0
    conn.close()

    total_amount = previous_amount + current_amount
    return {
        "previous_amount": previous_amount,
        "current_litres": current_litres,
        "current_amount": current_amount,
        "total_amount": total_amount
    }


# ============================================================
# PDF HELPERS
# ============================================================

def safe_filename(value):
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    return "".join(c for c in value.replace(" ", "_") if c in allowed) or "report"


def generate_customer_pdf(customer_id, year, month):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab installed nahi hai. CMD me 'pip install reportlab' karein.")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, phone, default_rate FROM customers WHERE id=?", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        conn.close()
        raise RuntimeError("Customer not found.")

    name, phone, default_rate = customer
    start_date, end_date = month_start_end(year, month)

    cur.execute("SELECT entry_date, session, litres, rate, amount FROM milk_entries WHERE customer_id=? AND entry_date BETWEEN ? AND ? ORDER BY entry_date, session", (customer_id, start_date, end_date))
    rows = cur.fetchall()
    conn.close()

    data = get_customer_month_data(customer_id, year, month)
    app = App.get_running_app()
    filename = f"{safe_filename(name)}_{year}_{month:02d}.pdf"
    pdf_path = os.path.join(app.user_data_dir if app else ".", filename)

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(pdf_path, pagesize=landscape(A4), rightMargin=10*mm, leftMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm)
    story = [
        Paragraph("<b>DAIRY HISAAB</b>", styles["Title"]),
        Paragraph(f"<b>Customer:</b> {escape(name)} | <b>Mobile:</b> {escape(phone)} | <b>Month:</b> {month_title(year, month)}", styles["Normal"]),
        Spacer(1, 8)
    ]

    table_data = [["Date", "Morning L", "Morning Rate", "Evening L", "Evening Rate", "Day Amount"]]
    grouped = {}
    for entry_date, session, litres, rate, amount in rows:
        if entry_date not in grouped:
            grouped[entry_date] = {"Morning": None, "Evening": None}
        grouped[entry_date][session] = (litres, rate, amount)

    for day in sorted(grouped.keys()):
        m = grouped[day]["Morning"]
        e = grouped[day]["Evening"]
        ml, mr = (m[0], m[1]) if m else (0, 0)
        el, er = (e[0], e[1]) if e else (0, 0)
        tot_a = (m[2] if m else 0) + (e[2] if e else 0)

        table_data.append([
            format_date(day),
            f"{ml:.2f}" if ml else "-",
            f"Rs. {mr:.2f}" if mr else "-",
            f"{el:.2f}" if el else "-",
            f"Rs. {er:.2f}" if er else "-",
            f"Rs. {tot_a:.2f}"
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D32")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")
    ]))
    story.append(table)
    story.append(Spacer(1, 12))

    summary_data = [
        ["Previous Dues", f"Rs. {data['previous_amount']:.2f}"],
        ["Current Month Milk", f"{data['current_litres']:.2f} L"],
        ["Current Month Total", f"Rs. {data['current_amount']:.2f}"],
        ["Total Amount (Dena Hai)", f"Rs. {data['total_amount']:.2f}"]
    ]
    stable = Table(summary_data, colWidths=[55*mm, 55*mm])
    stable.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold")
    ]))
    story.append(stable)
    doc.build(story)
    return pdf_path


def generate_all_customers_pdf(year, month):
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab installed nahi hai. CMD me 'pip install reportlab' karein.")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone FROM customers ORDER BY name")
    customers = cur.fetchall()
    conn.close()

    app = App.get_running_app()
    filename = f"All_Customers_{year}_{month:02d}.pdf"
    pdf_path = os.path.join(app.user_data_dir if app else ".", filename)

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(pdf_path, pagesize=landscape(A4), rightMargin=8*mm, leftMargin=8*mm, topMargin=8*mm, bottomMargin=8*mm)
    story = [
        Paragraph("<b>DAIRY HISAAB - ALL CUSTOMERS</b>", styles["Title"]),
        Paragraph(f"Statement: {month_title(year, month)}", styles["Normal"]),
        Spacer(1, 8)
    ]

    table_data = [["Customer", "Mobile", "Prev Amount", "Current Amount", "Total Dena Hai"]]
    tot_prev = tot_amt = tot_fin = 0

    for cid, name, phone in customers:
        data = get_customer_month_data(cid, year, month)
        tot_prev += data["previous_amount"]
        tot_amt += data["current_amount"]
        tot_fin += data["total_amount"]

        table_data.append([
            escape(name),
            escape(phone),
            f"Rs. {data['previous_amount']:.2f}",
            f"Rs. {data['current_amount']:.2f}",
            f"Rs. {data['total_amount']:.2f}"
        ])

    table_data.append(["TOTAL", "", f"Rs. {tot_prev:.2f}", f"Rs. {tot_amt:.2f}", f"Rs. {tot_fin:.2f}"])
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D32")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    ]))
    story.append(table)
    doc.build(story)
    return pdf_path


def share_pdf(pdf_path):
    if ANDROID_STORAGE_AVAILABLE:
        try:
            storage = SharedStorage()
            shared_file = storage.copy_to_shared(pdf_path, collection="DOCUMENTS", filepath=os.path.basename(pdf_path))
            if shared_file:
                ShareSheet().share_file(shared_file)
                return True
        except Exception as exc:
            print("Android sharing error:", exc)
    try:
        import webbrowser
        webbrowser.open("file://" + pdf_path)
        return True
    except Exception:
        return False


def open_pdf(pdf_path):
    if ANDROID_STORAGE_AVAILABLE:
        try:
            storage = SharedStorage()
            shared_file = storage.copy_to_shared(pdf_path, collection="DOCUMENTS", filepath=os.path.basename(pdf_path))
            if shared_file:
                ShareSheet().view_file(shared_file)
                return True
        except Exception as exc:
            print("PDF open error:", exc)
    try:
        import webbrowser
        webbrowser.open("file://" + pdf_path)
        return True
    except Exception:
        return False


# ============================================================
# SCREENS
# ============================================================

class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        layout.add_widget(Label(text="DAIRY HISAAB", font_size=dp(28), bold=True, size_hint_y=None, height=dp(70)))

        customers = make_button("CUSTOMERS", 65, 21)
        today = make_button("TODAY'S MILK", 65, 21)
        reports = make_button("REPORTS", 65, 21)

        customers.bind(on_press=lambda x: self.go("customers"))
        today.bind(on_press=lambda x: self.go("today"))
        reports.bind(on_press=lambda x: self.go("reports"))

        layout.add_widget(customers)
        layout.add_widget(today)
        layout.add_widget(reports)
        self.add_widget(layout)

    def go(self, name):
        self.manager.current = name


class CustomersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(7))

        top = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(5))
        back = make_button("< Back", 50, 14)
        back.size_hint_x = None
        back.width = dp(82)
        back.bind(on_press=lambda x: self.go_home())

        title = Label(text="CUSTOMERS", font_size=dp(21), bold=True)
        add = make_button("+ Add", 50, 14)
        add.size_hint_x = None
        add.width = dp(88)
        add.bind(on_press=lambda x: self.customer_form())

        top.add_widget(back)
        top.add_widget(title)
        top.add_widget(add)
        self.layout.add_widget(top)

        self.search = TextInput(hint_text="Search name or mobile", multiline=False, font_size=dp(17), size_hint_y=None, height=dp(50))
        self.search.bind(text=lambda *_: self.load_customers())
        self.layout.add_widget(self.search)

        scroll = ScrollView()
        self.customer_list = GridLayout(cols=1, spacing=dp(7), size_hint_y=None)
        self.customer_list.bind(minimum_height=self.customer_list.setter("height"))
        scroll.add_widget(self.customer_list)
        self.layout.add_widget(scroll)

        self.add_widget(self.layout)

    def on_pre_enter(self):
        self.load_customers()

    def go_home(self):
        self.manager.current = "home"

    def load_customers(self):
        self.customer_list.clear_widgets()
        search = self.search.text.strip().lower()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.name, c.phone, c.default_rate, COALESCE(SUM(m.amount), 0)
            FROM customers c
            LEFT JOIN milk_entries m ON c.id=m.customer_id
            GROUP BY c.id, c.name, c.phone, c.default_rate
            ORDER BY c.name
        """)
        rows = cur.fetchall()
        conn.close()

        if search:
            rows = [r for r in rows if search in r[1].lower() or search in r[2].lower()]

        if not rows:
            self.customer_list.add_widget(Label(text="No customers found.", font_size=dp(18), size_hint_y=None, height=dp(65)))
            return

        for cid, name, phone, default_rate, total in rows:
            rate_text = f"Rs. {default_rate:.2f}/L" if default_rate is not None else "Manual"
            btn = make_button(f"{name} | {phone}\nRate: {rate_text} | Total Amount: Rs. {total:.2f}", 75, 14)
            btn.bind(on_press=lambda x, i=cid: self.open_customer(i))
            self.customer_list.add_widget(btn)

    def open_customer(self, customer_id):
        screen = self.manager.get_screen("customer_detail")
        screen.load_customer(customer_id)
        self.manager.current = "customer_detail"

    def customer_form(self, customer_id=None):
        editing = customer_id is not None
        existing = None

        if editing:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT name, phone, default_rate FROM customers WHERE id=?", (customer_id,))
            existing = cur.fetchone()
            conn.close()

        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(7))
        name_in = make_input("Name *", existing[0] if existing else "")
        phone_in = make_input("Mobile Number *", existing[1] if existing else "")
        rate_in = make_input("Default Rate (Optional)", existing[2] if existing and existing[2] is not None else "", numeric=True)

        box.add_widget(Label(text="Name and Mobile Number are required", font_size=dp(13), size_hint_y=None, height=dp(25)))
        box.add_widget(name_in)
        box.add_widget(phone_in)
        box.add_widget(rate_in)

        save = make_button("SAVE", 55, 17)
        box.add_widget(save)

        if editing:
            del_btn = make_button("DELETE THIS CUSTOMER", 45, 14)
            del_btn.background_color = (0.8, 0.2, 0.2, 1)
            box.add_widget(del_btn)

        popup = Popup(title="Edit Customer" if editing else "Add Customer", content=box, size_hint=(0.92, 0.68 if editing else 0.60))

        def save_customer(instance):
            name = name_in.text.strip()
            phone = normalize_phone(phone_in.text)
            if not name:
                show_message("Required", "Customer name required hai.")
                return
            if not valid_phone(phone):
                show_message("Invalid Mobile", "Valid 10 digit Indian mobile number enter karein.")
                return

            rate_text = rate_in.text.strip()
            rate_val = parse_positive_float(rate_text) if rate_text else None
            if rate_text and rate_val is None:
                show_message("Invalid Rate", "Default rate valid number hona chahiye.")
                return

            conn = get_db()
            cur = conn.cursor()
            if editing:
                cur.execute("UPDATE customers SET name=?, phone=?, default_rate=? WHERE id=?", (name, phone, rate_val, customer_id))
            else:
                cur.execute("INSERT INTO customers (name, phone, default_rate) VALUES (?, ?, ?)", (name, phone, rate_val))
            conn.commit()
            conn.close()

            popup.dismiss()
            self.load_customers()

        save.bind(on_press=save_customer)

        if editing:
            def delete_customer_action(instance):
                def do_delete():
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM customers WHERE id=?", (customer_id,))
                    conn.commit()
                    conn.close()
                    popup.dismiss()
                    self.load_customers()
                    self.manager.current = "customers"
                confirm_action("Delete Customer", "Pura khata aur history delete ho jayegi.\nSure hain?", do_delete)

            del_btn.bind(on_press=delete_customer_action)

        popup.open()


class CustomerDetailScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = None
        self.customer_name = ""

        self.layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(5))

        top = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(4))
        back = make_button("< Back", 46, 14)
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda x: self.go_back())

        self.title = Label(text="Customer", font_size=dp(19), bold=True)
        edit = make_button("Edit", 46, 14)
        edit.size_hint_x = None
        edit.width = dp(65)
        edit.bind(on_press=lambda x: self.edit_customer())

        top.add_widget(back)
        top.add_widget(self.title)
        top.add_widget(edit)
        self.layout.add_widget(top)

        self.summary = Label(text="", font_size=dp(13), size_hint_y=None, height=dp(80))
        self.layout.add_widget(self.summary)

        actions = GridLayout(cols=3, size_hint_y=None, height=dp(70), spacing=dp(4))
        m_btn = make_button("Morn Entry", 65, 13)
        e_btn = make_button("Eve Entry", 65, 13)
        ocr_btn = make_button("Scan Register", 65, 13)
        ocr_btn.background_color = (0.2, 0.5, 0.8, 1)

        m_btn.bind(on_press=lambda x: self.entry_popup("Morning"))
        e_btn.bind(on_press=lambda x: self.entry_popup("Evening"))
        ocr_btn.bind(on_press=lambda x: self.open_register_scanner())

        actions.add_widget(m_btn)
        actions.add_widget(e_btn)
        actions.add_widget(ocr_btn)
        self.layout.add_widget(actions)

        report = make_button("CUSTOMER EXCEL REPORT", 42, 14)
        report.bind(on_press=lambda x: self.open_report())
        self.layout.add_widget(report)

        self.layout.add_widget(Label(text="MILK ENTRY HISTORY", font_size=dp(15), bold=True, size_hint_y=None, height=dp(28)))

        scroll = ScrollView()
        self.history = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.history.bind(minimum_height=self.history.setter("height"))
        scroll.add_widget(self.history)
        self.layout.add_widget(scroll)

        self.add_widget(self.layout)

    def load_customer(self, customer_id):
        self.customer_id = customer_id
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name, phone, default_rate FROM customers WHERE id=?", (customer_id,))
        customer = cur.fetchone()
        conn.close()

        if not customer:
            show_message("Error", "Customer not found.")
            self.manager.current = "customers"
            return

        self.customer_name = customer[0]
        self.title.text = customer[0]
        self.load_history()

    def load_history(self):
        self.history.clear_widgets()

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT COALESCE(SUM(litres), 0) FROM milk_entries WHERE customer_id=? ", (self.customer_id,))
        tot_litres = cur.fetchone()[0] or 0

        cur.execute("SELECT name, phone, default_rate FROM customers WHERE id=?", (self.customer_id,))
        customer = cur.fetchone()

        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM milk_entries WHERE customer_id=?", (self.customer_id,))
        milk_tot = cur.fetchone()[0] or 0

        cur.execute("""
            SELECT id, entry_date, session, litres, rate, amount 
            FROM milk_entries WHERE customer_id=? 
            ORDER BY entry_date DESC, id DESC LIMIT 100
        """, (self.customer_id,))
        entries = cur.fetchall()
        conn.close()

        rate_t = f"Rs. {customer[2]:.2f}/L" if customer and customer[2] is not None else "Manual"

        self.summary.text = (
            f"Phone: {customer[1] if customer else ''} | Default: {rate_t}\n"
            f"Total Milk: {tot_litres:.2f} L | Total Dena Hai: Rs. {milk_tot:.2f}"
        )

        if not entries:
            self.history.add_widget(Label(text="No milk entries yet.", font_size=dp(15), size_hint_y=None, height=dp(40)))
            return

        for eid, edate, sess, litres, rate, amt in entries:
            row = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(3))
            row.add_widget(Label(text=f"{format_date(edate)} | {sess}\n{litres:.2f} L x Rs. {rate:.2f} = Rs. {amt:.2f}", font_size=dp(12)))

            edit = make_button("Edit", 48, 12)
            edit.size_hint_x = None
            edit.width = dp(50)
            edit.bind(on_press=lambda x, i=eid: self.entry_popup(None, i))

            delete = make_button("Del", 48, 12)
            delete.size_hint_x = None
            delete.width = dp(42)
            delete.bind(on_press=lambda x, i=eid: self.delete_entry(i))

            row.add_widget(edit)
            row.add_widget(delete)
            self.history.add_widget(row)

    def edit_customer(self):
        screen = self.manager.get_screen("customers")
        screen.customer_form(self.customer_id)
        self.load_customer(self.customer_id)

    def open_register_scanner(self):
        content = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        filechooser = FileChooserIconView(filters=["*.png", "*.jpg", "*.jpeg"])
        content.add_widget(filechooser)

        btn_box = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        select_btn = make_button("Scan Register Sheet", 45, 14)
        cancel_btn = make_button("Cancel", 45, 14)
        btn_box.add_widget(select_btn)
        btn_box.add_widget(cancel_btn)
        content.add_widget(btn_box)

        popup = Popup(title="Select Register Photo", content=content, size_hint=(0.95, 0.9))
        cancel_btn.bind(on_press=popup.dismiss)

        def process_image(instance):
            if filechooser.selection:
                filepath = filechooser.selection[0]
                popup.dismiss()

                conn = get_db()
                cur = conn.cursor()
                cur.execute("SELECT default_rate FROM customers WHERE id=?", (self.customer_id,))
                d_rate = cur.fetchone()[0]
                conn.close()

                today = date.today()
                entries, warnings, err = parse_register_sheet_ocr(filepath, today.year, today.month, d_rate)

                if err:
                    show_message("OCR Error", str(err))
                    return

                if not entries:
                    show_message("No Data Found", "Register se koi valid line extract nahi hui. Saaf photo try karein.")
                    return

                conn = get_db()
                cur = conn.cursor()
                count = 0
                for item in entries:
                    edate = item["date"]
                    # Morning
                    if item["morn_l"] > 0:
                        cur.execute("DELETE FROM milk_entries WHERE customer_id=? AND entry_date=? AND session='Morning'", (self.customer_id, edate))
                        amt = item["morn_l"] * item["morn_r"]
                        cur.execute("INSERT INTO milk_entries (customer_id, entry_date, session, litres, rate, amount) VALUES (?, ?, 'Morning', ?, ?, ?)",
                                    (self.customer_id, edate, item["morn_l"], item["morn_r"], amt))
                        count += 1
                    # Evening
                    if item["eve_l"] > 0:
                        cur.execute("DELETE FROM milk_entries WHERE customer_id=? AND entry_date=? AND session='Evening'", (self.customer_id, edate))
                        amt = item["eve_l"] * item["eve_r"]
                        cur.execute("INSERT INTO milk_entries (customer_id, entry_date, session, litres, rate, amount) VALUES (?, ?, 'Evening', ?, ?, ?)",
                                    (self.customer_id, edate, item["eve_l"], item["eve_r"], amt))
                        count += 1

                conn.commit()
                conn.close()

                msg = f"{count} entries imported successfully!"
                if warnings:
                    msg += f"\n\nWarnings:\n" + "\n".join(warnings[:4])
                show_message("Scan Completed", msg)
                self.load_history()
            else:
                show_message("Select File", "Kripya photo select karein.")

        select_btn.bind(on_press=process_image)
        popup.open()

    def entry_popup(self, session="Morning", entry_id=None):
        editing = entry_id is not None
        conn = get_db()
        cur = conn.cursor()
        existing = None

        if editing:
            cur.execute("SELECT entry_date, session, litres, rate FROM milk_entries WHERE id=? AND customer_id=?", (entry_id, self.customer_id))
            existing = cur.fetchone()

        cur.execute("SELECT default_rate FROM customers WHERE id=?", (self.customer_id,))
        rate_row = cur.fetchone()
        conn.close()

        sel_date = existing[0] if editing else date.today().isoformat()
        sel_session = existing[1] if editing else session
        init_litres = str(existing[2]) if editing else ""
        init_rate = str(existing[3]) if editing else (str(rate_row[0]) if rate_row and rate_row[0] is not None else "")

        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(6))
        box.add_widget(Label(text="Edit Entry" if editing else f"{sel_session} Entry", font_size=dp(19), bold=True, size_hint_y=None, height=dp(36)))

        date_in = make_input("Date YYYY-MM-DD", sel_date)
        sess_in = make_input("Session", sel_session)
        sess_in.readonly = True
        litres_in = make_input("Litres *", init_litres, numeric=True)
        rate_in = make_input("Rate per Litre *", init_rate, numeric=True)
        amt_lbl = Label(text="Amount: Rs. 0.00", font_size=dp(18), size_hint_y=None, height=dp(35))

        box.add_widget(date_in)
        box.add_widget(sess_in)
        box.add_widget(litres_in)
        box.add_widget(rate_in)
        box.add_widget(amt_lbl)

        save = make_button("SAVE", 54, 17)
        box.add_widget(save)

        popup = Popup(title="Milk Entry", content=box, size_hint=(0.92, 0.78))

        def calc(*args):
            l = parse_positive_float(litres_in.text)
            r = parse_positive_float(rate_in.text)
            amt_lbl.text = f"Amount: Rs. {l*r:.2f}" if (l and r) else "Amount: Rs. 0.00"

        litres_in.bind(text=calc)
        rate_in.bind(text=calc)
        calc()

        def save_entry(instance):
            l = parse_positive_float(litres_in.text)
            r = parse_positive_float(rate_in.text)
            if l is None or r is None:
                show_message("Error", "Litres and Rate must be valid positive numbers.")
                return

            edate = date_in.text.strip()
            try:
                datetime.strptime(edate, "%Y-%m-%d")
            except ValueError:
                show_message("Invalid Date", "Date must be YYYY-MM-DD format.")
                return

            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id FROM milk_entries WHERE customer_id=? AND entry_date=? AND session=?", (self.customer_id, edate, sel_session))
            dup = cur.fetchone()

            if dup and (not editing or dup[0] != entry_id):
                conn.close()
                show_message("Duplicate", f"{sel_session} entry already exists for {format_date(edate)}.")
                return

            amt = l * r
            if editing:
                cur.execute("UPDATE milk_entries SET entry_date=?, session=?, litres=?, rate=?, amount=? WHERE id=? AND customer_id=?", (edate, sel_session, l, r, amt, entry_id, self.customer_id))
            else:
                cur.execute("INSERT INTO milk_entries (customer_id, entry_date, session, litres, rate, amount) VALUES (?, ?, ?, ?, ?, ?)", (self.customer_id, edate, sel_session, l, r, amt))
            conn.commit()
            conn.close()

            popup.dismiss()
            self.load_history()

        save.bind(on_press=save_entry)
        popup.open()

    def delete_entry(self, entry_id):
        def do_delete():
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM milk_entries WHERE id=?", (entry_id,))
            conn.commit()
            conn.close()
            self.load_history()

        confirm_action("Delete Milk Entry", "Are you sure you want to delete this milk entry?", do_delete)

    def open_report(self):
        report = self.manager.get_screen("customer_report")
        report.load_customer(self.customer_id)
        self.manager.current = "customer_report"

    def go_back(self):
        self.manager.current = "customers"


# ============================================================
# ALL REPORTS SCREEN
# ============================================================

class ReportsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(5))

        top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
        back = make_button("< Back", 46, 14)
        back.size_hint_x = None
        back.width = dp(75)
        back.bind(on_press=lambda x: self.go_home())

        title = Label(text="ALL REPORTS", font_size=dp(19), bold=True)
        top.add_widget(back)
        top.add_widget(title)
        self.layout.add_widget(top)

        today = date.today()
        self.year = today.year
        self.month = today.month

        month_bar = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))
        prev_btn = make_button("<", 40, 16)
        prev_btn.size_hint_x = 0.15
        prev_btn.bind(on_press=lambda x: self.change_month(-1))

        self.month_lbl = Label(text=month_title(self.year, self.month), font_size=dp(16), bold=True)

        next_btn = make_button(">", 40, 16)
        next_btn.size_hint_x = 0.15
        next_btn.bind(on_press=lambda x: self.change_month(1))

        month_bar.add_widget(prev_btn)
        month_bar.add_widget(self.month_lbl)
        month_bar.add_widget(next_btn)
        self.layout.add_widget(month_bar)

        pdf_bar = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
        view_pdf_btn = make_button("View PDF", 40, 13)
        view_pdf_btn.bind(on_press=lambda x: self.export_pdf("view"))
        share_pdf_btn = make_button("Share PDF", 40, 13)
        share_pdf_btn.bind(on_press=lambda x: self.export_pdf("share"))
        pdf_bar.add_widget(view_pdf_btn)
        pdf_bar.add_widget(share_pdf_btn)
        self.layout.add_widget(pdf_bar)

        table_header = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(1))
        table_header.add_widget(Button(text="CUSTOMER", bold=True, size_hint_x=0.28, font_size=dp(11)))
        table_header.add_widget(Button(text="PREV DUE", bold=True, size_hint_x=0.18, font_size=dp(11)))
        table_header.add_widget(Button(text="CURR AMT", bold=True, size_hint_x=0.18, font_size=dp(11)))
        table_header.add_widget(Button(text="TOTAL DENA", bold=True, size_hint_x=0.20, font_size=dp(11)))
        table_header.add_widget(Button(text="ACTION", bold=True, size_hint_x=0.16, font_size=dp(11)))
        self.layout.add_widget(table_header)

        scroll = ScrollView()
        self.report_list = GridLayout(cols=5, spacing=dp(1), size_hint_y=None)
        self.report_list.bind(minimum_height=self.report_list.setter("height"))
        scroll.add_widget(self.report_list)
        self.layout.add_widget(scroll)

        self.add_widget(self.layout)

    def on_pre_enter(self):
        self.load_report()

    def go_home(self):
        self.manager.current = "home"

    def change_month(self, delta):
        if delta == -1:
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
            self.report_list.add_widget(Label(text="No customers found.", font_size=dp(15), size_hint_y=None, height=dp(40)))
            return

        tot_prev = 0.0
        tot_curr = 0.0
        tot_final = 0.0

        for cid, name, phone in customers:
            data = get_customer_month_data(cid, self.year, self.month)
            p_amt = data['previous_amount']
            c_amt = data['current_amount']
            f_amt = data['total_amount']

            tot_prev += p_amt
            tot_curr += c_amt
            tot_final += f_amt

            cust_btn = Button(
                text=f"{name}",
                font_size=dp(11),
                bold=True,
                size_hint_x=0.28,
                size_hint_y=None,
                height=dp(34)
            )
            cust_btn.bind(on_press=lambda x, i=cid: self.open_customer_report(i))

            lbl_prev = Label(text=f"{p_amt:.0f}", font_size=dp(11), size_hint_x=0.18, size_hint_y=None, height=dp(34))
            lbl_curr = Label(text=f"{c_amt:.0f}", font_size=dp(11), size_hint_x=0.18, size_hint_y=None, height=dp(34))
            lbl_tot = Label(text=f"{f_amt:.0f}", font_size=dp(11), bold=True, size_hint_x=0.20, size_hint_y=None, height=dp(34))

            scan_btn = Button(
                text="Scan",
                font_size=dp(10),
                size_hint_x=0.16,
                size_hint_y=None,
                height=dp(34),
                background_color=(0.2, 0.5, 0.8, 1)
            )
            scan_btn.bind(on_press=lambda x, i=cid: self.scan_for_customer(i))

            self.report_list.add_widget(cust_btn)
            self.report_list.add_widget(lbl_prev)
            self.report_list.add_widget(lbl_curr)
            self.report_list.add_widget(lbl_tot)
            self.report_list.add_widget(scan_btn)

        self.report_list.add_widget(Button(text="TOTAL", bold=True, size_hint_x=0.28, size_hint_y=None, height=dp(32), font_size=dp(11)))
        self.report_list.add_widget(Button(text=f"{tot_prev:.0f}", bold=True, size_hint_x=0.18, size_hint_y=None, height=dp(32), font_size=dp(11)))
        self.report_list.add_widget(Button(text=f"{tot_curr:.0f}", bold=True, size_hint_x=0.18, size_hint_y=None, height=dp(32), font_size=dp(11)))
        self.report_list.add_widget(Button(text=f"{tot_final:.0f}", bold=True, size_hint_x=0.20, size_hint_y=None, height=dp(32), font_size=dp(11)))
        self.report_list.add_widget(Button(text="-", bold=True, size_hint_x=0.16, size_hint_y=None, height=dp(32), font_size=dp(11)))

    def scan_for_customer(self, customer_id):
        screen = self.manager.get_screen("customer_detail")
        screen.customer_id = customer_id
        screen.open_register_scanner()

    def open_customer_report(self, customer_id):
        screen = self.manager.get_screen("customer_report")
        screen.load_customer(customer_id, self.year, self.month)
        self.manager.current = "customer_report"

    def export_pdf(self, action="view"):
        try:
            pdf_path = generate_all_customers_pdf(self.year, self.month)
            if action == "view":
                open_pdf(pdf_path)
            else:
                share_pdf(pdf_path)
        except Exception as e:
            show_message("PDF Error", str(e))


# ============================================================
# CUSTOMER REPORT SCREEN
# ============================================================

class CustomerReportScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = None
        today = date.today()
        self.year = today.year
        self.month = today.month

        self.layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(4))
        back = make_button("< Back", 48, 14)
        back.size_hint_x = None
        back.width = dp(78)
        back.bind(on_press=lambda x: self.go_back())
        self.title = Label(text="Customer Report", font_size=dp(18), bold=True)
        top.add_widget(back)
        top.add_widget(self.title)
        self.layout.add_widget(top)

        pdf_bar = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(5))
        view_pdf = make_button("View PDF", 45, 14)
        view_pdf.bind(on_press=lambda x: self.export_pdf("view"))
        share_pdf_btn = make_button("Share PDF", 45, 14)
        share_pdf_btn.bind(on_press=lambda x: self.export_pdf("share"))
        pdf_bar.add_widget(view_pdf)
        pdf_bar.add_widget(share_pdf_btn)
        self.layout.add_widget(pdf_bar)

        scroll = ScrollView()
        self.container = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=dp(4))
        self.container.bind(minimum_height=self.container.setter("height"))
        scroll.add_widget(self.container)
        self.layout.add_widget(scroll)

        self.add_widget(self.layout)

    def load_customer(self, cid, year=None, month=None):
        self.customer_id = cid
        if year and month:
            self.year = year
            self.month = month

        self.container.clear_widgets()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name, phone FROM customers WHERE id=?", (cid,))
        customer = cur.fetchone()

        if not customer:
            conn.close()
            return

        name, phone = customer
        self.title.text = f"{name} ({month_title(self.year, self.month)})"

        data = get_customer_month_data(cid, self.year, self.month)

        summary_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(70), padding=dp(4))
        summary_box.add_widget(Label(
            text=f"Phone: {phone} | Prev Due: Rs. {data['previous_amount']:.2f}\n"
                 f"Current Month Total: Rs. {data['current_amount']:.2f} | Total Dena Hai: Rs. {data['total_amount']:.2f}",
            font_size=dp(13), halign="left"
        ))
        self.container.add_widget(summary_box)

        self.container.add_widget(Label(text="--- 10-DAY PERIOD SUMMARY ---", font_size=dp(14), bold=True, size_hint_y=None, height=dp(25)))

        start_date, end_date = month_start_end(self.year, self.month)
        cur.execute("""
            SELECT entry_date, session, litres, rate, amount 
            FROM milk_entries 
            WHERE customer_id=? AND entry_date BETWEEN ? AND ? 
            ORDER BY entry_date
        """, (cid, start_date, end_date))
        rows = cur.fetchall()
        conn.close()

        grouped = {}
        for edate, session, litres, rate, amount in rows:
            if edate not in grouped:
                grouped[edate] = {"Morning": None, "Evening": None}
            grouped[edate][session] = (litres, rate, amount)

        period_grid = GridLayout(cols=3, size_hint_y=None, height=dp(100), spacing=dp(2))
        period_grid.add_widget(Button(text="Period", bold=True, size_hint_y=None, height=dp(28), font_size=dp(12)))
        period_grid.add_widget(Button(text="Milk (L)", bold=True, size_hint_y=None, height=dp(28), font_size=dp(12)))
        period_grid.add_widget(Button(text="Amt (Rs.)", bold=True, size_hint_y=None, height=dp(28), font_size=dp(12)))

        for period in ["1-10", "11-20", "21-End"]:
            p_start, p_end = period_dates(self.year, self.month, period)
            p_litres = 0
            p_amount = 0
            for day, day_data in grouped.items():
                if p_start <= day <= p_end:
                    for s in ["Morning", "Evening"]:
                        if day_data[s]:
                            p_litres += day_data[s][0]
                            p_amount += day_data[s][2]

            period_grid.add_widget(Label(text=period, size_hint_y=None, height=dp(24), font_size=dp(12)))
            period_grid.add_widget(Label(text=f"{p_litres:.1f}", size_hint_y=None, height=dp(24), font_size=dp(12)))
            period_grid.add_widget(Label(text=f"Rs. {p_amount:.0f}", size_hint_y=None, height=dp(24), font_size=dp(12)))

        self.container.add_widget(period_grid)

        self.container.add_widget(Label(text="--- DAILY EXCEL SHEET ---", font_size=dp(14), bold=True, size_hint_y=None, height=dp(25)))

        h1 = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(1))
        h1.add_widget(Button(text="DATE", bold=True, size_hint_x=0.18, font_size=dp(11)))
        h1.add_widget(Button(text="MORNING", bold=True, size_hint_x=0.32, font_size=dp(11)))
        h1.add_widget(Button(text="EVENING", bold=True, size_hint_x=0.32, font_size=dp(11)))
        h1.add_widget(Button(text="TOTAL AMT", bold=True, size_hint_x=0.18, font_size=dp(11)))
        self.container.add_widget(h1)

        h2 = GridLayout(cols=6, size_hint_y=None, height=dp(26), spacing=dp(1))
        h2.add_widget(Button(text="", size_hint_x=0.18))
        h2.add_widget(Button(text="Litre", bold=True, size_hint_x=0.16, font_size=dp(11)))
        h2.add_widget(Button(text="Rate", bold=True, size_hint_x=0.16, font_size=dp(11)))
        h2.add_widget(Button(text="Litre", bold=True, size_hint_x=0.16, font_size=dp(11)))
        h2.add_widget(Button(text="Rate", bold=True, size_hint_x=0.16, font_size=dp(11)))
        h2.add_widget(Button(text="", size_hint_x=0.18))
        self.container.add_widget(h2)

        daily_grid = GridLayout(cols=6, size_hint_y=None, spacing=dp(1))
        daily_grid.bind(minimum_height=daily_grid.setter("height"))

        tot_m_l = 0.0
        tot_e_l = 0.0
        tot_day_amt = 0.0

        if not grouped:
            daily_grid.add_widget(Label(text="No entries", size_hint_y=None, height=dp(30)))
        else:
            for day in sorted(grouped.keys()):
                m = grouped[day]["Morning"]
                e = grouped[day]["Evening"]
                ml, mr = (m[0], m[1]) if m else (0.0, 0.0)
                el, er = (e[0], e[1]) if e else (0.0, 0.0)
                tot_a = (m[2] if m else 0.0) + (e[2] if e else 0.0)

                tot_m_l += ml
                tot_e_l += el
                tot_day_amt += tot_a

                daily_grid.add_widget(Label(text=format_date(day)[0:5], size_hint_x=0.18, size_hint_y=None, height=dp(26), font_size=dp(11)))
                daily_grid.add_widget(Label(text=f"{ml:.1f}" if ml else "-", size_hint_x=0.16, size_hint_y=None, height=dp(26), font_size=dp(11)))
                daily_grid.add_widget(Label(text=f"{mr:.0f}" if mr else "-", size_hint_x=0.16, size_hint_y=None, height=dp(26), font_size=dp(11)))
                daily_grid.add_widget(Label(text=f"{el:.1f}" if el else "-", size_hint_x=0.16, size_hint_y=None, height=dp(26), font_size=dp(11)))
                daily_grid.add_widget(Label(text=f"{er:.0f}" if er else "-", size_hint_x=0.16, size_hint_y=None, height=dp(26), font_size=dp(11)))
                daily_grid.add_widget(Label(text=f"{tot_a:.0f}", size_hint_x=0.18, size_hint_y=None, height=dp(26), font_size=dp(11)))

            daily_grid.add_widget(Button(text="TOTAL", bold=True, size_hint_x=0.18, size_hint_y=None, height=dp(28), font_size=dp(11)))
            daily_grid.add_widget(Button(text=f"{tot_m_l:.1f}", bold=True, size_hint_x=0.16, size_hint_y=None, height=dp(28), font_size=dp(11)))
            daily_grid.add_widget(Button(text="-", bold=True, size_hint_x=0.16, size_hint_y=None, height=dp(28), font_size=dp(11)))
            daily_grid.add_widget(Button(text=f"{tot_e_l:.1f}", bold=True, size_hint_x=0.16, size_hint_y=None, height=dp(28), font_size=dp(11)))
            daily_grid.add_widget(Button(text="-", bold=True, size_hint_x=0.16, size_hint_y=None, height=dp(28), font_size=dp(11)))
            daily_grid.add_widget(Button(text=f"{tot_day_amt:.0f}", bold=True, size_hint_x=0.18, size_hint_y=None, height=dp(28), font_size=dp(11)))

        self.container.add_widget(daily_grid)

    def go_back(self):
        self.manager.current = "reports"

    def export_pdf(self, action="view"):
        try:
            pdf_path = generate_customer_pdf(self.customer_id, self.year, self.month)
            if action == "view":
                open_pdf(pdf_path)
            else:
                share_pdf(pdf_path)
        except Exception as e:
            show_message("PDF Error", str(e))


class TodayMilkScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        top = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(4))
        back = make_button("< Back", 48, 14)
        back.size_hint_x = None
        back.width = dp(78)
        back.bind(on_press=lambda x: self.go_home())
        top.add_widget(back)
        top.add_widget(Label(text="TODAY'S MILK", font_size=dp(20), bold=True))
        layout.add_widget(top)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)

        self.add_widget(layout)

    def go_home(self):
        self.manager.current = "home"

    def on_pre_enter(self):
        self.load_today()

    def load_today(self):
        self.list_layout.clear_widgets()
        today_str = date.today().isoformat()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT c.name, m.session, m.litres, m.amount 
            FROM milk_entries m 
            JOIN customers c ON m.customer_id = c.id 
            WHERE m.entry_date = ?
            ORDER BY m.id DESC
        """, (today_str,))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            self.list_layout.add_widget(Label(text="Aaj ki koi entry nahi hai.", font_size=dp(16), size_hint_y=None, height=dp(50)))
            return

        for name, session, litres, amount in rows:
            self.list_layout.add_widget(Label(text=f"{name} | {session} | {litres:.2f}L | Rs. {amount:.2f}", font_size=dp(14), size_hint_y=None, height=dp(40)))


# ============================================================
# MAIN APP
# ============================================================

class DairyApp(App):
    def build(self):
        init_db()
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(CustomersScreen(name="customers"))
        sm.add_widget(CustomerDetailScreen(name="customer_detail"))
        sm.add_widget(ReportsScreen(name="reports"))
        sm.add_widget(TodayMilkScreen(name="today"))
        sm.add_widget(CustomerReportScreen(name="customer_report"))
        return sm


if __name__ == "__main__":
    DairyApp().run()