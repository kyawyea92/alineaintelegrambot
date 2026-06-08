import os
from datetime import datetime
from fpdf import FPDF

class VoucherPDF(FPDF):
    def header(self):
        # We can add a custom header if needed, but we will draw everything in the main body
        pass

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        self.set_font("Pyidaungsu", size=8)
        self.cell(0, 10, "ကျေးဇူးတင်ပါသည် / Thank you!", align="C")

def generate_voucher_pdf(customer_info: dict, items: list, payment_info: dict, output_path: str, tracking_number: str = "") -> str:
    """
    Generates a PDF voucher.
    customer_info: {
        "name": str,
        "address": str, (optional)
        "phone1": str,
        "phone2": str (optional)
    }
    items: list of {
        "name": str,
        "count": int,
        "price": float,
        "total": float
    }
    payment_info: {
        "type": str,
        "method": str, (optional)
        "other_amount": float, (optional)
        "delivery_paid": bool,
        "delivery_amount": float
    }
    """
    pdf = VoucherPDF()
    pdf.add_page()
    
    # Add Myanmar/Latin Font
    base_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(base_dir, "fonts", "Pyidaungsu-Regular.ttf")
    if os.path.exists(font_path):
        pdf.add_font("Pyidaungsu", style="", fname=font_path)
    else:
        # Fallback if font is not found
        pass

    # Enable text shaping for proper Myanmar script rendering
    pdf.set_text_shaping(True)

    pdf.set_font("Pyidaungsu", size=16)
    
    # Title: အလင်းအိမ် မုန့်ဆိုင်
    pdf.cell(0, 10, "အလင်းအိမ် မုန့်ဆိုင်", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    # Customer Info
    pdf.set_font("Pyidaungsu", size=11)
    
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    pdf.cell(0, 8, f"ရက်စွဲ (Date): {date_str}", new_x="LMARGIN", new_y="NEXT")
    if tracking_number:
        pdf.cell(0, 8, f"ခြေရာခံနံပါတ် (Tracking No.): {tracking_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"ဝယ်သူအမည် (Customer Name): {customer_info['name']}", new_x="LMARGIN", new_y="NEXT")
    
    address = customer_info.get("address", "").strip()
    if address:
        pdf.cell(0, 8, f"လိပ်စာ (Address): {address}", new_x="LMARGIN", new_y="NEXT")
        
    phone1 = customer_info.get("phone1", "").strip()
    phone2 = customer_info.get("phone2", "").strip()
    phones = phone1
    if phone2:
        phones += f" / {phone2}"
    pdf.cell(0, 8, f"ဖုန်းနံပါတ် (Phone): {phones}", new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(5)
    
    # Table Header
    # Column widths
    w_name = 90
    w_count = 25
    w_price = 35
    w_total = 40
    
    pdf.set_font("Pyidaungsu", size=11)
    
    # Header cells
    pdf.cell(w_name, 10, "ပစ္စည်းအမည် (Product)", border=1, align="C")
    pdf.cell(w_count, 10, "အရေအတွက်", border=1, align="C")
    pdf.cell(w_price, 10, "နှုန်း (Price)", border=1, align="C")
    pdf.cell(w_total, 10, "သင့်ငွေ (Total)", border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    
    grand_total = 0.0
    
    # Table Rows
    pdf.set_font("Pyidaungsu", size=10)
    for item in items:
        name = item["name"]
        count = item["count"]
        price = item["price"]
        total = item["total"]
        grand_total += total
        
        # Calculate height if name needs wrapping (multi-line)
        # Using multi_cell is a bit complex for dynamic line heights, 
        # so let's check text length or use basic cells, or just truncate / wrap
        # To keep it simple, we can use multi_cell or simple cell.
        # Since product names can be long, let's use a multi_cell helper or simple wrapping.
        # Let's write name in a cell, but to keep it aligned with other columns:
        # We can get current x, y, draw multi_cell for name, then set x, y back for others.
        x_before = pdf.get_x()
        y_before = pdf.get_y()
        
        pdf.multi_cell(w_name, 8, name, border=1, align="L")
        y_after = pdf.get_y()
        height = y_after - y_before
        
        # Draw other columns with the same height
        pdf.set_xy(x_before + w_name, y_before)
        pdf.cell(w_count, height, str(count), border=1, align="C")
        pdf.cell(w_price, height, f"{price:,.0f} VND", border=1, align="R")
        pdf.cell(w_total, height, f"{total:,.0f} VND", border=1, align="R", new_x="LMARGIN", new_y="NEXT")
        
    # Grand Total row
    pdf.set_font("Pyidaungsu", size=11)
    pdf.cell(w_name + w_count + w_price, 10, "စုစုပေါင်းသင့်ငွေ (Total Amount): ", border=1, align="R")
    pdf.cell(w_total, 10, f"{grand_total:,.0f} VND", border=1, align="R", new_x="LMARGIN", new_y="NEXT")
    
    # Extract Payment Info
    pay_type = payment_info.get("type", "")
    method = payment_info.get("method", "")
    other_amount = payment_info.get("other_amount", 0)
    del_amount = payment_info.get("delivery_amount", 0)
    del_paid = payment_info.get("delivery_paid", False)
    
    payment_str = f"{pay_type}"
    if pay_type == "Full Paid" and method:
        payment_str += f" ({method})"
        
    # Calculate Paid and Left Amount
    if pay_type == "Full Paid":
        paid_amount_str = f"{grand_total:,.0f} VND"
        left_amount_str = "0 VND"
    elif pay_type == "Others":
        paid_amount_str = f"{other_amount:,.0f} VND"
        left_amount = (grand_total - other_amount) + (del_amount if not del_paid else 0)
        left_amount_str = f"{left_amount:,.0f} VND"
    elif pay_type == "COD":
        paid_amount_str = "-"
        left_amount = grand_total + del_amount if not del_paid else grand_total
        left_amount_str = f"{left_amount:,.0f} VND"
    else:
        paid_amount_str = "-"
        left_amount_str = f"{grand_total:,.0f} VND"

    # Payment Type Row
    pdf.cell(w_name + w_count + w_price, 10, "Payment Type: ", border=1, align="R")
    pdf.cell(w_total, 10, payment_str, border=1, align="R", new_x="LMARGIN", new_y="NEXT")

    # Delivery Charges Row
    pdf.cell(w_name + w_count + w_price, 10, "Delivery Charges: ", border=1, align="R")
    pdf.cell(w_total, 10, f"{del_amount:,.0f} VND" if del_amount > 0 else "-", border=1, align="R", new_x="LMARGIN", new_y="NEXT")

    # Paid Amount Row
    pdf.cell(w_name + w_count + w_price, 10, "Paid Amount: ", border=1, align="R")
    pdf.cell(w_total, 10, paid_amount_str, border=1, align="R", new_x="LMARGIN", new_y="NEXT")

    # Left Amount Row
    pdf.cell(w_name + w_count + w_price, 10, "Left Amount: ", border=1, align="R")
    pdf.cell(w_total, 10, left_amount_str, border=1, align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    
    # Outside table details
    if del_paid:
        pdf.set_font("Pyidaungsu", style="", size=11)
        pdf.cell(0, 8, "Delivery ခ ကောက်ခံရန်မလို", new_x="LMARGIN", new_y="NEXT")
    
    pdf.output(output_path)
    return output_path
