# auth_manager.py - Supabase Cloud Auth & Session Management
import requests
import json
import database as db

SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-key"

class AuthManager:
    @staticmethod
    def sign_up(email, password, dairy_name, phone):
        url = f"{SUPABASE_URL}/auth/v1/signup"
        headers = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
        payload = {
            "email": email.strip(),
            "password": password.strip(),
            "data": {"dairy_name": dairy_name.strip(), "phone": phone.strip()}
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=8)
            data = res.json()
            if res.status_code in (200, 201):
                user_id = data.get("user", {}).get("id") or data.get("id")
                token = data.get("access_token", "")
                db.save_session(email, user_id, token, dairy_name, phone)
                return True, "Registration Successful!"
            return False, data.get("error_description") or data.get("msg") or "Registration failed."
        except Exception as e:
            return False, f"Network error: {str(e)}"

    @staticmethod
    def login(email, password):
        url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
        headers = {"apikey": SUPABASE_KEY, "Content-Type": "application/json"}
        payload = {"email": email.strip(), "password": password.strip()}
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=8)
            data = res.json()
            if res.status_code == 200:
                user = data.get("user", {})
                user_id = user.get("id")
                token = data.get("access_token")
                meta = user.get("user_metadata", {})
                dairy_name = meta.get("dairy_name", "Nilgiri Dairy")
                phone = meta.get("phone", "")
                db.save_session(email, user_id, token, dairy_name, phone)
                db.save_setting("dairy_name", dairy_name)
                db.save_setting("dairy_phone", phone)
                return True, "Login Successful!"
            return False, data.get("error_description") or "Invalid credentials."
        except Exception as e:
            return False, f"Network error: {str(e)}"

    @staticmethod
    def logout():
        db.clear_session()
        return True
