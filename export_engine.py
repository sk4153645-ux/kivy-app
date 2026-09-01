# export_engine.py - Excel (openpyxl) and PDF (fpdf2) statement exports
# Both libraries are imported lazily so a missing dependency only disables
# the specific export format instead of breaking the whole app.


def export_month_excel(output_path, title, code, name, month_label, data, entity_label, rows):
    """
    data: dict from get_farmer_month_data() / get_customer_month_data()
    rows: list of (date, litres, rate, amount) detail rows for the month
    """
    try:
        from openpyxl import Workbook
    except Exception as e:
        return False, f"openpyxl not available: {e}"

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Statement"

        ws.append([title])
        ws.append([f"{entity_label}: [{code}] {name}"])
        ws.append([f"Period: {month_label}"])
        ws.append([])
        ws.append(["Previous Due", f"Rs. {data['previous_due']:.2f}"])
        ws.append(["This Month Qty (L)", f"{data['current_litres']:.2f}"])
        ws.append(["This Month Amount", f"Rs. {data['current_amount']:.2f}"])
        ws.append(["This Month Paid", f"Rs. {data['current_paid']:.2f}"])
        ws.append(["Total Due", f"Rs. {data['total_due']:.2f}"])
        ws.append([])
        ws.append(["Date", "Litres", "Rate", "Amount"])
        for r in rows:
            ws.append(list(r))

        for col_letter, width in zip("ABCD", (14, 12, 10, 12)):
            ws.column_dimensions[col_letter].width = width

        wb.save(output_path)
        return True, output_path
    except Exception as e:
        return False, str(e)


def export_month_pdf(output_path, title, code, name, month_label, data, entity_label, rows):
    try:
        from fpdf import FPDF
    except Exception as e:
        return False, f"fpdf2 not available: {e}"

    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, title, ln=True, align="C")

        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 8, f"{entity_label}: [{code}] {name}", ln=True)
        pdf.cell(0, 8, f"Period: {month_label}", ln=True)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Summary", ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, f"Previous Due: Rs. {data['previous_due']:.2f}", ln=True)
        pdf.cell(0, 7, f"This Month Qty: {data['current_litres']:.2f} L", ln=True)
        pdf.cell(0, 7, f"This Month Amount: Rs. {data['current_amount']:.2f}", ln=True)
        pdf.cell(0, 7, f"This Month Paid: Rs. {data['current_paid']:.2f}", ln=True)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"TOTAL DUE: Rs. {data['total_due']:.2f}", ln=True)
        pdf.ln(4)

        if rows:
            pdf.set_font("Helvetica", "B", 11)
            col_w = [45, 40, 40, 45]
            headers = ["Date", "Litres", "Rate", "Amount"]
            for w, h in zip(col_w, headers):
                pdf.cell(w, 8, h, border=1)
            pdf.ln()
            pdf.set_font("Helvetica", "", 10)
            for r in rows:
                for w, val in zip(col_w, r):
                    text = f"{val:.2f}" if isinstance(val, float) else str(val)
                    pdf.cell(w, 7, text, border=1)
                pdf.ln()

        pdf.output(output_path)
        return True, output_path
    except Exception as e:
        return False, str(e)
