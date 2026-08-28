import os
import base64
import json
import requests

# ============================================================
# API KEY
# ------------------------------------------------------------
# NEVER hardcode the key here. It is loaded, in order of priority, from:
#   1. The GEMINI_API_KEY environment variable (set this for local dev)
#   2. secrets_config.py (auto-generated at CI build time, gitignored,
#      never committed - see .github/workflows/build-apk.yml)
# If neither is present, the scanner is disabled at runtime rather than
# crashing the app.
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY", "")

if not API_KEY:
    try:
        import secrets_config
        API_KEY = getattr(secrets_config, "GEMINI_API_KEY", "")
    except Exception:
        API_KEY = ""

API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"


def scan_dairy_register(image_path: str):
    """
    Image ko Google Gemini ko bhejta hai aur structured JSON array return karta hai.
    Overwritten/doubtful entries ko 'doubtful_fields' me mark karta hai.
    """
    if not API_KEY:
        print("Scanner Error: GEMINI_API_KEY not configured for this build.")
        return []

    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            b64_image = base64.b64encode(image_bytes).decode("utf-8")

        prompt = """
        Analyze this handwritten Indian dairy register/hisaab image carefully.
        Extract the daily table records into a structured JSON array.
        Each entry object must contain:
        - "date": Date as string (e.g. "11/8")
        - "morning_qty": Numeric string of milk (e.g. "15.22")
        - "morning_rate": Numeric string of rate (e.g. "37")
        - "evening_qty": Numeric string of milk (e.g. "20.65")
        - "evening_rate": Numeric string of rate (e.g. "37")
        - "doubtful_fields": List of field names that are overwritten, heavily cut, or unclear (e.g. ["evening_qty", "morning_rate"]). Empty list [] if clear.
        - "customer_name": Top name if present (or "Unknown")

        Rules:
        1. If an entry is written as '15.22 X 37', 15.22 is morning_qty and 37 is morning_rate.
        2. Pick the latest corrected value if crossed-out, and add that field name to 'doubtful_fields'.
        3. Return strictly a valid JSON array without markdown formatting.
        """

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": b64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json"
            }
        }

        response = requests.post(API_URL, json=payload, timeout=40)

        if response.status_code == 200:
            result = response.json()
            raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)
        else:
            print(f"API Error ({response.status_code}): {response.text}")
            return []

    except Exception as e:
        print(f"Scanner Error: {str(e)}")
        return []


def export_to_excel(records: list, output_path: str):
    """Extracted data ko Excel (.xlsx) file me save karta hai. Requires openpyxl."""
    try:
        from openpyxl import Workbook
    except Exception as e:
        print(f"Excel Export Error: openpyxl not available ({e})")
        return False

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "Dairy Hisaab"
        ws.append(["Date", "Morning Milk (L)", "Morning Rate", "Evening Milk (L)", "Evening Rate"])

        for r in records:
            ws.append([
                r.get("date", ""),
                r.get("morning_qty", ""),
                r.get("morning_rate", ""),
                r.get("evening_qty", ""),
                r.get("evening_rate", ""),
            ])

        # Reasonable default column widths so the export is readable without
        # manual resizing.
        for col_letter, width in zip("ABCDE", (12, 16, 12, 16, 12)):
            ws.column_dimensions[col_letter].width = width

        wb.save(output_path)
        return True
    except Exception as e:
        print(f"Excel Export Error: {str(e)}")
        return False


def export_to_pdf(records: list, output_path: str, title: str = "Dairy Hisaab"):
    """Extracted data ko clean A4 Table PDF me convert karta hai. Requires reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
    except Exception as e:
        print(f"PDF Export Error: reportlab not available ({e})")
        return False

    try:
        doc = SimpleDocTemplate(output_path, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph(f"<b>{title}</b>", styles["Heading1"]))
        elements.append(Spacer(1, 15))

        table_data = [["Date", "Morning (L)", "Rate", "Evening (L)", "Rate"]]
        for r in records:
            table_data.append([
                str(r.get("date", "")),
                str(r.get("morning_qty", "")),
                str(r.get("morning_rate", "")),
                str(r.get("evening_qty", "")),
                str(r.get("evening_rate", ""))
            ])

        t = Table(table_data, colWidths=[80, 100, 80, 100, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#EAECEE")])
        ]))

        elements.append(t)
        doc.build(elements)
        return True
    except Exception as e:
        print(f"PDF Export Error: {str(e)}")
        return False
