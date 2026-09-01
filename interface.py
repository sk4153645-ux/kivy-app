# interface.py - Pure UI Screens & Layouts (Nilgiri Dairy Original Theme)
import os
import threading
from datetime import date, datetime

from kivy.metrics import dp
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup

# Pure Database & Functioning Engine Import
import database as db

# Dynamic Safe Imports for Scanner/Cloud
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


# ============================================================
# UI THEME CONSTANTS (Matched to Screenshot)
# ============================================================
COLOR_HEADER = (0.12, 0.37, 0.23, 1.0)       # Dark Green Header
COLOR_BUY_ENTRY = (0.18, 0.55, 0.34, 1.0)    # Light Green
COLOR_BUY_TODAY = (0.20, 0.50, 0.40, 1.0)    # Teal-Green
COLOR_CUSTOMER = (0.22, 0.45, 0.65, 1.0)     # Blue
COLOR_SCANNER = (0.80, 0.40, 0.15, 1.0)      # Orange
COLOR_KHATA = (0.35, 0.45, 0.40, 1.0)        # Muted Dark Grey-Green
COLOR_SETTINGS = (0.28, 0.38, 0.48, 1.0)     # Steel Blue
COLOR_INACTIVE = (0.6, 0.6, 0.6, 1.0)


def make_btn(text, height=52, font=14, bg_color=COLOR_BUY_ENTRY):
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


def show_popup(title, msg):
    box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
    box.add_widget(Label(text=msg, font_size=dp(14)))
    close = make_btn("OK", 40, 13, COLOR_HEADER)
    box.add_widget(close)
    pop = Popup(title=title, content=box, size_hint=(0.85, 0.35))
    close.bind(on_press=pop.dismiss)
    pop.open()


def parse_num(val):
    try:
        return float(val)
    except Exception:
        return 0.0


# ============================================================
# 1. HOME SCREEN (Original Layout + Dual Mode + Settings)
# ============================================================
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", spacing=dp(6))

        top_bar = BoxLayout(size_hint_y=None, height=dp(54), spacing=dp(4))
        title_btn = Button(
            text="Nilgiri Dairy App",
            font_size=dp(18), bold=True,
            background_normal='', background_color=COLOR_HEADER, color=(1, 1, 1, 1)
        )
        lang_btn = make_btn("अ/A", 54, 14, (0.15, 0.28, 0.18, 1.0))
        lang_btn.size_hint_x = None
        lang_btn.width = dp(65)
        lang_btn.bind(on_press=self.toggle_lang)

        top_bar.add_widget(title_btn)
        top_bar.add_widget(lang_btn)
        layout.add_widget(top_bar)

        scroll = ScrollView()
        body = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, padding=[dp(10), dp(8)])
        body.bind(minimum_height=body.setter("height"))

        grid_main = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(150))

        btn_buy = make_btn("Buy Milk Entry\n(Kisan Doodh)", 70, 14, COLOR_BUY_ENTRY)
        btn_today = make_btn("Today's Milk\n(Aaj Ka Doodh)", 70, 14, COLOR_BUY_TODAY)
        btn_farmers = make_btn("Farmers\n(Kisan List)", 70, 14, COLOR_CUSTOMER)
        btn_scan = make_btn("AI Scanner\n(Register Scan)", 70, 14, COLOR_SCANNER)

        btn_buy.bind(on_press=lambda _: setattr(self.manager, "current", "buy_milk"))
        btn_today.bind(on_press=lambda _: setattr(self.manager, "current", "collection_list"))
        btn_farmers.bind(on_press=lambda _: setattr(self.manager, "current", "farmers"))
        btn_scan.bind(on_press=lambda _: setattr(self.manager, "current", "scan_register"))

        grid_main.add_widget(btn_buy)
        grid_main.add_widget(btn_today)
        grid_main.add_widget(btn_farmers)
        grid_main.add_widget(btn_scan)
        body.add_widget(grid_main)

        body.add_widget(Label(text="RETAIL MILK SALES (दूध बिक्री)", font_size=dp(12), bold=True, color=(0.5, 0.5, 0.5, 1), size_hint_y=None, height=dp(20)))
        grid_sale = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(65))
        btn_sale = make_btn("Sell Milk Entry\n(Grahak Bikri)", 60, 13, (0.25, 0.55, 0.50, 1))
        btn_cust = make_btn("Customers\n(Grahak List)", 60, 13, (0.35, 0.45, 0.60, 1))
        btn_sale.bind(on_press=lambda _: setattr(self.manager, "current", "daily_entry"))
        btn_cust.bind(on_press=lambda _: setattr(self.manager, "current", "customers"))
        grid_sale.add_widget(btn_sale)
        grid_sale.add_widget(btn_cust)
        body.add_widget(grid_sale)

        body.add_widget(Label(text="REPORTS & SETTINGS", font_size=dp(12), bold=True, color=(0.5, 0.5, 0.5, 1), size_hint_y=None, height=dp(20)))

        btn_reports = make_btn("Full Reports & Khata", 50, 14, COLOR_KHATA)
        btn_reports.bind(on_press=lambda _: setattr(self.manager, "current", "reports"))
        body.add_widget(btn_reports)

        grid_utils = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(52))
        btn_sync = make_btn("☁️ Sync Cloud", 48, 13, (0.15, 0.35, 0.55, 1))
        btn_settings = make_btn("⚙️ Settings", 48, 13, COLOR_SETTINGS)
        btn_sync.bind(on_press=self.sync_cloud)
        btn_settings.bind(on_press=lambda _: setattr(self.manager, "current", "settings"))
        grid_utils.add_widget(btn_sync)
        grid_utils.add_widget(btn_settings)
        body.add_widget(grid_utils)

        scroll.add_widget(body)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def toggle_lang(self, _):
        cur = db.get_setting("language", "hi")
        nxt = "en" if cur == "hi" else "hi"
        db.set_setting("language", nxt)
        show_popup("Language", f"Switched to {'English' if nxt == 'en' else 'Hindi'}")

    def sync_cloud(self, _):
        if not SYNC_AVAILABLE:
            show_popup("Sync", "sync_manager module not found.")
            return
        show_popup("Syncing", "Syncing with Supabase Cloud...")

        def run():
            try:
                m = SyncManager()
                _, msg = m.sync_all()
            except Exception as e:
                msg = str(e)
            Clock.schedule_once(lambda dt: show_popup("Sync Result", msg))
        threading.Thread(target=run, daemon=True).start()


# ============================================================
# 2. BUY MILK SCREEN (Collection Entry + Optional Fat/SNF)
# ============================================================
class BuyMilkScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.shift = "Morning" if datetime.now().hour < 12 else "Evening"
        self.milk_type = "Cow"
        self.fid = None
        self.farmer_phone = None
        self.use_fixed_rate = False

        layout = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))

        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_btn("< Back", 42, 13, COLOR_KHATA)
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="📥 Buy Milk Entry", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
        layout.add_widget(top)

        s_box = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        self.btn_m = make_btn("☀️ Morning", 36, 13, COLOR_SCANNER if self.shift == "Morning" else COLOR_INACTIVE)
        self.btn_e = make_btn("🌙 Evening", 36, 13, COLOR_CUSTOMER if self.shift == "Evening" else COLOR_INACTIVE)
        self.btn_m.bind(on_press=lambda _: self.set_shift("Morning"))
        self.btn_e.bind(on_press=lambda _: self.set_shift("Evening"))
        s_box.add_widget(self.btn_m)
        s_box.add_widget(self.btn_e)
        layout.add_widget(s_box)

        self.code_in = make_input("Farmer Code (e.g. 01)")
        self.code_in.bind(text=lambda *_: self.on_code_change())
        layout.add_widget(self.code_in)

        self.farmer_lbl = Label(text="Farmer: Not Selected", font_size=dp(14), bold=True, size_hint_y=None, height=dp(24), color=(0.1, 0.2, 0.4, 1))
        layout.add_widget(self.farmer_lbl)

        t_box = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
        self.btn_cow = make_btn("🐄 Cow", 34, 13, COLOR_BUY_ENTRY)
        self.btn_buff = make_btn("🐃 Buffalo", 34, 13, COLOR_INACTIVE)
        self.btn_cow.bind(on_press=lambda _: self.set_type("Cow"))
        self.btn_buff.bind(on_press=lambda _: self.set_type("Buffalo"))
        t_box.add_widget(self.btn_cow)
        t_box.add_widget(self.btn_buff)
        layout.add_widget(t_box)

        self.litres_in = make_input("Litres (लीटर) *", numeric=True)
        layout.add_widget(self.litres_in)

        f_s_box = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        self.fat_in = make_input("Fat % (Optional)", numeric=True)
        self.snf_in = make_input("SNF/CLR (Optional)", numeric=True)
        f_s_box.add_widget(self.fat_in)
        f_s_box.add_widget(self.snf_in)
        layout.add_widget(f_s_box)

        self.rate_in = make_input("Rate (₹/L) (Auto/Manual)", numeric=True)
        layout.add_widget(self.rate_in)

        self.litres_in.bind(text=lambda *_: self.calc())
        self.fat_in.bind(text=lambda *_: self.calc())
        self.snf_in.bind(text=lambda *_: self.calc())
        self.rate_in.bind(text=lambda *_: self.calc(manual=True))

        self.total_lbl = Label(text="TOTAL: ₹ 0.00", font_size=dp(18), bold=True, size_hint_y=None, height=dp(42), color=COLOR_HEADER)
        layout.add_widget(self.total_lbl)

        a_box = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        btn_s = make_btn("💾 SAVE", 46, 14, COLOR_BUY_ENTRY)
        btn_sp = make_btn("🖨️ SAVE & PRINT", 46, 14, COLOR_CUSTOMER)
        btn_s.bind(on_press=lambda _: self.save_data(print_slip=False))
        btn_sp.bind(on_press=lambda _: self.save_data(print_slip=True))
        a_box.add_widget(btn_s)
        a_box.add_widget(btn_sp)
        layout.add_widget(a_box)

        self.add_widget(layout)

    def set_shift(self, s):
        self.shift = s
        self.btn_m.background_color = COLOR_SCANNER if s == "Morning" else COLOR_INACTIVE
        self.btn_e.background_color = COLOR_CUSTOMER if s == "Evening" else COLOR_INACTIVE

    def set_type(self, t):
        self.milk_type = t
        self.btn_cow.background_color = COLOR_BUY_ENTRY if t == "Cow" else COLOR_INACTIVE
        self.btn_buff.background_color = COLOR_CUSTOMER if t == "Buffalo" else COLOR_INACTIVE
        self.calc()

    def on_code_change(self):
        cd = self.code_in.text.strip()
        farmer = db.get_farmer_by_code(cd)
        if farmer:
            self.fid, name, mtype, rate, phone = farmer
            self.farmer_phone = phone
            self.farmer_lbl.text = f"Farmer: [{cd}] {name}"
            if mtype:
                self.milk_type = mtype
                self.btn_cow.background_color = COLOR_BUY_ENTRY if mtype == "Cow" else COLOR_INACTIVE
                self.btn_buff.background_color = COLOR_CUSTOMER if mtype == "Buffalo" else COLOR_INACTIVE
            if rate and rate > 0:
                # Farmer has a fixed rate - use it, and do NOT let fat/snf
                # auto-calculation silently overwrite it.
                self.use_fixed_rate = True
                self.rate_in.text = str(rate)
            else:
                self.use_fixed_rate = False
            self.calc()
        else:
            self.fid = None
            self.farmer_phone = None
            self.use_fixed_rate = False
            self.farmer_lbl.text = "Farmer: Not Found"

    def calc(self, manual=False):
        l = parse_num(self.litres_in.text)
        fat = parse_num(self.fat_in.text)
        snf = parse_num(self.snf_in.text)
        if manual or self.use_fixed_rate:
            r = parse_num(self.rate_in.text)
        else:
            r = db.calculate_milk_rate(fat, snf, self.milk_type)
            self.rate_in.text = f"{r:.2f}"
        self.total_lbl.text = f"TOTAL: ₹ {l * r:.2f}"

    def save_data(self, print_slip):
        if not self.fid:
            show_popup("Error", "Pehle Sahi Farmer Code Daalein.")
            return
        l = parse_num(self.litres_in.text)
        r = parse_num(self.rate_in.text)
        if l <= 0 or r <= 0:
            show_popup("Error", "Litres aur Rate daalna zaroori hai.")
            return
        amt = round(l * r, 2)
        fat = parse_num(self.fat_in.text)
        snf = parse_num(self.snf_in.text)

        ok, msg = db.save_buy_entry(self.fid, self.shift, self.milk_type, l, fat, snf, r, amt)
        if not ok:
            show_popup("Error", f"Save failed: {msg}")
            return

        name = self.farmer_lbl.text.split("] ")[-1]
        result_lines = [f"Saved! Total ₹{amt:.2f}"]

        if print_slip:
            p_ok, p_msg = db.print_collection_slip(self.shift, name, self.code_in.text.strip(), self.milk_type, l, fat, snf, r, amt)
            result_lines.append(f"Print: {p_msg}")

        due = db.get_farmer_due_balance(self.fid)
        msg_text = db.format_collection_message(self.shift, name, self.milk_type, l, fat, snf, r, amt, due)

        if db.get_setting("auto_sms", "0") == "1" and self.farmer_phone:
            s_ok, s_msg = db.send_native_sms(self.farmer_phone, msg_text)
            result_lines.append(f"SMS: {s_msg}")

        if db.get_setting("auto_whatsapp", "0") == "1" and self.farmer_phone:
            w_ok, w_msg = db.open_whatsapp_chat(self.farmer_phone, msg_text)
            result_lines.append(f"WhatsApp: {w_msg}")

        show_popup("Result", "\n".join(result_lines))
        self.litres_in.text = ""
        self.fat_in.text = ""
        self.snf_in.text = ""
        self.total_lbl.text = "TOTAL: ₹ 0.00"


# ============================================================
# 3. TODAY'S COLLECTION LIST
# ============================================================
class CollectionListScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_btn("< Back", 42, 13, COLOR_KHATA)
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="📋 Today's Collection List", font_size=dp(15), bold=True, color=(0.1, 0.3, 0.1, 1)))
        layout.add_widget(top)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        layout.add_widget(scroll)

        self.summary_bar = Button(
            text="Day Total: 0.00 L | ₹ 0.00",
            font_size=dp(14), bold=True, size_hint_y=None, height=dp(40),
            background_normal='', background_color=COLOR_HEADER, color=(1, 1, 1, 1)
        )
        layout.add_widget(self.summary_bar)
        self.add_widget(layout)

    def on_pre_enter(self):
        self.list_layout.clear_widgets()
        rows, total_l, total_a = db.get_today_collection()
        for code, name, shift, mtype, l, fat, snf, rate, amt in rows:
            btn = Button(
                text=f"  [{code}] {name} ({shift} • {mtype})\n  {l:.2f}L | Fat:{fat:.1f} | Rate:₹{rate:.2f} | ₹{amt:.2f}",
                font_size=dp(13), size_hint_y=None, height=dp(58),
                background_normal='', background_color=(0.90, 0.95, 0.90, 1), color=(0.1, 0.2, 0.1, 1),
                halign='left', valign='middle'
            )
            btn.bind(size=btn.setter('text_size'))
            self.list_layout.add_widget(btn)

        if not rows:
            self.list_layout.add_widget(Label(text="No collection recorded today.", font_size=dp(13), size_hint_y=None, height=dp(50)))
        self.summary_bar.text = f"Day Total: {total_l:.2f} L | ₹{total_a:.2f}"


# ============================================================
# 4. FARMERS LIST & KHATA (Compact Format)
# ============================================================
class FarmersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_btn("< Back", 42, 13, COLOR_KHATA)
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="🚜 Farmers List (किसान)", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))

        add_btn = make_btn("+ Add", 42, 13, COLOR_BUY_ENTRY)
        add_btn.size_hint_x = None
        add_btn.width = dp(75)
        add_btn.bind(on_press=lambda _: self.farmer_form())
        top.add_widget(add_btn)
        layout.add_widget(top)

        self.search_in = TextInput(hint_text="🔍 Search Farmer...", multiline=False, font_size=dp(15), size_hint_y=None, height=dp(44))
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
        rows = db.get_farmers_with_balance()

        if not rows:
            self.list_layout.add_widget(Label(text="No farmers yet. Tap '+ Add' to create one.", font_size=dp(13), size_hint_y=None, height=dp(50)))
            return

        for fid, cd_str, name, phone, mtype, rate, due in rows:
            if search and search not in name.lower() and search not in cd_str.lower():
                continue

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
            due_btn.bind(on_press=lambda _, f=fid, n=name, d=due: self.pay_popup(f, n, d))

            row_box.add_widget(name_btn)
            row_box.add_widget(due_btn)
            self.list_layout.add_widget(row_box)

    def farmer_form(self, fid=None, name="", code="", phone="", mtype="Cow", rate=0.0):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        code_in = make_input("Farmer Code (e.g. 01)", code)
        name_in = make_input("Full Name *", name)
        phone_in = make_input("Phone", phone)
        rate_in = make_input("Fixed Rate (Optional)", rate if rate else "", numeric=True)
        box.add_widget(code_in)
        box.add_widget(name_in)
        box.add_widget(phone_in)
        box.add_widget(rate_in)

        type_box = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        btn_cow = make_btn("🐄 Cow", 36, 13, COLOR_BUY_ENTRY if mtype == "Cow" else COLOR_INACTIVE)
        btn_buff = make_btn("🐃 Buffalo", 36, 13, COLOR_CUSTOMER if mtype == "Buffalo" else COLOR_INACTIVE)
        selected_type = {"value": mtype or "Cow"}

        def pick_cow(_):
            selected_type["value"] = "Cow"
            btn_cow.background_color = COLOR_BUY_ENTRY
            btn_buff.background_color = COLOR_INACTIVE

        def pick_buff(_):
            selected_type["value"] = "Buffalo"
            btn_buff.background_color = COLOR_CUSTOMER
            btn_cow.background_color = COLOR_INACTIVE

        btn_cow.bind(on_press=pick_cow)
        btn_buff.bind(on_press=pick_buff)
        type_box.add_widget(btn_cow)
        type_box.add_widget(btn_buff)
        box.add_widget(type_box)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_c = make_btn("CANCEL", 42, 13, (0.5, 0.5, 0.5, 1))
        btn_s = make_btn("SAVE", 42, 13, COLOR_BUY_ENTRY)
        btns.add_widget(btn_c)
        btns.add_widget(btn_s)
        box.add_widget(btns)

        pop = Popup(title="Farmer Profile", content=box, size_hint=(0.9, 0.72))
        btn_c.bind(on_press=pop.dismiss)

        def save(_):
            nm = name_in.text.strip()
            if not nm:
                show_popup("Error", "Name is required.")
                return
            ok = db.save_farmer(fid, code_in.text.strip(), nm, phone_in.text.strip(), selected_type["value"], parse_num(rate_in.text))
            if not ok:
                show_popup("Error", "Could not save farmer.")
                return
            pop.dismiss()
            self.load()

        btn_s.bind(on_press=save)
        pop.open()

    def pay_popup(self, fid, name, due):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        box.add_widget(Label(text=f"Pay {name}\nDue Balance: ₹{due:.2f}", font_size=dp(14), bold=True))
        amt_in = make_input("Amount *", value=due if due > 0 else "", numeric=True)
        note_in = make_input("Note (Optional)")
        box.add_widget(amt_in)
        box.add_widget(note_in)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_c = make_btn("CANCEL", 42, 13, (0.5, 0.5, 0.5, 1))
        btn_s = make_btn("SAVE PAYMENT", 42, 13, COLOR_BUY_ENTRY)
        btns.add_widget(btn_c)
        btns.add_widget(btn_s)
        box.add_widget(btns)

        pop = Popup(title="Farmer Payment", content=box, size_hint=(0.85, 0.45))
        btn_c.bind(on_press=pop.dismiss)

        def save_p(_):
            amt = parse_num(amt_in.text)
            if amt <= 0:
                show_popup("Error", "Valid amount daalein.")
                return
            ok = db.save_farmer_payment(fid, amt, note_in.text.strip())
            if not ok:
                show_popup("Error", "Payment save nahi hua.")
                return
            pop.dismiss()
            self.load()

        btn_s.bind(on_press=save_p)
        pop.open()


# ============================================================
# 5. CUSTOMER SALES & KHATA SCREENS
# ============================================================
class DailyEntryScreen(Screen):
    """Customer Milk Sale Entry"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = "Morning" if datetime.now().hour < 12 else "Evening"
        layout = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_btn("< Back", 42, 13, COLOR_KHATA)
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="📤 Customer Milk Sale", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
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
        rows = db.get_customer_sales_status(self.session)

        for cid, cd_str, name, def_rate, entry in rows:
            if search and search not in name.lower() and search not in cd_str.lower():
                continue
            if entry:
                l, r, amt = entry
                txt = f"  [{cd_str}] {name} (Rate: Rs.{r:.2f})\n  ✓ Done: {l:.2f}L | ₹{amt:.2f}"
                bg = (0.85, 0.95, 0.85, 1)
            else:
                txt = f"  [{cd_str}] {name} (Rate: Rs.{def_rate or 'N/A'})\n  [ Tap to enter sale... ]"
                bg = (1, 1, 1, 1)

            btn = Button(text=txt, font_size=dp(13), size_hint_y=None, height=dp(64), background_normal='', background_color=bg, color=(0.1, 0.2, 0.1, 1), halign='left', valign='middle')
            btn.bind(size=btn.setter('text_size'))
            btn.bind(on_press=lambda _, c=cid, n=name, cd=cd_str, dr=def_rate, e=entry: self.open_entry(c, n, cd, dr, e))
            self.list_layout.add_widget(btn)

    def open_entry(self, cid, name, cd_str, def_rate, existing):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        box.add_widget(Label(text=f"[{cd_str}] {name}", font_size=dp(15), bold=True))
        l_in = make_input("Litres *", str(existing[0]) if existing else "", numeric=True)
        r_in = make_input("Rate *", str(existing[1]) if existing else (str(def_rate) if def_rate else ""), numeric=True)
        amt_lbl = Label(text="Amount: Rs. 0.00", font_size=dp(13))
        box.add_widget(l_in)
        box.add_widget(r_in)
        box.add_widget(amt_lbl)

        def calc(*_):
            l, r = parse_num(l_in.text), parse_num(r_in.text)
            amt_lbl.text = f"Amount: Rs. {l * r:.2f}" if l and r else "Amount: Rs. 0.00"
        l_in.bind(text=calc)
        r_in.bind(text=calc)
        calc()

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_c = make_btn("CANCEL", 42, 13, (0.5, 0.5, 0.5, 1))
        btn_s = make_btn("SAVE", 42, 13, COLOR_CUSTOMER)
        btns.add_widget(btn_c)
        btns.add_widget(btn_s)
        box.add_widget(btns)

        pop = Popup(title="Customer Sale", content=box, size_hint=(0.85, 0.50))
        btn_c.bind(on_press=pop.dismiss)

        def save(_):
            l, r = parse_num(l_in.text), parse_num(r_in.text)
            if l > 0 and r > 0:
                db.save_customer_sale(cid, self.session, l, r)
                pop.dismiss()
                self.load()
        btn_s.bind(on_press=save)
        pop.open()


class CustomersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_btn("< Back", 42, 13, COLOR_KHATA)
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="👥 Customers (ग्राहक)", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
        add_btn = make_btn("+ Add", 42, 13, COLOR_CUSTOMER)
        add_btn.size_hint_x = None
        add_btn.width = dp(75)
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
        rows = db.get_customers_with_balance()

        for cid, cd_str, name, phone, rate, due in rows:
            if search and search not in name.lower() and search not in cd_str.lower():
                continue
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
            due_btn.bind(on_press=lambda _, c=cid, n=name, d=due: self.pay_popup(c, n, d))

            row_box.add_widget(name_btn)
            row_box.add_widget(due_btn)
            self.list_layout.add_widget(row_box)

    def customer_form(self, cid=None, name="", code="", phone="", rate=0.0):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        code_in = make_input("Code", code)
        name_in = make_input("Name *", name)
        phone_in = make_input("Phone", phone)
        rate_in = make_input("Default Rate", rate if rate else "", numeric=True)
        box.add_widget(code_in)
        box.add_widget(name_in)
        box.add_widget(phone_in)
        box.add_widget(rate_in)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_c = make_btn("CANCEL", 42, 13, (0.5, 0.5, 0.5, 1))
        btn_s = make_btn("SAVE", 42, 13, COLOR_CUSTOMER)
        btns.add_widget(btn_c)
        btns.add_widget(btn_s)
        box.add_widget(btns)

        pop = Popup(title="Customer", content=box, size_hint=(0.9, 0.65))
        btn_c.bind(on_press=pop.dismiss)

        def save(_):
            nm = name_in.text.strip()
            if not nm:
                show_popup("Error", "Name is required.")
                return
            ok = db.save_customer(cid, code_in.text.strip(), nm, phone_in.text.strip(), parse_num(rate_in.text))
            if not ok:
                show_popup("Error", "Could not save customer.")
                return
            pop.dismiss()
            self.load()
        btn_s.bind(on_press=save)
        pop.open()

    def pay_popup(self, cid, name, due):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        box.add_widget(Label(text=f"Receive from {name}\nDue: ₹{due:.2f}", font_size=dp(14), bold=True))
        amt_in = make_input("Amount *", value=due if due > 0 else "", numeric=True)
        note_in = make_input("Note (Optional)")
        box.add_widget(amt_in)
        box.add_widget(note_in)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_c = make_btn("CANCEL", 42, 13, (0.5, 0.5, 0.5, 1))
        btn_s = make_btn("SAVE PAYMENT", 42, 13, COLOR_CUSTOMER)
        btns.add_widget(btn_c)
        btns.add_widget(btn_s)
        box.add_widget(btns)

        pop = Popup(title="Payment", content=box, size_hint=(0.85, 0.45))
        btn_c.bind(on_press=pop.dismiss)

        def save_r(_):
            amt = parse_num(amt_in.text)
            if amt <= 0:
                show_popup("Error", "Valid amount daalein.")
                return
            ok = db.save_customer_payment(cid, amt, note_in.text.strip())
            if not ok:
                show_popup("Error", "Payment save nahi hua.")
                return
            pop.dismiss()
            self.load()
        btn_s.bind(on_press=save_r)
        pop.open()


# ============================================================
# 6. SETTINGS SCREEN (Bluetooth, Dairy Info, Notify Toggles)
# ============================================================
class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_btn("< Back", 42, 13, COLOR_KHATA)
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="⚙️ App Settings & Hardware", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
        self.layout.add_widget(top)

        scroll = ScrollView()
        body = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None, padding=[dp(4), dp(4)])
        body.bind(minimum_height=body.setter("height"))

        body.add_widget(Label(text="Dairy Profile (Receipt Header)", font_size=dp(13), bold=True, size_hint_y=None, height=dp(20)))
        self.d_name = make_input("Dairy Name", db.get_setting("dairy_name", "Nilgiri Dairy"))
        self.d_phone = make_input("Dairy Phone", db.get_setting("dairy_phone", ""))
        body.add_widget(self.d_name)
        body.add_widget(self.d_phone)

        body.add_widget(Label(text="Bluetooth Thermal Printer MAC Address", font_size=dp(13), bold=True, size_hint_y=None, height=dp(20)))
        self.prn_mac = make_input("Printer MAC (e.g. 00:11:22:33:44:55)", db.get_setting("printer_mac", ""))
        body.add_widget(self.prn_mac)

        body.add_widget(Label(text="Milk Analyzer / Lactoscan MAC Address", font_size=dp(13), bold=True, size_hint_y=None, height=dp(20)))
        self.anz_mac = make_input("Analyzer MAC Address", db.get_setting("analyzer_mac", ""))
        body.add_widget(self.anz_mac)

        body.add_widget(Label(text="Auto Notify Farmer After Save", font_size=dp(13), bold=True, size_hint_y=None, height=dp(20)))
        toggle_box = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        self.btn_sms = make_btn("📱 SMS: OFF", 42, 13, COLOR_INACTIVE)
        self.btn_wa = make_btn("💬 WhatsApp: OFF", 42, 13, COLOR_INACTIVE)
        self.btn_sms.bind(on_press=self.toggle_sms)
        self.btn_wa.bind(on_press=self.toggle_wa)
        toggle_box.add_widget(self.btn_sms)
        toggle_box.add_widget(self.btn_wa)
        body.add_widget(toggle_box)

        note = Label(
            text="Note: Direct SMS sending needs the SEND_SMS permission and\n"
                 "may be restricted by Google Play for public apps.",
            font_size=dp(11), color=(0.5, 0.5, 0.5, 1), size_hint_y=None, height=dp(34)
        )
        body.add_widget(note)

        btn_save = make_btn("💾 SAVE SETTINGS", 48, 14, COLOR_BUY_ENTRY)
        btn_save.bind(on_press=self.save_settings)
        body.add_widget(btn_save)

        scroll.add_widget(body)
        self.layout.add_widget(scroll)
        self.add_widget(self.layout)

    def on_pre_enter(self):
        self.d_name.text = db.get_setting("dairy_name", "Nilgiri Dairy")
        self.d_phone.text = db.get_setting("dairy_phone", "")
        self.prn_mac.text = db.get_setting("printer_mac", "")
        self.anz_mac.text = db.get_setting("analyzer_mac", "")
        self._refresh_toggles()

    def _refresh_toggles(self):
        sms_on = db.get_setting("auto_sms", "0") == "1"
        wa_on = db.get_setting("auto_whatsapp", "0") == "1"
        self.btn_sms.text = f"📱 SMS: {'ON' if sms_on else 'OFF'}"
        self.btn_sms.background_color = COLOR_BUY_ENTRY if sms_on else COLOR_INACTIVE
        self.btn_wa.text = f"💬 WhatsApp: {'ON' if wa_on else 'OFF'}"
        self.btn_wa.background_color = COLOR_BUY_ENTRY if wa_on else COLOR_INACTIVE

    def toggle_sms(self, _):
        cur = db.get_setting("auto_sms", "0")
        db.set_setting("auto_sms", "0" if cur == "1" else "1")
        self._refresh_toggles()

    def toggle_wa(self, _):
        cur = db.get_setting("auto_whatsapp", "0")
        db.set_setting("auto_whatsapp", "0" if cur == "1" else "1")
        self._refresh_toggles()

    def save_settings(self, _):
        db.set_setting("dairy_name", self.d_name.text.strip())
        db.set_setting("dairy_phone", self.d_phone.text.strip())
        db.set_setting("printer_mac", self.prn_mac.text.strip())
        db.set_setting("analyzer_mac", self.anz_mac.text.strip())
        show_popup("Saved", "Settings updated successfully!")


# ============================================================
# 7. REPORTS SCREEN (Farmer Khata + Customer Khata, Excel/PDF)
# ============================================================
class ReportsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mode = "farmer"
        self.selected_id = None
        self.selected_name = None
        self.selected_code = None
        self.year = date.today().year
        self.month = date.today().month

        self.layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_btn("< Back", 42, 13, COLOR_KHATA)
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: self.go_back())
        top.add_widget(back)
        self.title_lbl = Label(text="Reports & Khata", font_size=dp(15), bold=True, color=(0.1, 0.3, 0.1, 1))
        top.add_widget(self.title_lbl)
        self.layout.add_widget(top)

        self.mode_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        self.btn_farmer_mode = make_btn("🚜 Farmers Khata", 38, 13, COLOR_CUSTOMER)
        self.btn_customer_mode = make_btn("👥 Customers Khata", 38, 13, COLOR_INACTIVE)
        self.btn_farmer_mode.bind(on_press=lambda _: self.set_mode("farmer"))
        self.btn_customer_mode.bind(on_press=lambda _: self.set_mode("customer"))
        self.mode_box.add_widget(self.btn_farmer_mode)
        self.mode_box.add_widget(self.btn_customer_mode)
        self.layout.add_widget(self.mode_box)

        self.search_in = TextInput(hint_text="🔍 Search...", multiline=False, font_size=dp(15), size_hint_y=None, height=dp(44))
        self.search_in.bind(text=lambda *_: self.load_list())
        self.layout.add_widget(self.search_in)

        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        self.layout.add_widget(scroll)

        self.add_widget(self.layout)

    def set_mode(self, mode):
        self.mode = mode
        self.selected_id = None
        self.btn_farmer_mode.background_color = COLOR_CUSTOMER if mode == "farmer" else COLOR_INACTIVE
        self.btn_customer_mode.background_color = COLOR_CUSTOMER if mode == "customer" else COLOR_INACTIVE
        self.search_in.text = ""
        self.title_lbl.text = "Reports & Khata"
        self.load_list()

    def go_back(self):
        if self.selected_id:
            self.selected_id = None
            self.title_lbl.text = "Reports & Khata"
            self.mode_box.disabled = False
            self.search_in.disabled = False
            self.load_list()
        else:
            self.manager.current = "home"

    def on_pre_enter(self):
        self.selected_id = None
        self.title_lbl.text = "Reports & Khata"
        self.mode_box.disabled = False
        self.search_in.disabled = False
        self.search_in.text = ""
        self.load_list()

    def load_list(self):
        self.list_layout.clear_widgets()
        search = self.search_in.text.strip().lower()

        if self.mode == "farmer":
            rows = db.get_farmers_with_balance()
        else:
            rows = db.get_customers_with_balance()

        if not rows:
            self.list_layout.add_widget(Label(text="No records yet.", font_size=dp(13), size_hint_y=None, height=dp(50)))
            return

        any_shown = False
        for row in rows:
            if self.mode == "farmer":
                pid, cd_str, name, phone, mtype, rate, due = row
            else:
                pid, cd_str, name, phone, rate, due = row

            if search and search not in name.lower() and search not in cd_str.lower():
                continue

            any_shown = True
            btn = Button(
                text=f"  [{cd_str}]  {name}\n  Total Due: Rs.{due:.2f}",
                font_size=dp(13), size_hint_y=None, height=dp(58),
                background_normal='', color=(0.1, 0.1, 0.1, 1),
                background_color=(1.0, 0.9, 0.85, 1) if due > 0 else (0.9, 0.95, 0.9, 1),
                halign='left', valign='middle'
            )
            btn.bind(size=btn.setter('text_size'))
            btn.bind(on_press=lambda _, p=pid, n=name, cd=cd_str: self.open_report(p, n, cd))
            self.list_layout.add_widget(btn)

        if not any_shown:
            self.list_layout.add_widget(Label(text="No matches found.", font_size=dp(13), size_hint_y=None, height=dp(50)))

    def open_report(self, pid, name, code):
        self.selected_id = pid
        self.selected_name = name
        self.selected_code = code
        self.title_lbl.text = name
        self.mode_box.disabled = True
        self.search_in.disabled = True
        self.year, self.month = date.today().year, date.today().month
        self.render_month_report()

    def render_month_report(self):
        self.list_layout.clear_widgets()

        nav = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_prev = make_btn("< Prev", 40, 13, (0.3, 0.4, 0.5, 1))
        month_lbl = Label(text=date(self.year, self.month, 1).strftime("%B %Y"), font_size=dp(14), bold=True)
        btn_next = make_btn("Next >", 40, 13, (0.3, 0.4, 0.5, 1))
        nav.add_widget(btn_prev)
        nav.add_widget(month_lbl)
        nav.add_widget(btn_next)
        self.list_layout.add_widget(nav)

        def go_prev(_):
            y, m = self.year, self.month
            self.year, self.month = (y - 1, 12) if m == 1 else (y, m - 1)
            self.render_month_report()

        def go_next(_):
            y, m = self.year, self.month
            self.year, self.month = (y + 1, 1) if m == 12 else (y, m + 1)
            self.render_month_report()

        btn_prev.bind(on_press=go_prev)
        btn_next.bind(on_press=go_next)

        if self.mode == "farmer":
            data = db.get_farmer_month_data(self.selected_id, self.year, self.month)
        else:
            data = db.get_customer_month_data(self.selected_id, self.year, self.month)

        stats = (
            f"Previous Due: Rs.{data['previous_due']:.2f}\n"
            f"This Month: {data['current_litres']:.2f} L = Rs.{data['current_amount']:.2f}\n"
            f"This Month Paid: Rs.{data['current_paid']:.2f}\n"
            f"TOTAL DUE: Rs.{data['total_due']:.2f}"
        )
        stats_lbl = Label(text=stats, font_size=dp(14), size_hint_y=None, height=dp(100), halign='left', valign='top')
        stats_lbl.bind(size=lambda w, s: setattr(w, 'text_size', (w.width, None)))
        self.list_layout.add_widget(stats_lbl)

        btn_payment_text = "+ Add Payment" if self.mode == "customer" else "+ Pay Farmer"
        btn_payment = make_btn(btn_payment_text, 44, 13, COLOR_BUY_ENTRY)
        btn_payment.bind(on_press=lambda _: self.add_payment_popup())
        self.list_layout.add_widget(btn_payment)

        export_box = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        btn_excel = make_btn("📊 Export Excel", 44, 12, (0.2, 0.5, 0.3, 1))
        btn_pdf = make_btn("📄 Export PDF", 44, 12, (0.6, 0.25, 0.2, 1))
        btn_excel.bind(on_press=lambda _: self.do_export("excel"))
        btn_pdf.bind(on_press=lambda _: self.do_export("pdf"))
        export_box.add_widget(btn_excel)
        export_box.add_widget(btn_pdf)
        self.list_layout.add_widget(export_box)

    def add_payment_popup(self):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(6))
        box.add_widget(Label(text=f"Payment - {self.selected_name}", font_size=dp(15), bold=True))
        amt_in = make_input("Amount *", numeric=True)
        note_in = make_input("Note (optional)")
        box.add_widget(amt_in)
        box.add_widget(note_in)

        btns = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        btn_c = make_btn("CANCEL", 42, 13, (0.5, 0.5, 0.5, 1))
        btn_s = make_btn("SAVE", 42, 13, COLOR_BUY_ENTRY)
        btns.add_widget(btn_c)
        btns.add_widget(btn_s)
        box.add_widget(btns)

        pop = Popup(title="Payment", content=box, size_hint=(0.85, 0.45))
        btn_c.bind(on_press=pop.dismiss)

        def save(_):
            amt = parse_num(amt_in.text)
            if amt <= 0:
                show_popup("Error", "Valid amount daalein.")
                return
            if self.mode == "farmer":
                ok = db.save_farmer_payment(self.selected_id, amt, note_in.text.strip())
            else:
                ok = db.save_customer_payment(self.selected_id, amt, note_in.text.strip())
            if not ok:
                show_popup("Error", "Payment save nahi hua.")
                return
            pop.dismiss()
            self.render_month_report()

        btn_s.bind(on_press=save)
        pop.open()

    def do_export(self, fmt):
        try:
            import export_engine
        except Exception as e:
            show_popup("Error", f"Export module not available: {e}")
            return

        if self.mode == "farmer":
            data = db.get_farmer_month_data(self.selected_id, self.year, self.month)
            rows = db.get_farmer_month_entries(self.selected_id, self.year, self.month)
            title = "Farmer Milk Purchase Statement"
            entity_label = "Farmer"
        else:
            data = db.get_customer_month_data(self.selected_id, self.year, self.month)
            rows = db.get_customer_month_entries(self.selected_id, self.year, self.month)
            title = "Customer Milk Sale Statement"
            entity_label = "Customer"

        month_label = date(self.year, self.month, 1).strftime("%B %Y")
        safe_name = "".join(c for c in self.selected_name if c.isalnum() or c in " _-").strip().replace(" ", "_")
        filename_base = f"{self.mode}_{safe_name}_{self.year}_{self.month:02d}"

        out_dir = db.get_export_dir()
        ext = "xlsx" if fmt == "excel" else "pdf"
        output_path = os.path.join(out_dir, f"{filename_base}.{ext}")

        if fmt == "excel":
            ok, result = export_engine.export_month_excel(output_path, title, self.selected_code, self.selected_name, month_label, data, entity_label, rows)
        else:
            ok, result = export_engine.export_month_pdf(output_path, title, self.selected_code, self.selected_name, month_label, data, entity_label, rows)

        if ok:
            show_popup("Exported", f"Saved to app storage:\n{result}")
        else:
            show_popup("Export Failed", result)


# ============================================================
# 8. AI SCANNER SCREEN
# ============================================================
class ScanRegisterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.img = None
        layout = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        top = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        back = make_btn("< Back", 42, 13, COLOR_KHATA)
        back.size_hint_x = None
        back.width = dp(70)
        back.bind(on_press=lambda _: setattr(self.manager, "current", "home"))
        top.add_widget(back)
        top.add_widget(Label(text="📷 AI Scanner (Register Scan)", font_size=dp(16), bold=True, color=(0.1, 0.3, 0.1, 1)))
        layout.add_widget(top)

        if not AI_SCANNER_AVAILABLE:
            layout.add_widget(Label(text="AI Scanner module not installed in this build.", font_size=dp(13)))
        else:
            self.lbl = Label(text="No photo selected.", font_size=dp(13), size_hint_y=None, height=dp(50))
            layout.add_widget(self.lbl)
            b1 = make_btn("Choose Register Photo", 46, 14, COLOR_CUSTOMER)
            b2 = make_btn("Scan & Extract", 46, 14, COLOR_SCANNER)
            b1.bind(on_press=self.pick)
            b2.bind(on_press=self.scan)
            layout.add_widget(b1)
            layout.add_widget(b2)
        self.add_widget(layout)

    def pick(self, _):
        if PLYER_FILECHOOSER:
            try:
                filechooser.open_file(on_selection=self.on_pick, filters=[["Images", "*.jpg", "*.png"]])
            except Exception as e:
                show_popup("Error", str(e))
        else:
            show_popup("Error", "File picker not available.")

    def on_pick(self, s):
        if s:
            self.img = s[0]
            self.lbl.text = f"Selected: {os.path.basename(self.img)}"

    def scan(self, _):
        if not self.img:
            show_popup("Error", "Pehle ek photo select karein.")
            return
        self.lbl.text = "Scanning..."

        def run():
            try:
                res = scan_dairy_register(self.img)
                msg = f"Done: {res}"
            except Exception as e:
                msg = f"Failed: {e}"
            Clock.schedule_once(lambda dt: setattr(self.lbl, 'text', msg))
        threading.Thread(target=run, daemon=True).start()
