# main.py - App Launcher, Softinput Pan, Auth Router & Permissions
import os
from kivy.app import App
from kivy.core.window import Window
from kivy.utils import platform
from kivy.uix.screenmanager import ScreenManager

# Android Keyboard Soft-Input Auto Pan Fix (Keyboard ke peeche slot nahi chupega)
Window.softinput_mode = "below_target"
Window.clearcolor = (0.96, 0.97, 0.98, 1)

import database as db
from interface import (
    LoginScreen, SignUpScreen, HomeScreen, BuyMilkScreen,
    CollectionListScreen, FarmersScreen, DailyEntryScreen,
    CustomersScreen, SettingsScreen, ReportsScreen, ScanRegisterScreen
)


class NilgiriDairyApp(App):
    def build(self):
        self.title = "Nilgiri Dairy Collection"

        # Android Runtime Permissions
        if platform == "android":
            self.request_android_permissions()

        # Database Tables & Default Setup
        db.init_db()

        # Screen Manager & Registry
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(SignUpScreen(name="signup"))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(BuyMilkScreen(name="buy_milk"))
        sm.add_widget(CollectionListScreen(name="collection_list"))
        sm.add_widget(FarmersScreen(name="farmers"))
        sm.add_widget(DailyEntryScreen(name="daily_entry"))
        sm.add_widget(CustomersScreen(name="customers"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(ReportsScreen(name="reports"))
        sm.add_widget(ScanRegisterScreen(name="scan_register"))

        # Smart Session Routing (Pehle se login hai to seedha Home, nahi to Login)
        try:
            if db.is_user_logged_in():
                sm.current = "home"
            else:
                sm.current = "login"
        except Exception:
            sm.current = "login"

        return sm

    def request_android_permissions(self):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.INTERNET,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.CAMERA,
                Permission.BLUETOOTH,
                Permission.BLUETOOTH_ADMIN,
                Permission.BLUETOOTH_CONNECT,
                Permission.BLUETOOTH_SCAN,
                Permission.SEND_SMS
            ])
        except Exception as e:
            print(f"Android Permissions Error: {e}")


if __name__ == "__main__":
    NilgiriDairyApp().run()
    
