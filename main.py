# main.py - App Launcher, Android Runtime Permissions & Screen Registry
import os
from kivy.app import App
from kivy.utils import platform
from kivy.uix.screenmanager import ScreenManager

import database as db
from interface import (
    HomeScreen, BuyMilkScreen, CollectionListScreen,
    FarmersScreen, DailyEntryScreen, CustomersScreen,
    SettingsScreen, ReportsScreen, ScanRegisterScreen
)


class NilgiriDairyApp(App):
    def build(self):
        self.title = "Nilgiri Dairy Collection"

        # Android Runtime Permissions (Bluetooth, SMS, Camera, Storage)
        if platform == "android":
            self.request_android_permissions()

        # Database Tables & Default Setup
        db.init_db()

        # Screen Manager & Registry
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(BuyMilkScreen(name="buy_milk"))
        sm.add_widget(CollectionListScreen(name="collection_list"))
        sm.add_widget(FarmersScreen(name="farmers"))
        sm.add_widget(DailyEntryScreen(name="daily_entry"))
        sm.add_widget(CustomersScreen(name="customers"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(ReportsScreen(name="reports"))
        sm.add_widget(ScanRegisterScreen(name="scan_register"))

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
