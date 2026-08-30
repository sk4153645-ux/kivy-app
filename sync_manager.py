import sqlite3
import requests

SUPABASE_URL = "https://myprwqurrtspkhojbvoh.supabase.co"
SUPABASE_KEY = "YAHAN_APNI_COPIED_KEY_PASTE_KARO"

class SyncManager:
    def __init__(self, db_path="dairy_v2.db"):
        self.db_path = db_path
        self.headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def sync_all(self):
        """Unsynced customers aur entries ko Supabase par upload karta hai."""
        conn = self._get_conn()
        cur = conn.cursor()

        try:
            # 1. Sync Customers
            cur.execute("SELECT * FROM customers WHERE is_synced = 0")
            customers = [dict(r) for r in cur.fetchall()]
            for c in customers:
                payload = {
                    "id": c["id"],
                    "name": c["name"],
                    "phone": c.get("phone"),
                    "address": c.get("address"),
                    "default_rate": c.get("default_rate", 0.0),
                    "updated_at": c["updated_at"]
                }
                res = requests.post(
                    f"{SUPABASE_URL}/rest/v1/customers",
                    json=payload,
                    headers=self.headers,
                    timeout=10
                )
                if res.status_code in (200, 201):
                    cur.execute("UPDATE customers SET is_synced = 1 WHERE id = ?", (c["id"],))

            # 2. Sync Milk Entries
            cur.execute("SELECT * FROM milk_entries WHERE is_synced = 0")
            entries = [dict(r) for r in cur.fetchall()]
            for e in entries:
                payload = {
                    "id": e["id"],
                    "customer_id": e["customer_id"],
                    "entry_date": e["entry_date"],
                    "shift": e["shift"],
                    "litres": e["litres"],
                    "rate": e["rate"],
                    "amount": e["amount"],
                    "updated_at": e["updated_at"]
                }
                res = requests.post(
                    f"{SUPABASE_URL}/rest/v1/milk_entries",
                    json=payload,
                    headers=self.headers,
                    timeout=10
                )
                if res.status_code in (200, 201):
                    cur.execute("UPDATE milk_entries SET is_synced = 1 WHERE id = ?", (e["id"],))

            conn.commit()
            return True, "Sync Successful!"
        except Exception as err:
            return False, f"Sync Failed: {str(err)}"
        finally:
            conn.close()
