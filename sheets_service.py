import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_sheet = None


def _get_sheet():
    """Initialize and return the first worksheet of the Google Sheet."""
    global _sheet
    if _sheet is not None:
        return _sheet

    email = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL")
    raw_key = os.getenv("GOOGLE_PRIVATE_KEY", "")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")

    if not (email and raw_key and sheet_id):
        raise RuntimeError(
            "❌ Google Sheets credentials missing. "
            "Check GOOGLE_SERVICE_ACCOUNT_EMAIL, GOOGLE_PRIVATE_KEY and GOOGLE_SHEET_ID in .env"
        )

    # Handle escaped newlines stored in .env
    private_key = raw_key.replace("\\n", "\n")

    creds = Credentials.from_service_account_info(
        {
            "type": "service_account",
            "project_id": "alineain-menu-telegram-bot",
            "private_key_id": "key",
            "private_key": private_key,
            "client_email": email,
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        scopes=SCOPES,
    )

    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sheet_id)
    _sheet = spreadsheet.sheet1  # First worksheet
    print(f"✅ Connected to Google Sheet: {spreadsheet.title}")
    return _sheet


def get_all_products() -> list[dict]:
    """Fetch all rows from the sheet and return as a list of product dicts."""
    try:
        sheet = _get_sheet()
        rows = sheet.get_all_records()  # List of {header: value} dicts
        products = []
        for row in rows:
            name = str(row.get("Product Name", "")).strip()
            if not name:
                continue
            products.append(
                {
                    "id": str(row.get("Product Code") or row.get("No.", "")).strip(),
                    "name": name,
                    "category": str(row.get("Brand Name", "")).strip(),
                    "weight": str(row.get("Weight", "")).strip(),
                    "available": str(row.get("Available Count", "")).strip(),
                    "branch": str(row.get("Branch Name", "")).strip(),
                    "expiry": str(row.get("Expiry Date", "")).strip(),
                    "price": str(row.get("Selling Price", "")).strip(),
                }
            )
        return products
    except Exception as exc:
        print(f"❌ Error fetching products: {exc}")
        return []


def get_categories() -> list[str]:
    """Return a sorted, deduplicated list of category (Brand Name) values."""
    products = get_all_products()
    seen = []
    for p in products:
        cat = p["category"]
        if cat and cat not in seen:
            try:
                available = int(p["available"])
            except (ValueError, TypeError):
                available = 0
            if available > 0:
                seen.append(cat)
    return seen


def get_products_by_category(category: str) -> list[dict]:
    products = []
    for p in get_all_products():
        if p["category"] == category:
            try:
                available = int(p["available"])
            except (ValueError, TypeError):
                available = 0
            if available > 0:
                products.append(p)
    return products


def get_product_by_id(product_id: str) -> dict | None:
    for p in get_all_products():
        if p["id"] == product_id:
            return p
    return None

_customer_spreadsheet = None

def _get_customer_spreadsheet():
    """Initialize and return the customer spreadsheet."""
    global _customer_spreadsheet
    if _customer_spreadsheet is not None:
        return _customer_spreadsheet

    email = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL")
    raw_key = os.getenv("GOOGLE_PRIVATE_KEY", "")
    sheet_id = os.getenv("GOOGLE_CUSTOMER_SHEET_ID")

    if not (email and raw_key and sheet_id):
        raise RuntimeError(
            "❌ Google Customer Sheet credentials missing. "
            "Check GOOGLE_CUSTOMER_SHEET_ID in .env"
        )

    private_key = raw_key.replace("\\n", "\n")

    creds = Credentials.from_service_account_info(
        {
            "type": "service_account",
            "project_id": "alineain-menu-telegram-bot",
            "private_key_id": "key",
            "private_key": private_key,
            "client_email": email,
            "token_uri": "https://oauth2.googleapis.com/token",
        },
        scopes=SCOPES,
    )

    client = gspread.authorize(creds)
    _customer_spreadsheet = client.open_by_key(sheet_id)
    return _customer_spreadsheet

def save_order_record(order_id: str, date_str: str, customer: dict, items: list, payment: dict, tracking_number: str = ""):
    """Saves customer info and order items to two separate worksheets in the Google Spreadsheet."""
    try:
        spreadsheet = _get_customer_spreadsheet()
        worksheets = spreadsheet.worksheets()
        
        if len(worksheets) < 2:
            print("❌ The customer spreadsheet needs at least 2 sheets (tabs).")
            return
            
        customer_sheet = worksheets[0]
        items_sheet = worksheets[1]
        
        # Check if Tracking Number header exists, if not add it at column 12
        headers = customer_sheet.row_values(1)
        if "Tracking Number" not in headers:
            try:
                customer_sheet.update_cell(1, 12, "Tracking Number")
            except Exception as e:
                print(f"⚠️ Could not add Tracking Number header: {e}")
        
        # Save to Customer Info
        customer_row = [
            order_id,
            date_str,
            customer.get("name", ""),
            customer.get("address", ""),
            customer.get("phone1", ""),
            customer.get("phone2", ""),
            payment.get("type", ""),
            payment.get("method", ""),
            "Yes" if payment.get("delivery_paid") else "No",
            payment.get("delivery_amount", 0),
            payment.get("other_amount", 0),
            tracking_number
        ]
        customer_sheet.append_row(customer_row)
        
        # Save to Order Items
        item_rows = []
        for item in items:
            item_rows.append([
                order_id,
                item.get("name", ""),
                item.get("count", 0),
                item.get("price", 0),
                item.get("total", 0)
            ])
        items_sheet.append_rows(item_rows)
        
        print(f"✅ Successfully saved order {order_id} to Google Sheets.")
    except Exception as exc:
        print(f"❌ Error saving order to Google Sheets: {exc}")


def reduce_stock(items: list):
    """Reduce the Available Count in the product stock sheet for each ordered item."""
    try:
        sheet = _get_sheet()
        header_row = sheet.row_values(1)
        
        # Find column indices (1-based for gspread)
        code_col = None
        avail_col = None
        for i, h in enumerate(header_row):
            if h.strip() == "Product Code":
                code_col = i + 1
            elif h.strip() == "Available Count":
                avail_col = i + 1
        
        if code_col is None or avail_col is None:
            print("❌ Could not find 'Product Code' or 'Available Count' columns in stock sheet.")
            return
        
        # Get all product codes from the sheet
        all_codes = sheet.col_values(code_col)
        
        for item in items:
            product_id = str(item.get("id", "")).strip()
            ordered_count = item.get("count", 0)
            
            if not product_id or ordered_count <= 0:
                continue
            
            # Find the row for this product (skip header, so start from index 1)
            for row_idx, code in enumerate(all_codes):
                if str(code).strip() == product_id:
                    cell_row = row_idx + 1  # 1-based row number
                    current_val = sheet.cell(cell_row, avail_col).value
                    try:
                        current_count = int(current_val)
                    except (ValueError, TypeError):
                        current_count = 0
                    
                    new_count = max(0, current_count - ordered_count)
                    sheet.update_cell(cell_row, avail_col, new_count)
                    print(f"📦 Stock updated: {item.get('name', product_id)} → {current_count} → {new_count}")
                    break
        
        print("✅ Stock reduction complete.")
    except Exception as exc:
        print(f"❌ Error reducing stock: {exc}")


def upload_file_to_drive(local_path: str, filename: str, folder_id: str) -> str | None:
    """Uploads a local file to a specific Google Drive folder via Google Apps Script Web App."""
    import requests
    import base64
    import json
    
    try:
        apps_script_url = os.getenv("APPS_SCRIPT_URL")
        if not apps_script_url:
            print("❌ APPS_SCRIPT_URL missing from environment variables.")
            return None
        
        # Read and encode file as base64
        with open(local_path, "rb") as f:
            file_bytes = f.read()
        base64_data = base64.b64encode(file_bytes).decode("utf-8")
        
        payload = {
            "filename": filename,
            "folderId": folder_id,
            "base64Data": base64_data
        }
        
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            apps_script_url,
            headers=headers,
            data=json.dumps(payload),
            allow_redirects=True,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                file_id = result.get("id")
                print(f"✅ Successfully uploaded file to Google Drive via Apps Script. File ID: {file_id}")
                return file_id
            else:
                print(f"❌ Apps Script error: {result.get('message')}")
                return None
        else:
            print(f"❌ Error calling Apps Script: {response.status_code} - {response.text}")
            return None
    except Exception as exc:
        print(f"❌ Exception uploading file via Apps Script: {exc}")
        return None
