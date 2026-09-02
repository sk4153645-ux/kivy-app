# services.py - Model Validation, Services & Safe Transactions
import datetime
import database as db

class ValidationError(Exception):
    pass

class DairyService:
    @staticmethod
    def validate_code(code):
        if not code or not str(code).isalnum():
            raise ValidationError("Invalid Code: Must be alphanumeric.")
        return str(code).strip()

    @staticmethod
    def validate_positive_number(val, name, min_val=0.01, max_val=1000.0):
        try:
            num = float(val)
        except (ValueError, TypeError):
            raise ValidationError(f"{name} must be a valid number.")
        if num < min_val:
            raise ValidationError(f"{name} must be greater than {min_val}.")
        if num > max_val:
            raise ValidationError(f"{name} seems unusually high (Max {max_val}).")
        return round(num, 2)

    @staticmethod
    def save_milk_entry(farmer_code, shift, milk_type, litres, fat, snf, rate, date_str=None):
        code = DairyService.validate_code(farmer_code)
        litres = DairyService.validate_positive_number(litres, "Litres", 0.1, 500.0)
        rate = DairyService.validate_positive_number(rate, "Rate", 1.0, 200.0)
        fat = float(fat or 0.0)
        snf = float(snf or 0.0)
        if fat < 0 or snf < 0:
            raise ValidationError("Fat and SNF cannot be negative.")

        total_amount = round(litres * rate, 2)
        if not date_str:
            date_str = datetime.date.today().isoformat()

        conn = db.get_db()
        try:
            with conn:
                # Check farmer existence
                f = conn.execute("SELECT name FROM farmers WHERE code = ?", (code,)).fetchone()
                if not f:
                    raise ValidationError(f"Farmer with code [{code}] does not exist!")

                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO milk_purchases (date, shift, farmer_code, milk_type, litres, fat, snf, rate, total_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (date_str, shift, code, milk_type, litres, fat, snf, rate, total_amount))
                entry_id = cur.lastrowid
                db.log_audit("INSERT", "milk_purchases", entry_id, f"{litres}L by [{code}] - Total: Rs.{total_amount}")
                return entry_id, total_amount
        finally:
            conn.close()

    @staticmethod
    def delete_milk_entry(entry_id):
        conn = db.get_db()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM milk_purchases WHERE id = ?", (entry_id,))
                db.log_audit("DELETE", "milk_purchases", entry_id, "Milk purchase deleted")
                return True
        finally:
            conn.close()

    @staticmethod
    def settle_farmer_payment(farmer_code, amount, mode="Cash", note=""):
        code = DairyService.validate_code(farmer_code)
        amt = DairyService.validate_positive_number(amount, "Amount", 1.0, 500000.0)
        date_str = datetime.date.today().isoformat()

        conn = db.get_db()
        try:
            with conn:
                f = conn.execute("SELECT name, phone FROM farmers WHERE code = ?", (code,)).fetchone()
                if not f:
                    raise ValidationError(f"Farmer [{code}] does not exist.")
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO farmer_payments (date, farmer_code, amount, payment_mode, note)
                    VALUES (?, ?, ?, ?, ?)
                ''', (date_str, code, amt, mode, note))
                p_id = cur.lastrowid
                db.log_audit("INSERT", "farmer_payments", p_id, f"Paid Rs.{amt} via {mode} to [{code}]")
                return f["name"], f["phone"], amt
        finally:
            conn.close()
