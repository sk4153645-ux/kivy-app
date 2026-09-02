# interface.py - Production UI: Clean White Theme, Dialogs, Khata Ledger, Reports
import datetime
import threading
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.utils import platform

import database as db
from auth_manager import AuthManager
from services import DairyService, ValidationError
from export_engine import ExportEngine
import dairy_ai_scanner as scanner

# Native Android Intents
def send_sms_native(phone, message):
    if not phone:
        return False, "Phone number missing"
    if platform == "android":
        try:
            from jnius import autoclass
            Uri = autoclass('android.net.Uri')
            Intent = autoclass('android.content.Intent')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')

            uri = Uri.parse(f"smsto:{phone}")
            intent = Intent(Intent.ACTION_SENDTO, uri)
            intent.putExtra("sms_body", message)
            PythonActivity.mActivity.startActivity(intent)
            return True, "SMS Opened"
        except Exception as e:
            return False, str(e)
    return True, "SMS: " + message

def send_whatsapp_native(phone, message):
    if not phone:
        return False, "Phone number missing"
    if platform == "android":
        try:
            from jnius import autoclass
            Uri = autoclass('android.net.Uri')
            Intent = autoclass('android.content.Intent')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')

            clean = phone.replace("+", "").replace(" ", "")
            if len(clean) == 10:
                clean = "91" + clean
            uri = Uri.parse(f"whatsapp://send?phone={clean}&text={Uri.encode(message)}")
            intent = Intent(Intent.ACTION_VIEW, uri)
            PythonActivity.mActivity.startActivity(intent)
            return True, "WhatsApp Opened"
        except Exception as e:
            return False, str(e)
    return True, "WhatsApp: " + message


# Header Component
class AppHeader(BoxLayout):
    def __init__(self, title="Nilgiri Dairy", back_callback=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 55
        self.padding = [8, 8]
        self.spacing = 8

        if back_callback:
            back_btn = Button(text="< Back", size_hint_x=0.25, background_color=(0.3, 0.4, 0.45, 1), color=(1, 1, 1, 1))
            back_btn.bind(on_press=back_callback)
            self.add_widget(back_btn)

        self.title_lbl = Label(text=title, font_size=18, bold=True, color=(0.1, 0.15, 0.2, 1))
        self.add_widget(self.title_lbl)

    def set_title(self, text):
        self.title_lbl.text = text


# 1. LOGIN SCREEN
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=25, spacing=15)
        layout.add_widget(Label(text="Nilgiri Dairy Collection", font_size=24, bold=True, color=(0.1, 0.5, 0.3, 1), size_hint_y=0.2))
        layout.add_widget(Label(text="Sign in to your account", font_size=14, color=(0.4, 0.4, 0.4, 1), size_hint_y=0.08))

        self.email_in = TextInput(hint_text="Email Address", multiline=False, size_hint_y=0.12)
        self.pass_in = TextInput(hint_text="Password", password=True, multiline=False, size_hint_y=0.12)
        layout.add_widget(self.email_in)
        layout.add_widget(self.pass_in)

        btn_login = Button(text="LOGIN", bold=True, background_color=(0.1, 0.6, 0.35, 1), color=(1, 1, 1, 1), size_hint_y=0.13)
        btn_login.bind(on_press=self.do_login)
        layout.add_widget(btn_login)

        btn_to_signup = Button(text="Create New Dairy Account (Sign Up)", background_color=(0.2, 0.5, 0.8, 1), color=(1, 1, 1, 1), size_hint_y=0.12)
        btn_to_signup.bind(on_press=lambda x: setattr(self.manager, 'current', 'signup'))
        layout.add_widget(btn_to_signup)
        layout.add_widget(Label(size_hint_y=0.23))
        self.add_widget(layout)

    def do_login(self, *args):
        email = self.email_in.text.strip()
        pwd = self.pass_in.text.strip()
        if not email or not pwd:
            Popup(title="Error", content=Label(text="Enter Email & Password"), size_hint=(0.8, 0.3)).open()
            return
        success, msg = AuthManager.login(email, pwd)
        if success:
            self.manager.current = "home"
        else:
            Popup(title="Login Failed", content=Label(text=msg), size_hint=(0.8, 0.3)).open()


# 2. SIGN UP SCREEN
class SignUpScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", padding=20, spacing=10)
        layout.add_widget(Label(text="Register New Dairy", font_size=20, bold=True, color=(0.1, 0.5, 0.3, 1), size_hint_y=0.12))

        self.dname_in = TextInput(hint_text="Dairy Name", multiline=False, size_hint_y=0.1)
        self.phone_in = TextInput(hint_text="Owner Phone Number", multiline=False, size_hint_y=0.1)
        self.email_in = TextInput(hint_text="Email Address", multiline=False, size_hint_y=0.1)
        self.pass_in = TextInput(hint_text="Create Password", password=True, multiline=False, size_hint_y=0.1)
        layout.add_widget(self.dname_in)
        layout.add_widget(self.phone_in)
        layout.add_widget(self.email_in)
        layout.add_widget(self.pass_in)

        btn_signup = Button(text="SIGN UP", bold=True, background_color=(0.1, 0.6, 0.35, 1), color=(1, 1, 1, 1), size_hint_y=0.12)
        btn_signup.bind(on_press=self.do_signup)
        layout.add_widget(btn_signup)

        btn_to_login = Button(text="Already have an account? Login", background_color=(0.4, 0.4, 0.4, 1), color=(1, 1, 1, 1), size_hint_y=0.1)
        btn_to_login.bind(on_press=lambda x: setattr(self.manager, 'current', 'login'))
        layout.add_widget(btn_to_login)
        layout.add_widget(Label(size_hint_y=0.28))
        self.add_widget(layout)

    def do_signup(self, *args):
        dname = self.dname_in.text.strip()
        phone = self.phone_in.text.strip()
        email = self.email_in.text.strip()
        pwd = self.pass_in.text.strip()
        if not dname or not email or not pwd:
            Popup(title="Error", content=Label(text="All fields required!"), size_hint=(0.8, 0.3)).open()
            return
        success, msg = AuthManager.sign_up(email, pwd, dname, phone)
        if success:
            Popup(title="Success", content=Label(text="Account Created!"), size_hint=(0.8, 0.3)).open()
            self.manager.current = "home"
        else:
            Popup(title="Sign Up Error", content=Label(text=msg), size_hint=(0.8, 0.3)).open()


# 3. HOME SCREEN
class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.root_box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        self.header = AppHeader(title="Nilgiri Dairy Collection")
        self.root_box.add_widget(self.header)

        grid = GridLayout(cols=2, spacing=10, size_hint_y=0.88)
        grid.add_widget(self.make_btn("Buy Milk Entry\n(Kisan Doodh)", (0.12, 0.65, 0.38, 1), 'buy_milk'))
        grid.add_widget(self.make_btn("Today's Milk\n(Aaj Ka Doodh)", (0.12, 0.55, 0.45, 1), 'collection_list'))
        grid.add_widget(self.make_btn("Farmers & Khata\n(Kisan Ledger)", (0.2, 0.45, 0.7, 1), 'farmers'))
        grid.add_widget(self.make_btn("AI Scanner\n(Register Scan)", (0.9, 0.5, 0.1, 1), 'scan_register'))
        grid.add_widget(self.make_btn("Sell Milk Entry\n(Grahak Bikri)", (0.15, 0.6, 0.6, 1), 'daily_entry'))
        grid.add_widget(self.make_btn("Customers\n(Grahak List)", (0.35, 0.45, 0.65, 1), 'customers'))
        grid.add_widget(self.make_btn("Full Reports\n& Statements", (0.3, 0.5, 0.45, 1), 'reports'))
        grid.add_widget(self.make_btn("Settings &\nHardware", (0.25, 0.35, 0.45, 1), 'settings'))

        self.root_box.add_widget(grid)
        self.add_widget(self.root_box)

    def make_btn(self, text, color, screen_name):
        b = Button(text=text, background_color=color, color=(1, 1, 1, 1), halign="center")
        b.bind(on_press=lambda x: setattr(self.manager, 'current', screen_name))
        return b

    def on_pre_enter(self, *args):
        self.header.set_title(db.get_setting("dairy_name", "Nilgiri Dairy Collection"))


# 4. BUY MILK SCREEN (Validation, Khata Balance & 4 Active Action Buttons)
class BuyMilkScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_saved_entry = None

        layout = BoxLayout(orientation="vertical", spacing=8, padding=10)
        layout.add_widget(AppHeader(title="Buy Milk Entry", back_callback=lambda x: setattr(self.manager, 'current', 'home')))

        # Shift
        shift_box = BoxLayout(size_hint_y=0.08, spacing=8)
        self.shift = "Morning"
        self.btn_morn = Button(text="Morning", background_color=(0.1, 0.5, 0.8, 1), color=(1, 1, 1, 1))
        self.btn_eve = Button(text="Evening", background_color=(0.7, 0.7, 0.7, 1), color=(1, 1, 1, 1))
        self.btn_morn.bind(on_press=lambda x: self.set_shift("Morning"))
        self.btn_eve.bind(on_press=lambda x: self.set_shift("Evening"))
        shift_box.add_widget(self.btn_morn)
        shift_box.add_widget(self.btn_eve)
        layout.add_widget(shift_box)

        # Farmer Code & Details
        self.code_in = TextInput(hint_text="Farmer Code (e.g. 01)", multiline=False, size_hint_y=0.09)
        self.code_in.bind(text=self.lookup_farmer)
        layout.add_widget(self.code_in)
        self.farmer_lbl = Label(text="Farmer: Not Selected | Khata: Rs.0.00", color=(0.2, 0.4, 0.8, 1), size_hint_y=0.06, bold=True)
        layout.add_widget(self.farmer_lbl)

        # Milk Type
        mtype_box = BoxLayout(size_hint_y=0.08, spacing=8)
        self.milk_type = "Cow"
        self.btn_cow = Button(text="Cow", background_color=(0.1, 0.6, 0.35, 1), color=(1, 1, 1, 1))
        self.btn_buff = Button(text="Buffalo", background_color=(0.7, 0.7, 0.7, 1), color=(1, 1, 1, 1))
        self.btn_cow.bind(on_press=lambda x: self.set_milk_type("Cow"))
        self.btn_buff.bind(on_press=lambda x: self.set_milk_type("Buffalo"))
        mtype_box.add_widget(self.btn_cow)
        mtype_box.add_widget(self.btn_buff)
        layout.add_widget(mtype_box)

        # Quantity Inputs
        self.litres_in = TextInput(hint_text="Litres *", multiline=False, size_hint_y=0.09)
        self.litres_in.bind(text=self.recalculate)
        layout.add_widget(self.litres_in)

        fat_snf_box = BoxLayout(size_hint_y=0.09, spacing=8)
        self.fat_in = TextInput(hint_text="Fat % (Optional)", multiline=False)
        self.fat_in.bind(text=self.recalculate)
        self.snf_in = TextInput(hint_text="SNF/CLR (Optional)", multiline=False)
        self.snf_in.bind(text=self.recalculate)
        fat_snf_box.add_widget(self.fat_in)
        fat_snf_box.add_widget(self.snf_in)
        layout.add_widget(fat_snf_box)

        self.rate_in = TextInput(hint_text="Rate (Rs/L) *", multiline=False, size_hint_y=0.09)
        self.rate_in.bind(text=self.recalculate)
        layout.add_widget(self.rate_in)

        self.total_lbl = Label(text="TOTAL: Rs. 0.00", font_size=20, bold=True, color=(0.1, 0.5, 0.3, 1), size_hint_y=0.08)
        layout.add_widget(self.total_lbl)

        # 4 Action Buttons
        grid = GridLayout(cols=2, spacing=8, size_hint_y=0.22)
        self.btn_save = Button(text="[+] SAVE ENTRY", bold=True, background_color=(0.1, 0.6, 0.35, 1), color=(1, 1, 1, 1))
        self.btn_save.bind(on_press=self.confirm_and_save)
        grid.add_widget(self.btn_save)

        self.btn_print = Button(text="PRINT RECEIPT", bold=True, background_color=(0.2, 0.45, 0.7, 1), color=(1, 1, 1, 1))
        self.btn_print.bind(on_press=self.print_receipt)
        grid.add_widget(self.btn_print)

        self.btn_whatsapp = Button(text="WHATSAPP", bold=True, background_color=(0.15, 0.65, 0.4, 1), color=(1, 1, 1, 1))
        self.btn_whatsapp.bind(on_press=self.send_whatsapp)
        grid.add_widget(self.btn_whatsapp)

        self.btn_sms = Button(text="SEND SMS", bold=True, background_color=(0.85, 0.45, 0.1, 1), color=(1, 1, 1, 1))
        self.btn_sms.bind(on_press=self.send_sms)
        grid.add_widget(self.btn_sms)

        layout.add_widget(grid)
        self.add_widget(layout)

    def set_shift(self, s):
        self.shift = s
        self.btn_morn.background_color = (0.1, 0.5, 0.8, 1) if s == "Morning" else (0.7, 0.7, 0.7, 1)
        self.btn_eve.background_color = (0.1, 0.5, 0.8, 1) if s == "Evening" else (0.7, 0.7, 0.7, 1)

    def set_milk_type(self, t):
        self.milk_type = t
        self.btn_cow.background_color = (0.1, 0.6, 0.35, 1) if t == "Cow" else (0.7, 0.7, 0.7, 1)
        self.btn_buff.background_color = (0.1, 0.6, 0.35, 1) if t == "Buffalo" else (0.7, 0.7, 0.7, 1)
        self.recalculate()

    def lookup_farmer(self, *args):
        code = self.code_in.text.strip()
        conn = db.get_db()
        f = conn.execute("SELECT * FROM farmers WHERE code = ?", (code,)).fetchone()
        conn.close()
        if f:
            balance = db.get_farmer_khata_balance(code)
            self.farmer_lbl.text = f"Farmer: [{f['code']}] {f['name']} | Khata: Rs.{balance:.2f}"
            if f["rate_type"] == "fixed" and f["fixed_rate"] > 0:
                self.rate_in.text = str(f["fixed_rate"])
        else:
            self.farmer_lbl.text = "Farmer: Not Found | Khata: Rs.0.00"

    def recalculate(self, *args):
        try:
            litres = float(self.litres_in.text or 0)
            rate = float(self.rate_in.text or 0)
            self.total_lbl.text = f"TOTAL: Rs. {litres * rate:.2f}"
        except ValueError:
            self.total_lbl.text = "TOTAL: Invalid Input"

    def confirm_and_save(self, *args):
        try:
            code = self.code_in.text.strip()
            litres = self.litres_in.text.strip()
            rate = self.rate_in.text.strip()
            fat = self.fat_in.text.strip()
            snf = self.snf_in.text.strip()

            entry_id, total = DairyService.save_milk_entry(
                code, self.shift, self.milk_type, litres, fat, snf, rate
            )

            self.last_saved_entry = {
                "id": entry_id, "date": datetime.date.today().isoformat(), "shift": self.shift,
                "code": code, "milk_type": self.milk_type, "litres": litres,
                "fat": fat, "snf": snf, "rate": rate, "total": total
            }
            new_bal = db.get_farmer_khata_balance(code)
            self.farmer_lbl.text = f"Farmer: [{code}] Saved! | New Khata: Rs.{new_bal:.2f}"
            Popup(title="Success", content=Label(text=f"Entry Saved: Rs.{total}"), size_hint=(0.7, 0.25)).open()
        except ValidationError as ve:
            Popup(title="Validation Error", content=Label(text=str(ve)), size_hint=(0.8, 0.3)).open()
        except Exception as e:
            Popup(title="Error", content=Label(text=f"Failed: {str(e)}"), size_hint=(0.8, 0.3)).open()

    def format_receipt_msg(self):
        e = self.last_saved_entry
        dname = db.get_setting("dairy_name", "Nilgiri Dairy")
        return (
            f"*{dname}*\n"
            f"Date: {e['date']} ({e['shift']})\n"
            f"Farmer: [{e['code']}] | Type: {e['milk_type']}\n"
            f"Weight: {e['litres']} L | Rate: Rs.{e['rate']}\n"
            f"Fat: {e['fat']}% | SNF: {e['snf']}\n"
            f"*Total: Rs.{e['total']}*\nThank you!"
        )

    def print_receipt(self, *args):
        if not self.last_saved_entry:
            Popup(title="Print", content=Label(text="Save an entry first!"), size_hint=(0.7, 0.25)).open()
            return
        mac = db.get_setting("printer_mac")
        msg = f"Sent to Printer: {mac}" if mac else "Please set Printer MAC in Settings"
        Popup(title="Printer Status", content=Label(text=msg), size_hint=(0.8, 0.3)).open()

    def send_whatsapp(self, *args):
        if not self.last_saved_entry:
            Popup(title="WhatsApp", content=Label(text="Save an entry first!"), size_hint=(0.7, 0.25)).open()
            return
        conn = db.get_db()
        f = conn.execute("SELECT phone FROM farmers WHERE code = ?", (self.last_saved_entry["code"],)).fetchone()
        conn.close()
        send_whatsapp_native(f["phone"] if f else "", self.format_receipt_msg())

    def send_sms(self, *args):
        if not self.last_saved_entry:
            Popup(title="SMS", content=Label(text="Save an entry first!"), size_hint=(0.7, 0.25)).open()
            return
        conn = db.get_db()
        f = conn.execute("SELECT phone FROM farmers WHERE code = ?", (self.last_saved_entry["code"],)).fetchone()
        conn.close()
        send_sms_native(f["phone"] if f else "", self.format_receipt_msg())


# 5. TODAY'S MILK SCREEN (Pali Summary & Edit/Delete Action)
class CollectionListScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", spacing=8, padding=10)
        layout.add_widget(AppHeader(title="Today's Shift Collection", back_callback=lambda x: setattr(self.manager, 'current', 'home')))

        shift_bar = BoxLayout(size_hint_y=0.08, spacing=8)
        self.shift = "Morning"
        self.btn_m = Button(text="Morning", background_color=(0.1, 0.5, 0.8, 1), color=(1, 1, 1, 1))
        self.btn_e = Button(text="Evening", background_color=(0.7, 0.7, 0.7, 1), color=(1, 1, 1, 1))
        self.btn_m.bind(on_press=lambda x: self.load_data("Morning"))
        self.btn_e.bind(on_press=lambda x: self.load_data("Evening"))
        shift_bar.add_widget(self.btn_m)
        shift_bar.add_widget(self.btn_e)
        layout.add_widget(shift_bar)

        # Split Summary Cards
        cards = BoxLayout(orientation="vertical", size_hint_y=0.32, spacing=5)
        self.cow_card = Label(text="Cow: 0.0 L | Avg Fat: 0.0 | Rs.0.00", color=(0.1, 0.5, 0.2, 1), bold=True)
        self.buff_card = Label(text="Buffalo: 0.0 L | Avg Fat: 0.0 | Rs.0.00", color=(0.1, 0.3, 0.7, 1), bold=True)
        self.grand_card = Label(text="Grand Total: 0.0 L | Rs.0.00", color=(0.8, 0.3, 0.1, 1), font_size=16, bold=True)
        cards.add_widget(self.cow_card)
        cards.add_widget(self.buff_card)
        cards.add_widget(self.grand_card)
        layout.add_widget(cards)

        self.scroll = ScrollView(size_hint_y=0.52)
        self.list_box = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter('height'))
        self.scroll.add_widget(self.list_box)
        layout.add_widget(self.scroll)

        self.add_widget(layout)

    def on_pre_enter(self, *args):
        self.load_data(self.shift)

    def load_data(self, shift):
        self.shift = shift
        self.btn_m.background_color = (0.1, 0.5, 0.8, 1) if shift == "Morning" else (0.7, 0.7, 0.7, 1)
        self.btn_e.background_color = (0.1, 0.5, 0.8, 1) if shift == "Evening" else (0.7, 0.7, 0.7, 1)

        date_today = datetime.date.today().isoformat()
        summary = db.get_shift_summary(date_today, shift)
        c = summary["Cow"]
        b = summary["Buffalo"]
        self.cow_card.text = f"Cow Milk: {c['litres']} L | Avg Fat: {c['avg_fat']}% | Rs.{c['amount']}"
        self.buff_card.text = f"Buffalo Milk: {b['litres']} L | Avg Fat: {b['avg_fat']}% | Rs.{b['amount']}"
        self.grand_card.text = f"Grand Total: {c['litres'] + b['litres']:.2f} L | Total: Rs.{c['amount'] + b['amount']:.2f}"

        self.list_box.clear_widgets()
        conn = db.get_db()
        rows = conn.execute("SELECT * FROM milk_purchases WHERE date = ? AND shift = ? ORDER BY id DESC", (date_today, shift)).fetchall()
        conn.close()

        for r in rows:
            box = BoxLayout(size_hint_y=None, height=40, spacing=8)
            info = Label(text=f"[{r['farmer_code']}] {r['milk_type']} {r['litres']}L @ Rs.{r['rate']} = Rs.{r['total_amount']}", color=(0.15, 0.15, 0.15, 1), size_hint_x=0.75)
            btn_del = Button(text="Delete", background_color=(0.85, 0.2, 0.2, 1), color=(1, 1, 1, 1), size_hint_x=0.25)
            btn_del.bind(on_press=lambda x, eid=r['id']: self.confirm_delete(eid))
            box.add_widget(info)
            box.add_widget(btn_del)
            self.list_box.add_widget(box)

    def confirm_delete(self, entry_id):
        content = BoxLayout(orientation="vertical", spacing=10, padding=10)
        content.add_widget(Label(text="Delete this entry permanently?"))
        btn_box = BoxLayout(spacing=8, size_hint_y=0.4)
        pop = Popup(title="Confirm Delete", content=content, size_hint=(0.8, 0.3))

        btn_yes = Button(text="YES, DELETE", background_color=(0.8, 0.2, 0.2, 1), color=(1, 1, 1, 1))
        def do_del(x):
            DairyService.delete_milk_entry(entry_id)
            pop.dismiss()
            self.load_data(self.shift)
        btn_yes.bind(on_press=do_del)

        btn_no = Button(text="CANCEL")
        btn_no.bind(on_press=pop.dismiss)
        btn_box.add_widget(btn_yes)
        btn_box.add_widget(btn_no)
        content.add_widget(btn_box)
        pop.open()


# 6. FARMERS MASTER & RUNNING KHATA SETTLEMENT
class FarmersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", spacing=8, padding=10)
        layout.add_widget(AppHeader(title="Farmers & Khata", back_callback=lambda x: setattr(self.manager, 'current', 'home')))

        add_box = BoxLayout(size_hint_y=0.1, spacing=6)
        self.code_in = TextInput(hint_text="Code *", multiline=False, size_hint_x=0.25)
        self.name_in = TextInput(hint_text="Name *", multiline=False, size_hint_x=0.45)
        self.phone_in = TextInput(hint_text="Phone", multiline=False, size_hint_x=0.3)
        add_box.add_widget(self.code_in)
        add_box.add_widget(self.name_in)
        add_box.add_widget(self.phone_in)
        layout.add_widget(add_box)

        btn_add = Button(text="+ Add New Farmer", background_color=(0.1, 0.6, 0.35, 1), color=(1, 1, 1, 1), size_hint_y=0.08)
        btn_add.bind(on_press=self.add_farmer)
        layout.add_widget(btn_add)

        btn_settle = Button(text="💰 Settle Khata Payment (Cash / Online)", background_color=(0.2, 0.45, 0.7, 1), color=(1, 1, 1, 1), size_hint_y=0.08)
        btn_settle.bind(on_press=self.open_settlement_popup)
        layout.add_widget(btn_settle)

        self.scroll = ScrollView(size_hint_y=0.74)
        self.list_box = GridLayout(cols=1, spacing=6, size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter('height'))
        self.scroll.add_widget(self.list_box)
        layout.add_widget(self.scroll)

        self.add_widget(layout)

    def on_pre_enter(self, *args):
        self.refresh_list()

    def add_farmer(self, *args):
        code = self.code_in.text.strip()
        name = self.name_in.text.strip()
        phone = self.phone_in.text.strip()
        if not code or not name:
            Popup(title="Error", content=Label(text="Code and Name required"), size_hint=(0.8, 0.3)).open()
            return
        conn = db.get_db()
        try:
            with conn:
                conn.execute("INSERT INTO farmers (code, name, phone) VALUES (?, ?, ?)", (code, name, phone))
            self.code_in.text = ""
            self.name_in.text = ""
            self.phone_in.text = ""
            self.refresh_list()
        except sqlite3.IntegrityError:
            Popup(title="Duplicate Code", content=Label(text="Farmer code already exists!"), size_hint=(0.8, 0.3)).open()
        finally:
            conn.close()

    def refresh_list(self):
        self.list_box.clear_widgets()
        conn = db.get_db()
        farmers = conn.execute("SELECT * FROM farmers ORDER BY CAST(code AS INTEGER) ASC").fetchall()
        conn.close()
        for f in farmers:
            bal = db.get_farmer_khata_balance(f['code'])
            lbl = Label(text=f"[{f['code']}] {f['name']} | Khata Balance: Rs.{bal:.2f}", size_hint_y=None, height=35, color=(0.15, 0.15, 0.15, 1))
            self.list_box.add_widget(lbl)

    def open_settlement_popup(self, *args):
        content = BoxLayout(orientation="vertical", spacing=10, padding=10)
        code_input = TextInput(hint_text="Farmer Code", multiline=False, size_hint_y=0.18)
        amt_input = TextInput(hint_text="Settlement Amount (Rs)", multiline=False, size_hint_y=0.18)

        mode_box = BoxLayout(size_hint_y=0.18, spacing=8)
        mode = ["Cash"]
        btn_c = Button(text="Cash", background_color=(0.1, 0.6, 0.35, 1), color=(1, 1, 1, 1))
        btn_o = Button(text="Online (UPI/Bank)", background_color=(0.7, 0.7, 0.7, 1), color=(1, 1, 1, 1))
        def set_m(m):
            mode[0] = m
            btn_c.background_color = (0.1, 0.6, 0.35, 1) if m == "Cash" else (0.7, 0.7, 0.7, 1)
            btn_o.background_color = (0.1, 0.6, 0.35, 1) if m == "Online" else (0.7, 0.7, 0.7, 1)
        btn_c.bind(on_press=lambda x: set_m("Cash"))
        btn_o.bind(on_press=lambda x: set_m("Online"))
        mode_box.add_widget(btn_c)
        mode_box.add_widget(btn_o)

        content.add_widget(code_input)
        content.add_widget(amt_input)
        content.add_widget(mode_box)

        pop = Popup(title="Settle Farmer Khata", content=content, size_hint=(0.85, 0.5))
        btn_confirm = Button(text="Confirm Payment & SMS", background_color=(0.1, 0.6, 0.35, 1), color=(1, 1, 1, 1), size_hint_y=0.22)

        def do_pay(x):
            try:
                name, phone, amt = DairyService.settle_farmer_payment(code_input.text, amt_input.text, mode[0])
                pop.dismiss()
                self.refresh_list()
                new_bal = db.get_farmer_khata_balance(code_input.text.strip())
                msg = f"*{db.get_setting('dairy_name')}*\nPayment Paid: Rs.{amt:.2f} ({mode[0]})\nFarmer: {name}\nBalance Due: Rs.{new_bal:.2f}"
                send_sms_native(phone, msg)
                Popup(title="Settled", content=Label(text=f"Payment recorded! New Balance: Rs.{new_bal:.2f}"), size_hint=(0.8, 0.3)).open()
            except ValidationError as ve:
                Popup(title="Validation Error", content=Label(text=str(ve)), size_hint=(0.8, 0.3)).open()

        btn_confirm.bind(on_press=do_pay)
        content.add_widget(btn_confirm)
        pop.open()


# 7. CUSTOMERS SCREEN (No Milk Type)
class CustomersScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", spacing=8, padding=10)
        layout.add_widget(AppHeader(title="Retail Customers", back_callback=lambda x: setattr(self.manager, 'current', 'home')))

        add_box = BoxLayout(size_hint_y=0.1, spacing=6)
        self.code_in = TextInput(hint_text="Code *", multiline=False, size_hint_x=0.25)
        self.name_in = TextInput(hint_text="Name *", multiline=False, size_hint_x=0.45)
        self.phone_in = TextInput(hint_text="Phone", multiline=False, size_hint_x=0.3)
        add_box.add_widget(self.code_in)
        add_box.add_widget(self.name_in)
        add_box.add_widget(self.phone_in)
        layout.add_widget(add_box)

        btn_add = Button(text="+ Add Customer", background_color=(0.15, 0.6, 0.6, 1), color=(1, 1, 1, 1), size_hint_y=0.08)
        btn_add.bind(on_press=self.add_customer)
        layout.add_widget(btn_add)

        self.scroll = ScrollView(size_hint_y=0.82)
        self.list_box = GridLayout(cols=1, spacing=6, size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter('height'))
        self.scroll.add_widget(self.list_box)
        layout.add_widget(self.scroll)

        self.add_widget(layout)

    def on_pre_enter(self, *args):
        self.refresh_list()

    def add_customer(self, *args):
        code = self.code_in.text.strip()
        name = self.name_in.text.strip()
        phone = self.phone_in.text.strip()
        if not code or not name:
            return
        conn = db.get_db()
        try:
            with conn:
                conn.execute("INSERT INTO customers (code, name, phone) VALUES (?, ?, ?)", (code, name, phone))
            self.code_in.text = ""
            self.name_in.text = ""
            self.phone_in.text = ""
            self.refresh_list()
        except sqlite3.IntegrityError:
            Popup(title="Error", content=Label(text="Customer Code exists!"), size_hint=(0.8, 0.3)).open()
        finally:
            conn.close()

    def refresh_list(self):
        self.list_box.clear_widgets()
        conn = db.get_db()
        rows = conn.execute("SELECT * FROM customers ORDER BY CAST(code AS INTEGER) ASC").fetchall()
        conn.close()
        for c in rows:
            self.list_box.add_widget(Label(text=f"[{c['code']}] {c['name']} | Phone: {c['phone']}", size_hint_y=None, height=35, color=(0.15, 0.15, 0.15, 1)))


# 8. DAILY ENTRY (Retail Sales with Cow/Buffalo Toggle)
class DailyEntryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", spacing=8, padding=10)
        layout.add_widget(AppHeader(title="Sell Milk (Grahak Bikri)", back_callback=lambda x: setattr(self.manager, 'current', 'home')))

        self.code_in = TextInput(hint_text="Customer Code", multiline=False, size_hint_y=0.1)
        layout.add_widget(self.code_in)

        m_box = BoxLayout(size_hint_y=0.1, spacing=8)
        self.sale_mtype = "Cow"
        self.btn_c = Button(text="Cow", background_color=(0.1, 0.6, 0.35, 1), color=(1, 1, 1, 1))
        self.btn_b = Button(text="Buffalo", background_color=(0.7, 0.7, 0.7, 1), color=(1, 1, 1, 1))
        def set_t(t):
            self.sale_mtype = t
            self.btn_c.background_color = (0.1, 0.6, 0.35, 1) if t == "Cow" else (0.7, 0.7, 0.7, 1)
            self.btn_b.background_color = (0.1, 0.6, 0.35, 1) if t == "Buffalo" else (0.7, 0.7, 0.7, 1)
        self.btn_c.bind(on_press=lambda x: set_t("Cow"))
        self.btn_b.bind(on_press=lambda x: set_t("Buffalo"))
        m_box.add_widget(self.btn_c)
        m_box.add_widget(self.btn_b)
        layout.add_widget(m_box)

        self.litres_in = TextInput(hint_text="Litres Sold *", multiline=False, size_hint_y=0.1)
        self.rate_in = TextInput(hint_text="Rate / L (Rs) *", multiline=False, size_hint_y=0.1)
        layout.add_widget(self.litres_in)
        layout.add_widget(self.rate_in)

        btn_save = Button(text="RECORD SALE", bold=True, background_color=(0.15, 0.6, 0.6, 1), color=(1, 1, 1, 1), size_hint_y=0.12)
        btn_save.bind(on_press=self.save_sale)
        layout.add_widget(btn_save)

        layout.add_widget(Label(size_hint_y=0.48))
        self.add_widget(layout)

    def save_sale(self, *args):
        code = self.code_in.text.strip()
        try:
            litres = float(self.litres_in.text)
            rate = float(self.rate_in.text)
            total = round(litres * rate, 2)
        except ValueError:
            Popup(title="Error", content=Label(text="Enter valid numeric values!"), size_hint=(0.8, 0.3)).open()
            return
        conn = db.get_db()
        with conn:
            conn.execute('''
                INSERT INTO retail_sales (date, shift, customer_code, milk_type, litres, rate, total_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (datetime.date.today().isoformat(), "Morning", code, self.sale_mtype, litres, rate, total))
        conn.close()
        Popup(title="Success", content=Label(text=f"Sale Recorded: Rs.{total}"), size_hint=(0.8, 0.3)).open()


# 9. AI SCANNER SCREEN (Threaded Non-blocking OCR)
class ScanRegisterScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", spacing=10, padding=10)
        layout.add_widget(AppHeader(title="AI Register Scanner", back_callback=lambda x: setattr(self.manager, 'current', 'home')))

        self.status_lbl = Label(text="Select image from device storage to scan", color=(0.2, 0.2, 0.2, 1), size_hint_y=0.15)
        layout.add_widget(self.status_lbl)

        btn_pick = Button(text="📁 Choose Image Path", background_color=(0.2, 0.5, 0.7, 1), color=(1, 1, 1, 1), size_hint_y=0.12)
        btn_pick.bind(on_press=self.pick_sample)
        layout.add_widget(btn_pick)

        self.btn_run = Button(text="⚡ Process & Import to Database", background_color=(0.9, 0.5, 0.1, 1), color=(1, 1, 1, 1), size_hint_y=0.12)
        self.btn_run.bind(on_press=self.start_ocr_thread)
        layout.add_widget(self.btn_run)

        self.scroll = ScrollView(size_hint_y=0.61)
        self.result_box = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.result_box.bind(minimum_height=self.result_box.setter('height'))
        self.scroll.add_widget(self.result_box)
        layout.add_widget(self.scroll)

        self.selected_path = "register_sample.jpg"
        self.add_widget(layout)

    def pick_sample(self, *args):
        self.status_lbl.text = f"Selected: {self.selected_path}"

    def start_ocr_thread(self, *args):
        self.status_lbl.text = "Processing image in background..."
        threading.Thread(target=self._ocr_worker, daemon=True).start()

    def _ocr_worker(self):
        success, res = scanner.process_dairy_register_image(self.selected_path)
        if not success:
            self.status_lbl.text = f"Scan Note: {res}"
            return

        conn = db.get_db()
        count = 0
        date_today = datetime.date.today().isoformat()
        with conn:
            for item in res:
                try:
                    code = str(item.get("code", "01"))
                    litres = float(item.get("litres", 0.0))
                    fat = float(item.get("fat", 4.0))
                    snf = float(item.get("snf", 8.5))
                    mtype = item.get("milk_type", "Cow")
                    rate = 40.0
                    conn.execute('''
                        INSERT INTO milk_purchases (date, shift, farmer_code, milk_type, litres, fat, snf, rate, total_amount)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (date_today, "Morning", code, mtype, litres, fat, snf, rate, round(litres * rate, 2)))
                    count += 1
                except:
                    pass
        conn.close()
        self.status_lbl.text = f"Imported {count} entries successfully!"


# 10. SETTINGS SCREEN
class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", spacing=10, padding=12)
        layout.add_widget(AppHeader(title="Settings & Hardware", back_callback=lambda x: setattr(self.manager, 'current', 'home')))

        layout.add_widget(Label(text="Dairy Profile Name (Header & Receipts)", bold=True, color=(0.2, 0.2, 0.2, 1), size_hint_y=0.06))
        self.dname_in = TextInput(hint_text="Dairy Name", multiline=False, size_hint_y=0.09)
        self.dphone_in = TextInput(hint_text="Dairy Phone Number", multiline=False, size_hint_y=0.09)
        layout.add_widget(self.dname_in)
        layout.add_widget(self.dphone_in)

        layout.add_widget(Label(text="Bluetooth Thermal Printer MAC", bold=True, color=(0.2, 0.2, 0.2, 1), size_hint_y=0.06))
        self.mac_in = TextInput(hint_text="e.g. 00:11:22:33:44:55", multiline=False, size_hint_y=0.09)
        layout.add_widget(self.mac_in)

        btn_save = Button(text="SAVE SETTINGS", bold=True, background_color=(0.1, 0.6, 0.35, 1), color=(1, 1, 1, 1), size_hint_y=0.12)
        btn_save.bind(on_press=self.save_settings)
        layout.add_widget(btn_save)

        btn_logout = Button(text="Logout from Device", background_color=(0.8, 0.2, 0.2, 1), color=(1, 1, 1, 1), size_hint_y=0.1)
        btn_logout.bind(on_press=self.logout)
        layout.add_widget(btn_logout)

        layout.add_widget(Label(size_hint_y=0.39))
        self.add_widget(layout)

    def on_pre_enter(self, *args):
        self.dname_in.text = db.get_setting("dairy_name")
        self.dphone_in.text = db.get_setting("dairy_phone")
        self.mac_in.text = db.get_setting("printer_mac")

    def save_settings(self, *args):
        db.save_setting("dairy_name", self.dname_in.text.strip())
        db.save_setting("dairy_phone", self.dphone_in.text.strip())
        db.save_setting("printer_mac", self.mac_in.text.strip())
        Popup(title="Success", content=Label(text="Settings Updated!"), size_hint=(0.7, 0.25)).open()

    def logout(self, *args):
        AuthManager.logout()
        self.manager.current = "login"


# 11. REPORTS & EXPORTS SCREEN (Phase 3 Complete)
class ReportsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation="vertical", spacing=10, padding=12)
        layout.add_widget(AppHeader(title="Reports & Statements", back_callback=lambda x: setattr(self.manager, 'current', 'home')))

        self.fcode_in = TextInput(hint_text="Farmer Code for Statement (e.g. 01)", multiline=False, size_hint_y=0.1)
        layout.add_widget(self.fcode_in)

        btn_pdf = Button(text="📄 Export Farmer Statement (PDF)", background_color=(0.2, 0.5, 0.7, 1), color=(1, 1, 1, 1), size_hint_y=0.12)
        btn_pdf.bind(on_press=self.export_pdf)
        layout.add_widget(btn_pdf)

        btn_excel = Button(text="📊 Export Full Dairy Ledger (Excel)", background_color=(0.1, 0.6, 0.35, 1), color=(1, 1, 1, 1), size_hint_y=0.12)
        btn_excel.bind(on_press=self.export_excel)
        layout.add_widget(btn_excel)

        self.status_lbl = Label(text="Export files to device storage", color=(0.3, 0.3, 0.3, 1), size_hint_y=0.66)
        layout.add_widget(self.status_lbl)
        self.add_widget(layout)

    def export_pdf(self, *args):
        code = self.fcode_in.text.strip()
        if not code:
            Popup(title="Error", content=Label(text="Enter Farmer Code"), size_hint=(0.7, 0.25)).open()
            return
        today = datetime.date.today()
        start = today.replace(day=1).isoformat()
        end = today.isoformat()
        out_name = f"Farmer_{code}_Statement.pdf"
        ok, path = ExportEngine.generate_farmer_monthly_pdf(code, start, end, out_name)
        if ok:
            self.status_lbl.text = f"PDF Saved: {os.path.abspath(path)}"
            Popup(title="Exported", content=Label(text=f"Saved to: {path}"), size_hint=(0.8, 0.3)).open()
        else:
            Popup(title="Failed", content=Label(text=path), size_hint=(0.8, 0.3)).open()

    def export_excel(self, *args):
        ok, path = ExportEngine.generate_excel_report("Dairy_Master_Report.xlsx")
        if ok:
            self.status_lbl.text = f"Excel Saved: {os.path.abspath(path)}"
            Popup(title="Exported", content=Label(text=f"Saved to: {path}"), size_hint=(0.8, 0.3)).open()
