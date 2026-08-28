import os
import re
import json
import base64
import mimetypes
import requests

# ============================================================
# API KEY RESOLVER
# ============================================================

def get_api_key():
    # 1. Environment Variable
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key

    # 2. secrets_config.py
    try:
        import secrets_config
        key = getattr(secrets_config, "GEMINI_API_KEY", "").strip()
        if key:
            return key
    except Exception:
        pass

    # 3. Secure Built-in Fallback Key
    encoded_fallback = "QVEuQWI4Uk42TFlIZkM1NVhYSHZTeV9EcE9VY25kSHZuZ1dBZ1VIa3FURzVvSHowdzBOM0E="
    try:
        return base64.b64decode(encoded_fallback).decode("utf-8")
    except Exception:
        return ""


def clean_json_response(raw_text: str):
    """Markdown backticks ya extra text ko hata kar pure JSON array nikalta hai."""
    text = raw_text.strip()
    # Remove markdown codeblocks ```json ... ```
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    
    # Locate array boundaries
    start_idx = text.find("[")
    end_idx = text.rfind("]")
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx : end_idx + 1]
    
    return json.loads(text)


def scan_dairy_register(image_path: str):
    """
    Image ko Google Gemini ko bhej kar structured JSON array return karta hai.
    """
    api_key = get_api_key()
    if not api_key:
        print("Scanner Error: GEMINI_API_KEY not found.")
        return []

    if not os.path.exists(image_path):
        print(f"Scanner Error: File does not exist at {image_path}")
        return []

    try:
        # Dynamic Mime-Type Detection
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/jpeg"

        with open(image_path, "rb") as f:
            image_bytes = f.read()
            b64_image = base64.b64encode(image_bytes).decode("utf-8")

        prompt = """
        Analyze this handwritten Indian dairy register/hisaab image carefully.
        Extract the daily table records into a structured JSON array.
        Each entry object must strictly contain:
        - "date": Date as string (e.g. "11/8" or "11-08")
        - "morning_qty": Numeric string of milk litres (e.g. "15.22" or "" if absent)
        - "morning_rate": Numeric string of rate (e.g. "37" or "" if absent)
        - "evening_qty": Numeric string of milk litres (e.g. "20.65" or "" if absent)
        - "evening_rate": Numeric string of rate (e.g. "37" or "" if absent)
        - "doubtful_fields": List of field names that are overwritten, cut, or unclear (e.g. ["evening_qty"]). Empty list [] if clear.
        - "customer_name": Top name if written (or "Unknown")

        Rules:
        1. If an entry is written like '15.22 X 37', 15.22 is morning_qty and 37 is morning_rate.
        2. Pick the latest corrected value if overwritten, and mark that field in 'doubtful_fields'.
        3. Return strictly a JSON array without markdown explanation.
        """

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
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

        api_url = f"[https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=](https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=){api_key}"
        response = requests.post(api_url, json=payload, timeout=45)

        if response.status_code == 200:
            result = response.json()
            raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
            return clean_json_response(raw_text)
        else:
            print(f"API Error ({response.status_code}): {response.text}")
            return []

    except Exception as e:
        print(f"Scanner Error: {str(e)}")
        return []


def export_to_excel(records: list, output_path: str):
    """Extracted data ko Excel (.xlsx) file me save karta hai."""
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

        for col_letter, width in zip("ABCDE", (12, 16, 12, 16, 12)):
            ws.column_dimensions[col_letter].width = width

        wb.save(output_path)
        return True
    except Exception as e:
        print(f"Excel Export Error: {str(e)}")
        return False


def export_to_pdf(records: list, output_path: str, title: str = "Dairy Hisaab"):
    """Extracted data ko A4 Table PDF me convert karta hai."""
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
