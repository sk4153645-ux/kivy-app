# interface.py - Saara UI Layout & Screens Logic
import os
import sqlite3
import threading
from calendar import monthrange
from datetime import date, datetime

from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup

# Dynamic imports for optional tools
try:
    from dairy_ai_scanner import scan_dairy_register
    AI_SCANNER_AVAILABLE = True
except Exception:
    AI_SCANNER_AVAILABLE = False

try:
    from sync_manager import SyncManager
    SYNC_AVAILABLE = True
except Exception:
    SYNC_AVAILABLE = False

try:
    from plyer import filechooser
    PLYER_FILECHOOSER = True
except Exception:
    PLYER_FILECHOOSER = False


# --- UI Helpers ---
def make_button(text, height=50, font=14, bg_color=(0.12, 0.45, 0.25, 1.0)):
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
    close = make_button("OK", 40, 13)
    box.add_widget(close)
    popup = Popup(title=title, content=box, size_hint=(0.85, 0.35))
    close.bind(on_press=popup.dismiss)
    popup.open()

def parse_float(val):
    try:
        return float(val)
    except Exception:
        return 0.0

def calculate_milk_rate(fat, snf, milk_type="Cow", manual_rate=None):
    if manual_rate and manual_rate > 0:
        return manual_rate
    if fat > 0 and snf > 0:
        if milk_type == "Cow":
            return round((fat * 6.5) + (snf * 1.5), 2)
        return round((fat * 7.2) + (snf * 1.8), 2)
    elif fat > 0:
        return round(fat * 8.5, 2)
    return 40.0 if milk_type == "Cow" else 55.0


# --- Screens ---
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", spacing=dp(6))

        header = Button(
            text="🌿  Nilgiri Dairy Collection & Sales",
            font_size=dp(18), bold=True, size_hint_y=None, height=dp(52),
            background_normal='', background_color=(0.12, 0.37, 0.23, 1), color=(1, 1, 1, 1)
        )
        layout.add_widget(header)

        scroll = ScrollView()
        body = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, padding=[dp(10), dp(8)])
        body.bind(minimum_height=body.setter("height"))

        # Section 1: Inward Collection (Farmers)
        body.add_widget(Label(text="MILK COLLECTION (दूध खरीद - Farmers)", font_size=dp(13), bold=True, color=(0.12, 0.37, 0.23, 1), size_hint_y=None, height=dp(22)))
        grid_buy = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(130))
        btn_buy_entry = make_button("📥 Buy Milk\n(Collection Entry)", 60, 14, bg_color=(0.18, 0.55, 0.34, 1))
        btn_buy_list = make_button("📋 Collection\nSummary (Aaj Ka)", 60, 14, bg_color=(0.20, 0.50, 0.40, 1))
        btn_farmers = make_button("🚜 Farmers List\n& Khata", 60, 14, bg_color=(0.25, 0.55, 0.50, 1))
        btn_ai_scan = make_button("📷 AI Scanner\n(Register Scan)", 60, 14, bg_color=(0.80, 0.40, 0.15, 1))

        btn_buy_entry.bind(on_press=lambda _: setattr(self.manager, "current", "buy_milk"))
        btn_buy_list.bind(on_press=lambda _: setattr(self.manager, "current", "collection_list"))
        btn_farmers.bind(on_press=lambda _: setattr(self.manager, "current", "farmers"))
        btn_ai_scan.bind(on_press=lambda _: setattr(self.manager, "current", "scan_register"))

        grid_buy.add_widget(btn_buy_entry)
        grid_buy.add_widget(btn_buy_list)
        grid_buy.add_widget(btn_farmers)
        grid_buy.add_widget(btn_ai_scan)
        body.add_widget(grid_buy)

        # Section 2: Outward Sale (Customers)
        body.add_widget(Label(text="MILK SALES & RETAIL (दूध बिक्री - Customers)", font_size=dp(13), bold=True, color=(0.12, 0.37, 0.23, 1), size_hint_y=None, height=dp(22)))
        grid_sale = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(65))
        btn_sale_entry = make_button("📤 Sell Milk\n(Customer Entry)", 60, 14, bg_color=(0.22, 0.45, 0.65, 1))
        btn_customers = make_button("👥 Customers\nList & Khata", 60, 14, bg_color=(0.35, 0.45, 0.60, 1))

        btn_sale_entry.bind(on_press=lambda _: setattr(self.manager, "current", "daily_entry"))
        btn_customers.bind(on_press=lambda _: setattr(self.manager, "current", "customers"))

        grid_sale.add_widget(btn_sale_entry)
        grid_sale.add_widget(btn_customers)
        body.add_widget(grid_sale)

        # Section 3: Cloud & Reports
        body.add_widget(Label(text="REPORTS & CLOUD UTILITIES", font_size=dp(13), bold=True, color=(0.12, 0.37, 0.23, 1), size_hint_y=None, height=dp(22)))
        grid_reports = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(65))
        btn_reports = make_button("📊 Reports\n& Khata", 60, 13, bg_color=(0.35, 0.45, 0.40, 1))
        btn_reports.bind(on_press=lambda _: setattr(self.manager, "current", "reports"))
        grid_reports.add_widget(btn_reports)

        btn_sync = make_button("☁️ Sync Cloud\n(Supabase)", 60, 13, bg_color=(0.15, 0.35, 0.55, 1))
        btn_sync.bind(on_press=lambda _: self.trigger_cloud_sync())
        grid_reports.add_widget(btn_sync)
        body.add_widget(grid_reports)

        scroll.add_widget(body)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def trigger_cloud_sync(self):
        if not SYNC_AVAILABLE:
            show_message("Sync Error", "sync_manager.py module missing.")
            return

        show_message("Syncing", "Connecting to Supabase... Please wait.")
        def run_sync():
            try:
                manager = SyncManager()
                success, msg = manager.sync_all()
            except Exception as e:
                msg = str(e)
            Clock.schedule_once(lambda dt: show_message("Sync Status", msg))
        threading.Thread(target=run_sync, daemon=True).start()


class BuyMilkScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.shift = "Morning" if datetime.now().hour < 12 else "Evening"
        self.milk_type = "Cow"
        self.current_farmer_id = None

        layout = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="📥 Buy Milk Entry", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
        layout.add_widget(top)

        shift_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        self.btn_m = make_button("☀️ Morning", 38, 13, bg_color=(0.90, 0.60, 0.10, 1) if self.shift == "Morning" else (0.6, 0.6, 0.6, 1))
        self.btn_e = make_button("🌙 Evening", 38, 13, bg_color=(0.20, 0.40, 0.65, 1) if self.shift == "Evening" else (0.6, 0.6, 0.6, 1))
        self.btn_m.bind(on_press=lambda _: self.set_shift("Morning"))
        self.btn_e.bind(on_press=lambda _: self.set_shift("Evening"))
        shift_box.add_widget(self.btn_m)
        shift_box.add_widget(self.btn_e)
        layout.add_widget(shift_box)

        self.farmer_code_in = make_input("Enter Farmer Code (e.g. 01)")
        self.farmer_code_in.bind(text=lambda *_: self.on_code_change())
        layout.add_widget(self.farmer_code_in)

        self.farmer_lbl = Label(text="Farmer: Not Selected", font_size=dp(14), bold=True, size_hint_y=None, height=dp(26), color=(0.1, 0.2, 0.4, 1))
        layout.add_widget(self.farmer_lbl)

        type_box = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        self.btn_cow = make_button("🐄 Cow", 36, 13, bg_color=(0.18, 0.55, 0.34, 1))
        self.btn_buff = make_button("🐃 Buffalo", 36, 13, bg_color=(0.6, 0.6, 0.6, 1))
        self.btn_cow.bind(on_press=lambda _: self.set_milk_type("Cow"))
        self.btn_buff.bind(on_press=lambda _: self.set_milk_type("Buffalo"))
        type_box.add_widget(self.btn_cow)
        type_box.add_widget(self.btn_buff)
        layout.add_widget(type_box)

        self.litres_in = make_input("Litres (लीटर) *", numeric=True)
        layout.add_widget(self.litres_in)

        fat_snf_box = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        self.fat_in = make_input("Fat % (Optional)", numeric=True)
        self.snf_in = make_input("SNF/CLR (Optional)", numeric=True)
        fat_snf_box.add_widget(self.fat_in)
        fat_snf_box.add_widget(self.snf_in)
        layout.add_widget(fat_snf_box)

        self.rate_in = make_input("Rate (₹/L) (Auto/Manual)", numeric=True)
        layout.add_widget(self.rate_in)

        self.litres_in.bind(text=lambda *_: self.calc())
        self.fat_in.bind(text=lambda *_: self.calc())
        self.snf_in.bind(text=lambda *_: self.calc())
        self.rate_in.bind(text=lambda *_: self.calc(manual=True))

        self.total_lbl = Label(text="TOTAL: ₹ 0.00", font_size=dp(18), bold=True, size_hint_y=None, height=dp(45), color=(0.12, 0.45, 0.25, 1))
        layout.add_widget(self.total_lbl)

        btn_box = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        btn_save = make_button("💾 SAVE", 46, 14, bg_color=(0.18, 0.55, 0.34, 1))
        btn_print = make_button("🖨️ SAVE & PRINT", 46, 14, bg_color=(0.20, 0.45, 0.65, 1))
        btn_save.bind(on_press=lambda _: self.save_entry(False))
        btn_print.bind(on_press=lambda _: self.save_entry(True))
        btn_box.add_widget(btn_save)
        btn_box.add_widget(btn_print)
        layout.add_widget(btn_box)

        self.add_widget(layout)

    def set_shift(self, s):
        self.shift = s
        self.btn_m.background_color = (0.90, 0.60, 0.10, 1) if s == "Morning" else (0.6, 0.6, 0.6, 1)
        self.btn_e.background_color = (0.20, 0.40, 0.65, 1) if s == "Evening" else (0.6, 0.6, 0.6, 1)

    def set_milk_type(self, t):
        self.milk_type = t
        self.btn_cow.background_color = (0.18, 0.55, 0.34, 1) if t == "Cow" else (0.6, 0.6, 0.6, 1)
        self.btn_buff.background_color = (0.20, 0.40, 0.65, 1) if t == "Buffalo" else (0.6, 0.6, 0.6, 1)
        self.calc()

    def on_code_change(self):
        code = self.farmer_code_in.text.strip()
        if not code:
            self.current_farmer_id = None
            self.farmer_lbl.text = "Farmer: Not Selected"
            return
        try:
            conn = sqlite3.connect("dairy_v2.db")
            cur = conn.cursor()
            cur.execute("SELECT id, name, milk_type, default_rate FROM farmers WHERE code=? OR id=?", (code, code))
            row = cur.fetchone()
            conn.close()
            if row:
                self.current_farmer_id = row[0]
                self.farmer_lbl.text = f"Farmer: [{code}] {row[1]}"
                if row[2]: self.set_milk_type(row[2])
                if row[3] and row[3] > 0: self.rate_in.text = str(row[3])
                self.calc()
            else:
                self.current_farmer_id = None
                self.farmer_lbl.text = "Farmer Not Found"
        except Exception:
            pass

    def calc(self, manual=False):
        l = parse_float(self.litres_in.text)
        fat = parse_float(self.fat_in.text)
        snf = parse_float(self.snf_in.text)
        if not manual:
            r = calculate_milk_rate(fat, snf, self.milk_type)
            self.rate_in.text = f"{r:.2f}"
        else:
            r = parse_float(self.rate_in.text)
        self.total_lbl.text = f"TOTAL: ₹ {l * r:.2f}"

    def save_entry(self, print_slip):
        if not self.current_farmer_id:
            show_message("Error", "Kisan Code sahi daalein.")
            return
        l = parse_float(self.litres_in.text)
        r = parse_float(self.rate_in.text)
        if l <= 0 or r <= 0:
            show_message("Error", "Litres aur Rate daalein.")
            return
        amt = round(l * r, 2)
        try:
            conn = sqlite3.connect("dairy_v2.db")
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO milk_purchases (farmer_id, entry_date, shift, milk_type, litres, fat, snf, rate, amount, updated_at, is_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (self.current_farmer_id, date.today().isoformat(), self.shift, self.milk_type, l, parse_float(self.fat_in.text), parse_float(self.snf_in.text), r, amt, datetime.utcnow().isoformat()))
            conn.commit()
            conn.close()
            show_message("Saved", f"Entry ₹{amt:.2f} save ho gayi!" + (" (Printing slip...)" if print_slip else ""))
            self.litres_in.text = ""
            self.fat_in.text = ""
            self.snf_in.text = ""
            self.total_lbl.text = "TOTAL: ₹ 0.00"
        except Exception as e:
            show_message("Error", str(e))


class CollectionListScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="Collection Summary", font_size=dp(15), bold=True, color=(0.1, 0.3, 0.1, 1)))
        layout.add_widget(top)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)

        self.summary_bar = Button(text="Day Total: 0.00 L | ₹ 0.00", font_size=dp(14), bold=True, size_hint_y=None, height=dp(40), background_normal='', background_color=(0.12, 0.37, 0.23, 1), color=(1, 1, 1, 1))
        layout.add_widget(self.summary_bar)
        self.add_widget(layout)

    def on_pre_enter(self):
        self.list_layout.clear_widgets()
        try:
            conn = sqlite3.connect("dairy_v2.db")
            cur = conn.cursor()
            cur.execute("""
                SELECT f.code, f.name, p.shift, p.milk_type, p.litres, p.fat, p.snf, p.rate, p.amount
                FROM milk_purchases p JOIN farmers f ON f.id = p.farmer_id
                WHERE p.entry_date=? ORDER BY p.id DESC
            """, (date.today().isoformat(),))
            rows = cur.fetchall()
            conn.close()
        except Exception:
            rows = []

        total_l, total_a = 0.0, 0.0
        for code, name, shift, mtype, l, fat, snf, rate, amt in rows:
            total_l += l
            total_a += amt
            btn = Button(
                text=f" [{code}] {name} ({shift} • {mtype})\n {l:.2f}L | Fat:{fat:.1f} | Rate:₹{rate:.2f} | ₹{amt:.2f}",
                font_size=dp(13), size_hint_y=None, height=dp(58),
                background_normal='', background_color=(0.9, 0.95, 0.9, 1), color=(0.1, 0.2, 0.1, 1), halign='left', valign='middle'
            )
            btn.bind(size=btn.setter('text_size'))
            self.list_layout.add_widget(btn)

        if not rows:
            self.list_layout.add_widget(Label(text="No collection recorded today.", font_size=dp(13), size_hint_y=None, height=dp(50)))
        self.summary_bar.text = f"Day Total: {total_l:.2f} L | ₹{total_a:.2f}"


class FarmersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="🚜 Farmers (किसान)", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
        add_btn = make_button("+ Add", 42, 13, bg_color=(0.18, 0.55, 0.34, 1))
        add_btn.size_hint_x = None
        add_btn.width = dp(75)
        add_btn.bind(on_press=lambda _: self.farmer_form())
        top.add_widget(add_btn)
        layout.add_widget(top)

        self.search_in = TextInput(hint_text="🔍 Search Farmer...", multiline=False, font_size=dp(15), size_hint_y=None, height=dp(44))
        self.search_in.bind(text=lambda *_: self.load_farmers())
        layout.add_widget(self.search_in)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self):
        self.load_farmers()

    def load_farmers(self):
        self.list_layout.clear_widgets()
        search = self.search_in.text.strip().lower()
        try:
            conn = sqlite3.connect("dairy_v2.db")
            cur = conn.cursor()
            cur.execute("SELECT id, code, name, phone, milk_type, default_rate FROM farmers ORDER BY CAST(code AS INTEGER), id")
            rows = cur.fetchall()
            conn.close()
        except Exception:
            rows = []

        if not rows:
            self.list_layout.add_widget(Label(text="No farmers yet. Tap '+ Add'.", font_size=dp(13), size_hint_y=None, height=dp(50)))
            return

        for fid, code, name, phone, mtype, rate in rows:
            cd_str = str(code) if code else f"{fid:02d}"
            if search and search not in name.lower() and search not in cd_str.lower():
                continue

            try:
                conn = sqlite3.connect("dairy_v2.db")
                c = conn.cursor()
                c.execute("SELECT COALESCE(SUM(amount),0) FROM milk_purchases WHERE farmer_id=?", (fid,))
                bill = c.fetchone()[0] or 0.0
                c.execute("SELECT COALESCE(SUM(amount),0) FROM farmer_payments WHERE farmer_id=?", (fid,))
                paid = c.fetchone()[0] or 0.0
                due = bill - paid
                conn.close()
            except Exception:
                due = 0.0

            row_box = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(4))
            name_btn = Button(
                text=f" [{cd_str}] {name}\n 📞 {phone or '-'} • {mtype}", font_size=dp(13),
                background_normal='', background_color=(0.95, 0.95, 0.95, 1), color=(0.1, 0.1, 0.1, 1),
                halign='left', valign='middle'
            )
            name_btn.bind(size=name_btn.setter('text_size'))
            name_btn.bind(on_press=lambda _, f=fid, n=name, cd=cd_str, p=phone, m=mtype, r=rate: self.farmer_form(f, n, cd, p, m, r))

            due_btn = Button(
                text=f"₹ {due:.2f}\n{'Dena Baaki' if due > 0 else 'Clear'}", font_size=dp(13), bold=True,
                size_hint_x=None, width=dp(110), background_normal='',
                background_color=(0.95, 0.85, 0.85, 1) if due > 0 else (0.85, 0.95, 0.85, 1),
                color=(0.7, 0.1, 0.1, 1) if due > 0 else (0.1, 0.5, 0.1, 1)
            )
            due_btn.bind(on_press=lambda _, f=fid, n=name, d=due: self.pay_farmer(f, n, d))

            row_box.add_widget(name_btn)
            row_box.add_widget(due_btn)
            self.list_layout.add_widget(row_box)

    def farmer_form(self, fid=None, name="", code="", phone="", mtype="Cow", rate=0.0):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        code_in = make_input("Farmer Code (e.g. 01)", code)
        name_in = make_input("Full Name *", name)
        phone_in = make_input("Phone", phone)
        rate_in = make_input("Fixed Rate (Optional)", rate if rate else "", numeric=True)
        box.add_widget(code_in); box.add_widget(name_in); box.add_widget(phone_in); box.add_widget(rate_in)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_cancel = make_button("CANCEL", 42, 13, bg_color=(0.5, 0.5, 0.5, 1))
        btn_save = make_button("SAVE", 42, 13, bg_color=(0.18, 0.55, 0.34, 1))
        btns.add_widget(btn_cancel); btns.add_widget(btn_save); box.add_widget(btns)

        popup = Popup(title="Farmer", content=box, size_hint=(0.9, 0.65))
        btn_cancel.bind(on_press=popup.dismiss)

        def save(_):
            nm = name_in.text.strip()
            if not nm: return
            try:
                conn = sqlite3.connect("dairy_v2.db")
                cur = conn.cursor()
                if fid:
                    cur.execute("UPDATE farmers SET code=?, name=?, phone=?, default_rate=?, updated_at=?, is_synced=0 WHERE id=?", (code_in.text.strip(), nm, phone_in.text.strip(), parse_float(rate_in.text), datetime.utcnow().isoformat(), fid))
                else:
                    cur.execute("INSERT INTO farmers (code, name, phone, milk_type, default_rate, updated_at, is_synced) VALUES (?, ?, ?, 'Cow', ?, ?, 0)", (code_in.text.strip(), nm, phone_in.text.strip(), parse_float(rate_in.text), datetime.utcnow().isoformat()))
                conn.commit(); conn.close()
            except Exception: pass
            popup.dismiss(); self.load_farmers()

        btn_save.bind(on_press=save)
        popup.open()

    def pay_farmer(self, fid, name, due):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        box.add_widget(Label(text=f"Pay {name}\nDue: ₹{due:.2f}", font_size=dp(14), bold=True))
        amt_in = make_input("Amount to Pay *", value=due if due > 0 else "", numeric=True)
        note_in = make_input("Note (Optional)")
        box.add_widget(amt_in); box.add_widget(note_in)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_c = make_button("CANCEL", 42, 13, bg_color=(0.5, 0.5, 0.5, 1))
        btn_s = make_button("SAVE PAYMENT", 42, 13, bg_color=(0.18, 0.55, 0.34, 1))
        btns.add_widget(btn_c); btns.add_widget(btn_s); box.add_widget(btns)

        popup = Popup(title="Payment", content=box, size_hint=(0.85, 0.45))
        btn_c.bind(on_press=popup.dismiss)

        def save_p(_):
            amt = parse_float(amt_in.text)
            if amt <= 0: return
            try:
                conn = sqlite3.connect("dairy_v2.db")
                cur = conn.cursor()
                cur.execute("INSERT INTO farmer_payments (farmer_id, payment_date, amount, note, updated_at, is_synced) VALUES (?, ?, ?, ?, ?, 0)", (fid, date.today().isoformat(), amt, note_in.text.strip(), datetime.utcnow().isoformat()))
                conn.commit(); conn.close()
            except Exception: pass
            popup.dismiss(); self.load_farmers()

        btn_s.bind(on_press=save_p)
        popup.open()


class DailyEntryScreen(Screen):
    """Customer Milk Sale Entry"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = "Morning" if datetime.now().hour < 12 else "Evening"
        layout = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None; back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="📤 Customer Milk Sale", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
        layout.add_widget(top)

        self.search_input = TextInput(hint_text="🔍 Search Customer...", multiline=False, font_size=dp(15), size_hint_y=None, height=dp(44))
        self.search_input.bind(text=lambda *_: self.load())
        layout.add_widget(self.search_input)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)

        self.summary_bar = Button(text="Total Sale: 0.00 L | Rs. 0.00", font_size=dp(14), bold=True, size_hint_y=None, height=dp(38), background_normal='', background_color=(0.12, 0.37, 0.23, 1), color=(1, 1, 1, 1))
        layout.add_widget(self.summary_bar)
        self.add_widget(layout)

    def on_pre_enter(self):
        self.load()

    def load(self):
        self.list_layout.clear_widgets()
        search = self.search_input.text.strip().lower()
        try:
            conn = sqlite3.connect("dairy_v2.db")
            cur = conn.cursor()
            cur.execute("SELECT id, code, name, default_rate FROM customers ORDER BY CAST(code AS INTEGER), id")
            customers = cur.fetchall()
            cur.execute("SELECT customer_id, litres, rate, amount FROM milk_entries WHERE entry_date=? AND session=?", (date.today().isoformat(), self.session))
            entries = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}
            conn.close()
        except Exception:
            customers, entries = [], {}

        total_l, total_a = 0.0, 0.0
        for cid, code, name, def_rate in customers:
            cd_str = str(code) if code else f"{cid:02d}"
            if search and search not in name.lower() and search not in cd_str.lower(): continue
            entry = entries.get(cid)
            if entry:
                l, r, amt = entry
                total_l += l; total_a += amt
                card_text = f"  [{cd_str}] {name} (Rate: Rs.{r:.2f})\n  ✓ Done: {l:.2f}L | ₹{amt:.2f}"
                btn = Button(text=card_text, font_size=dp(13), size_hint_y=None, height=dp(64), background_normal='', background_color=(0.85, 0.95, 0.85, 1), color=(0.1, 0.2, 0.1, 1), halign='left', valign='middle')
            else:
                card_text = f"  [{cd_str}] {name} (Rate: Rs.{def_rate or 'N/A'})\n  [ Tap to enter sale... ]"
                btn = Button(text=card_text, font_size=dp(13), size_hint_y=None, height=dp(64), background_normal='', background_color=(1, 1, 1, 1), color=(0.1, 0.2, 0.1, 1), halign='left', valign='middle')

            btn.bind(size=btn.setter('text_size'))
            btn.bind(on_press=lambda _, c=cid, n=name, cd=cd_str, dr=def_rate, e=entry: self.open_entry(c, n, cd, dr, e))
            self.list_layout.add_widget(btn)

        self.summary_bar.text = f"Total Sale ({self.session}): {total_l:.2f} L | Rs.{total_a:.2f}"

    def open_entry(self, cid, name, code_str, def_rate, existing):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        box.add_widget(Label(text=f"[{code_str}] {name}", font_size=dp(15), bold=True))
        litres_in = make_input("Enter Litres *", str(existing[0]) if existing else "", numeric=True)
        rate_in = make_input("Enter Rate *", str(existing[1]) if existing else (str(def_rate) if def_rate else ""), numeric=True)
        amt_lbl = Label(text="Amount: Rs. 0.00", font_size=dp(13))
        box.add_widget(litres_in); box.add_widget(rate_in); box.add_widget(amt_lbl)

        def calc(*_):
            l, r = parse_float(litres_in.text), parse_float(rate_in.text)
            amt_lbl.text = f"Amount: Rs. {l * r:.2f}" if l and r else "Amount: Rs. 0.00"

        litres_in.bind(text=calc); rate_in.bind(text=calc); calc()

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_c = make_button("CANCEL", 42, 13, bg_color=(0.5, 0.5, 0.5, 1))
        btn_s = make_button("SAVE", 42, 13, bg_color=(0.18, 0.55, 0.34, 1))
        btns.add_widget(btn_c); btns.add_widget(btn_s); box.add_widget(btns)

        popup = Popup(title="Sale Entry", content=box, size_hint=(0.85, 0.50))
        btn_c.bind(on_press=popup.dismiss)

        def save_s(_):
            l, r = parse_float(litres_in.text), parse_float(rate_in.text)
            if l <= 0 or r <= 0: return
            try:
                conn = sqlite3.connect("dairy_v2.db")
                cur = conn.cursor()
                cur.execute("INSERT OR REPLACE INTO milk_entries (customer_id, entry_date, session, litres, rate, amount, updated_at, is_synced) VALUES (?, ?, ?, ?, ?, ?, ?, 0)", (cid, date.today().isoformat(), self.session, l, r, l * r, datetime.utcnow().isoformat()))
                conn.commit(); conn.close()
            except Exception: pass
            popup.dismiss(); self.load()

        btn_s.bind(on_press=save_s)
        popup.open()


class CustomersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None; back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="👥 Customers (ग्राहक)", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
        add_btn = make_button("+ Add", 42, 13, bg_color=(0.18, 0.55, 0.34, 1))
        add_btn.size_hint_x = None; add_btn.width = dp(75)
        add_btn.bind(on_press=lambda _: self.customer_form())
        top.add_widget(add_btn)
        layout.add_widget(top)

        self.search_in = TextInput(hint_text="🔍 Search Customer...", multiline=False, font_size=dp(15), size_hint_y=None, height=dp(44))
        self.search_in.bind(text=lambda *_: self.load())
        layout.add_widget(self.search_in)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def on_pre_enter(self):
        self.load()

    def load(self):
        self.list_layout.clear_widgets()
        search = self.search_in.text.strip().lower()
        try:
            conn = sqlite3.connect("dairy_v2.db")
            cur = conn.cursor()
            cur.execute("SELECT id, code, name, phone, default_rate FROM customers ORDER BY CAST(code AS INTEGER), id")
            rows = cur.fetchall()
            conn.close()
        except Exception:
            rows = []

        if not rows:
            self.list_layout.add_widget(Label(text="No customers yet.", font_size=dp(13), size_hint_y=None, height=dp(50)))
            return

        for cid, code, name, phone, rate in rows:
            cd_str = str(code) if code else f"{cid:02d}"
            if search and search not in name.lower() and search not in cd_str.lower(): continue
            try:
                conn = sqlite3.connect("dairy_v2.db")
                c = conn.cursor()
                c.execute("SELECT COALESCE(SUM(amount),0) FROM milk_entries WHERE customer_id=?", (cid,))
                sale = c.fetchone()[0] or 0.0
                c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE customer_id=?", (cid,))
                rec = c.fetchone()[0] or 0.0
                due = sale - rec
                conn.close()
            except Exception:
                due = 0.0

            row_box = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(4))
            name_btn = Button(
                text=f" [{cd_str}] {name}\n 📞 {phone or '-'} • Rate: Rs.{rate:.2f}", font_size=dp(13),
                background_normal='', background_color=(0.95, 0.95, 0.95, 1), color=(0.1, 0.1, 0.1, 1),
                halign='left', valign='middle'
            )
            name_btn.bind(size=name_btn.setter('text_size'))
            name_btn.bind(on_press=lambda _, c=cid, n=name, cd=cd_str, p=phone, r=rate: self.customer_form(c, n, cd, p, r))

            due_btn = Button(
                text=f"₹ {due:.2f}\n{'Due' if due > 0 else 'Clear'}", font_size=dp(13), bold=True,
                size_hint_x=None, width=dp(110), background_normal='',
                background_color=(0.95, 0.85, 0.85, 1) if due > 0 else (0.85, 0.95, 0.85, 1),
                color=(0.7, 0.1, 0.1, 1) if due > 0 else (0.1, 0.5, 0.1, 1)
            )
            due_btn.bind(on_press=lambda _, c=cid, n=name, d=due: self.receive_pay(c, n, d))

            row_box.add_widget(name_btn)
            row_box.add_widget(due_btn)
            self.list_layout.add_widget(row_box)

    def customer_form(self, cid=None, name="", code="", phone="", rate=0.0):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        code_in = make_input("Code", code)
        name_in = make_input("Name *", name)
        phone_in = make_input("Phone", phone)
        rate_in = make_input("Default Rate", rate if rate else "", numeric=True)
        box.add_widget(code_in); box.add_widget(name_in); box.add_widget(phone_in); box.add_widget(rate_in)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_c = make_button("CANCEL", 42, 13, bg_color=(0.5, 0.5, 0.5, 1))
        btn_s = make_button("SAVE", 42, 13, bg_color=(0.18, 0.55, 0.34, 1))
        btns.add_widget(btn_c); btns.add_widget(btn_s); box.add_widget(btns)

        popup = Popup(title="Customer", content=box, size_hint=(0.9, 0.65))
        btn_c.bind(on_press=popup.dismiss)

        def save(_):
            nm = name_in.text.strip()
            if not nm: return
            try:
                conn = sqlite3.connect("dairy_v2.db")
                cur = conn.cursor()
                if cid:
                    cur.execute("UPDATE customers SET code=?, name=?, phone=?, default_rate=?, updated_at=?, is_synced=0 WHERE id=?", (code_in.text.strip(), nm, phone_in.text.strip(), parse_float(rate_in.text), datetime.utcnow().isoformat(), cid))
                else:
                    cur.execute("INSERT INTO customers (code, name, phone, default_rate, updated_at, is_synced) VALUES (?, ?, ?, ?, ?, 0)", (code_in.text.strip(), nm, phone_in.text.strip(), parse_float(rate_in.text), datetime.utcnow().isoformat()))
                conn.commit(); conn.close()
            except Exception: pass
            popup.dismiss(); self.load()

        btn_s.bind(on_press=save)
        popup.open()

    def receive_pay(self, cid, name, due):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        box.add_widget(Label(text=f"Receive from {name}\nDue: ₹{due:.2f}", font_size=dp(14), bold=True))
        amt_in = make_input("Amount *", value=due if due > 0 else "", numeric=True)
        note_in = make_input("Note (Optional)")
        box.add_widget(amt_in); box.add_widget(note_in)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_c = make_button("CANCEL", 42, 13, bg_color=(0.5, 0.5, 0.5, 1))
        btn_s = make_button("SAVE PAYMENT", 42, 13, bg_color=(0.18, 0.55, 0.34, 1))
        btns.add_widget(btn_c); btns.add_widget(btn_s); box.add_widget(btns)

        popup = Popup(title="Payment", content=box, size_hint=(0.85, 0.45))
        btn_c.bind(on_press=popup.dismiss)

        def save_r(_):
            amt = parse_float(amt_in.text)
            if amt <= 0: return
            try:
                conn = sqlite3.connect("dairy_v2.db")
                cur = conn.cursor()
                cur.execute("INSERT INTO payments (customer_id, payment_date, amount, note, updated_at, is_synced) VALUES (?, ?, ?, ?, ?, 0)", (cid, date.today().isoformat(), amt, note_in.text.strip(), datetime.utcnow().isoformat()))
                conn.commit(); conn.close()
            except Exception: pass
            popup.dismiss(); self.load()

        btn_s.bind(on_press=save_r)
        popup.open()


class ReportsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None; back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="📊 Reports & Khata", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
        layout.add_widget(top)
        layout.add_widget(Label(text="Monthly Khata is available directly under\nFarmers & Customers tabs.", font_size=dp(13)))
        self.add_widget(layout)


class ScanRegisterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.img_path = None
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_button("< Back", 42, 13, bg_color=(0.3, 0.4, 0.3, 1))
        back.size_hint_x = None; back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="AI Register Scanner", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
        layout.add_widget(top)

        if not AI_SCANNER_AVAILABLE:
            layout.add_widget(Label(text="AI Scanner module not available in this build.", font_size=dp(13)))
        else:
            self.status = Label(text="No image selected.", font_size=dp(13), size_hint_y=None, height=dp(60))
            layout.add_widget(self.status)
            b1 = make_button("Choose Photo", 46, 14, bg_color=(0.20, 0.45, 0.65, 1))
            b2 = make_button("Scan Image", 46, 14, bg_color=(0.80, 0.40, 0.15, 1))
            b1.bind(on_press=self.pick)
            b2.bind(on_press=self.scan)
            layout.add_widget(b1); layout.add_widget(b2)

        self.add_widget(layout)

    def pick(self, _):
        if PLYER_FILECHOOSER:
            try: filechooser.open_file(on_selection=self.on_sel, filters=[["Images", "*.jpg", "*.png"]])
            except Exception as e: show_message("Error", str(e))

    def on_sel(self, s):
        if s: self.img_path = s[0]; self.status.text = f"Selected: {os.path.basename(self.img_path)}"

    def scan(self, _):
        if not self.img_path: return
        self.status.text = "Scanning..."
        def run():
            try: res = scan_dairy_register(self.img_path); msg = f"Result: {res}"
            except Exception as e: msg = f"Failed: {e}"
            Clock.schedule_once(lambda dt: setattr(self.status, 'text', msg))
        threading.Thread(target=run, daemon=True).start()
