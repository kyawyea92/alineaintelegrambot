import logging
import os
import html
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import sheets_service as sheet
from voucher_pdf import generate_voucher_pdf

logger = logging.getLogger(__name__)

(
    STATE_NAME,
    STATE_ADDRESS,
    STATE_PHONE1,
    STATE_PHONE2,
    STATE_SELECT_CATEGORY,
    STATE_SELECT_PRODUCT,
    STATE_PRODUCT_DETAIL,
    STATE_INPUT_COUNT,
    STATE_INPUT_PRICE,
    STATE_DECIDE_NEXT,
    STATE_PAYMENT_TYPE,
    STATE_FULL_PAID_METHOD,
    STATE_OTHER_AMOUNT,
    STATE_DELIVERY_PAID,
    STATE_DELIVERY_AMOUNT,
) = range(15)

def get_cancel_kb(back_callback: str = None) -> InlineKeyboardMarkup:
    buttons = []
    if back_callback:
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=back_callback)])
    buttons.append([InlineKeyboardButton("❌ Cancel Order", callback_data="v_cancel")])
    return InlineKeyboardMarkup(buttons)

def get_skip_cancel_kb(back_callback: str = None) -> InlineKeyboardMarkup:
    buttons = []
    buttons.append([InlineKeyboardButton("⏩ Skip", callback_data="v_skip")])
    if back_callback:
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=back_callback)])
    buttons.append([InlineKeyboardButton("❌ Cancel Order", callback_data="v_cancel")])
    return InlineKeyboardMarkup(buttons)

def _escape(text: str) -> str:
    """Escape special characters for Telegram HTML mode."""
    return html.escape(str(text))

# --- Starting the Voucher flow ---
async def start_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        chat_id = query.message.chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text="📝 <b>Open Voucher Flow Started</b>\n\nဝယ်သူအမည် (Customer Name) ကို ရိုက်ထည့်ပေးပါရန်။",
            parse_mode="HTML",
            reply_markup=get_cancel_kb()
        )
    else:
        await update.message.reply_text(
            "📝 <b>Open Voucher Flow Started</b>\n\nဝယ်သူအမည် (Customer Name) ကို ရိုက်ထည့်ပေးပါရန်။",
            parse_mode="HTML",
            reply_markup=get_cancel_kb()
        )
        
    # Initialize session data
    context.user_data["voucher"] = {
        "customer": {
            "name": "",
            "address": "",
            "phone1": "",
            "phone2": ""
        },
        "items": [],
        "current_item": {} # temp store for item being configured
    }
    return STATE_NAME

# --- Customer Info Inputs ---
async def input_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("အမည်ကို အနည်းဆုံး စာလုံးတစ်လုံး ထည့်ပေးပါရန်။", reply_markup=get_cancel_kb())
        return STATE_NAME
    
    context.user_data["voucher"]["customer"]["name"] = name
    await update.message.reply_text(
        f"သတ်မှတ်ပြီးအမည်: <b>{_escape(name)}</b>\n\nလိပ်စာ (Address) ကို ရိုက်ထည့်ပေးပါရန်။",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(back_callback="back_to_name")
    )
    return STATE_ADDRESS

async def input_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    address = update.message.text.strip()
    if not address:
        await update.message.reply_text(
            "လိပ်စာကို ရိုက်ထည့်ပေးပါရန်။",
            reply_markup=get_cancel_kb(back_callback="back_to_name")
        )
        return STATE_ADDRESS

    context.user_data["voucher"]["customer"]["address"] = address
    await update.message.reply_text(
        f"သတ်မှတ်ပြီးလိပ်စာ: <b>{_escape(address)}</b>\n\nဖုန်းနံပါတ် ၁ (Phone Number 1) ကို ရိုက်ထည့်ပေးပါရန်။",
        parse_mode="HTML",
        reply_markup=get_cancel_kb(back_callback="back_to_address")
    )
    return STATE_PHONE1

async def input_phone1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone1 = update.message.text.strip()
    if not phone1:
        await update.message.reply_text(
            "ဖုန်းနံပါတ် ထည့်သွင်းပေးပါရန်။",
            reply_markup=get_cancel_kb(back_callback="back_to_address")
        )
        return STATE_PHONE1
        
    context.user_data["voucher"]["customer"]["phone1"] = phone1
    await update.message.reply_text(
        f"သတ်မှတ်ပြီး ဖုန်းနံပါတ် ၁: <b>{_escape(phone1)}</b>\n\nဖုန်းနံပါတ် ၂ (Phone Number 2) ကို ရိုက်ထည့်ပေးပါရန်။ (မထည့်လိုက 'Skip' ကို နှိပ်ပါ)",
        parse_mode="HTML",
        reply_markup=get_skip_cancel_kb(back_callback="back_to_phone1")
    )
    return STATE_PHONE2

async def input_phone2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone2 = update.message.text.strip()
    context.user_data["voucher"]["customer"]["phone2"] = phone2
    await update.message.reply_text(
        f"သတ်မှတ်ပြီး ဖုန်းနံပါတ် ၂: <b>{_escape(phone2)}</b>\n\nပစ္စည်းများကို စတင်ရွေးချယ်ပါမည်။",
        parse_mode="HTML"
    )
    return await send_voucher_categories(update, context)

async def skip_phone2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["voucher"]["customer"]["phone2"] = ""
    await query.message.reply_text("ဖုန်းနံပါတ် ၂ ကို ကျော်လိုက်ပါပြီ။ ပစ္စည်းများကို စတင်ရွေးချယ်ပါမည်။")
    return await send_voucher_categories(update, context, query.message)


# --- Back navigation handlers ---
async def back_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "ဝယ်သူအမည် (Customer Name) ကို ပြန်လည်ရိုက်ထည့်ပေးပါရန်။",
        reply_markup=get_cancel_kb()
    )
    return STATE_NAME

async def back_to_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "လိပ်စာ (Address) ကို ပြန်လည်ရိုက်ထည့်ပေးပါရန်။",
        reply_markup=get_cancel_kb(back_callback="back_to_name")
    )
    return STATE_ADDRESS

async def back_to_phone1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "ဖုန်းနံပါတ် ၁ (Phone Number 1) ကို ပြန်လည်ရိုက်ထည့်ပေးပါရန်။",
        reply_markup=get_cancel_kb(back_callback="back_to_address")
    )
    return STATE_PHONE1


# --- Category and Product Selection (Voucher Flow specific) ---
async def send_voucher_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, message_obj=None) -> int:
    categories = sheet.get_categories()
    rows = []
    if categories:
        for i in range(0, len(categories), 2):
            row = [InlineKeyboardButton(f"{i+1}. {categories[i]}", callback_data=f"vcat_{categories[i]}")]
            if i + 1 < len(categories):
                row.append(InlineKeyboardButton(f"{i+2}. {categories[i+1]}", callback_data=f"vcat_{categories[i+1]}"))
            rows.append(row)
    else:
        rows.append([InlineKeyboardButton("📦 View All Products", callback_data="v_all_products")])
        
    rows.append([InlineKeyboardButton("❌ Cancel Order", callback_data="v_cancel")])
    
    text = "📂 <b>Brand / Category တစ်ခုခုကို ရွေးချယ်ပါရန်:</b>"
    
    if message_obj:
        await message_obj.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
        
    return STATE_SELECT_CATEGORY

async def handle_voucher_category_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    category = query.data[5:] # remove 'vcat_'
    products = sheet.get_products_by_category(category)
    
    rows = []
    for p in products:
        label = p["name"][:35] + "…" if len(p["name"]) > 35 else p["name"]
        rows.append([InlineKeyboardButton(label, callback_data=f"vprod_{p['id']}")])
        
    rows.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="v_back_categories")])
    rows.append([InlineKeyboardButton("❌ Cancel Order", callback_data="v_cancel")])
    
    safe_cat = _escape(category)
    await query.edit_message_text(
        text=f"📁 <b>{safe_cat}</b> စာရင်းဝင် ပစ္စည်းများ:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return STATE_SELECT_PRODUCT

async def handle_all_products_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    products = sheet.get_all_products()
    rows = []
    for p in products:
        label = p["name"][:35] + "…" if len(p["name"]) > 35 else p["name"]
        rows.append([InlineKeyboardButton(label, callback_data=f"vprod_{p['id']}")])
        
    rows.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="v_back_categories")])
    rows.append([InlineKeyboardButton("❌ Cancel Order", callback_data="v_cancel")])
    
    await query.edit_message_text(
        text="📦 <b>ပစ္စည်းအားလုံး:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return STATE_SELECT_PRODUCT

async def handle_voucher_product_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    product_id = query.data[6:] # remove 'vprod_'
    product = sheet.get_product_by_id(product_id)
    
    if not product:
        await query.edit_message_text(
            text="❌ ပစ္စည်းကို ရှာမတွေ့ပါ။",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Categories", callback_data="v_back_categories")]])
        )
        return STATE_SELECT_CATEGORY
        
    # Temporarily store the product we are adding
    try:
        avail_val = int(product["available"])
    except (ValueError, TypeError):
        avail_val = 0
    try:
        price_val = float(product["price"].replace(",", "")) if product.get("price") else 0.0
    except (ValueError, TypeError):
        price_val = 0.0

    context.user_data["voucher"]["current_item"] = {
        "id": product["id"],
        "name": product["name"],
        "category": product["category"],
        "available": avail_val,
        "price": price_val
    }
    
    price_str = f"{product['price']} VND" if product.get('price') else "N/A"
    detail = (
        f"<b>{_escape(product['name'])}</b>\n\n"
        f"🏷 Brand:      {_escape(product['category'] or 'N/A')}\n"
        f"🔖 Code:       {_escape(product['id'] or 'N/A')}\n"
        f"⚖️ Weight:     {_escape(product['weight'] or 'N/A')}\n"
        f"💰 Price:      {_escape(price_str)}\n"
        f"📦 Available:  {_escape(product['available'] or '0')}\n"
        f"🏪 Branch:     {_escape(product['branch'] or 'N/A')}\n"
        f"📅 Expiry:     {_escape(product['expiry'] or 'N/A')}"
    )
    
    rows = [
        [InlineKeyboardButton("✅ Add to Voucher", callback_data="v_add_confirm")],
        [InlineKeyboardButton("🔙 Back to List", callback_data=f"vcat_{product['category']}")],
        [InlineKeyboardButton("❌ Cancel Order", callback_data="v_cancel")]
    ]
    
    await query.edit_message_text(
        text=detail,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return STATE_PRODUCT_DETAIL

async def handle_add_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    current_item = context.user_data["voucher"]["current_item"]
    await query.message.reply_text(
        text=f"📦 <b>{_escape(current_item['name'])}</b>\n\nကျေးဇူးပြု၍ အရေအတွက် (Item Count) ကို ရိုက်ထည့်ပေးပါရန်။ (လက်ကျန်: {current_item['available']})",
        parse_mode="HTML",
        reply_markup=get_cancel_kb()
    )
    return STATE_INPUT_COUNT

async def handle_input_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    count_str = update.message.text.strip()
    current_item = context.user_data["voucher"]["current_item"]
    try:
        count = int(count_str)
        if count <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text(
            "⚠️ အရေအတွက်မှာ လုံးရေအပေါင်းကိန်း (Positive Integer) ဖြစ်ရပါမည်။ ထပ်မံရိုက်ထည့်ပေးပါရန်။",
            reply_markup=get_cancel_kb()
        )
        return STATE_INPUT_COUNT
        
    if count > current_item["available"]:
        await update.message.reply_text(
            f"⚠️ လက်ကျန်အရေအတွက်ထက် ပိုမိုရွေးချယ်ထားပါသည်။ ကျေးဇူးပြု၍ လက်ကျန် {current_item['available']} သို့မဟုတ် ထိုထက်နည်းသော အရေအတွက်ကို ထည့်သွင်းပေးပါရန်။",
            reply_markup=get_cancel_kb()
        )
        return STATE_INPUT_COUNT

    current_item["count"] = count
    price = current_item["price"]
    current_item["total"] = price * count
    
    # Save current item into list directly since price is already retrieved
    context.user_data["voucher"]["items"].append(current_item)
    context.user_data["voucher"]["current_item"] = {} # clear temp
    
    # Show running summary and ask for next step
    items = context.user_data["voucher"]["items"]
    customer = context.user_data["voucher"]["customer"]
    
    summary_text = (
        f"📝 <b>Voucher Summary</b>\n"
        f"ဝယ်သူ: {customer['name']}\n"
        f"---------------------------\n"
    )
    
    grand_total = 0.0
    for idx, item in enumerate(items, 1):
        summary_text += f"{idx}. {item['name']}\n    {item['count']} x {item['price']:,.0f} = {item['total']:,.0f} VND\n"
        grand_total += item["total"]
        
    summary_text += f"---------------------------\n<b>စုစုပေါင်း: {grand_total:,.0f} VND</b>\n\nနောက်ထပ် ပစ္စည်းထည့်မလား သို့မဟုတ် ဘောက်ချာပိတ်မလား ရွေးချယ်ပါရန်။"
    
    rows = [
        [InlineKeyboardButton("➕ One More Item", callback_data="v_one_more")],
        [InlineKeyboardButton("🏁 Finish Order", callback_data="v_finish")],
        [InlineKeyboardButton("❌ Cancel Order", callback_data="v_cancel")]
    ]
    
    await update.message.reply_text(
        text=summary_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return STATE_DECIDE_NEXT

# --- Decide Next Action handler ---
async def handle_one_more(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await send_voucher_categories(update, context)

async def handle_finish_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    items = context.user_data["voucher"]["items"]
    if not items:
        await query.message.reply_text("⚠️ ပစ္စည်း တစ်ခုမှ မရှိသေးပါ။")
        return await send_voucher_categories(update, context)
        
    rows = [
        [InlineKeyboardButton("Pre Paid", callback_data="pay_full")],
        [InlineKeyboardButton("COD", callback_data="pay_cod")],
        [InlineKeyboardButton("❌ Cancel Order", callback_data="v_cancel")]
    ]
    await query.edit_message_text(
        "ငွေပေးချေမှု အမျိုးအစား (Payment Type) ကို ရွေးချယ်ပါရန်:",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return STATE_PAYMENT_TYPE

async def handle_payment_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    context.user_data["voucher"]["payment"] = {}
    
    if data == "pay_full":
        context.user_data["voucher"]["payment"]["type"] = "Pre Paid"
        context.user_data["voucher"]["payment"]["method"] = ""
        return await show_delivery_charges(update, context)
    elif data == "pay_cod":
        context.user_data["voucher"]["payment"]["type"] = "COD"
        return await show_delivery_charges(update, context)
    return STATE_PAYMENT_TYPE

async def handle_full_paid_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    method = query.data.split("_")[1].title()
    if method == "Kpay": method = "KPay"
    if method == "Ayapay": method = "AYAPay"
    
    context.user_data["voucher"]["payment"]["method"] = method
    return await show_delivery_charges(update, context)

async def show_delivery_charges(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["voucher"]["payment"]["delivery_paid"] = False
    context.user_data["voucher"]["payment"]["delivery_amount"] = 25000.0
    
    items = context.user_data["voucher"]["items"]
    grand_total = sum(item["total"] for item in items)
    del_amount = 25000.0
    total_sum = grand_total + del_amount
    
    pay_type = context.user_data["voucher"]["payment"].get("type", "")
    
    rows = [
        [InlineKeyboardButton("🆗 OK", callback_data="del_confirm_ok")],
        [InlineKeyboardButton("❌ Cancel Order", callback_data="v_cancel")]
    ]
    
    text = (
        f"ℹ️ <b>Delivery Charges & Order Total:</b>\n\n"
        f"📋 Payment Type: <b>{pay_type}</b>\n"
        f"💵 Items Total: <b>{grand_total:,.0f} VND</b>\n"
        f"🛵 Delivery Charges: <b>{del_amount:,.0f} VND</b>\n"
        f"---------------------------\n"
        f"💰 <b>Total Amount: {total_sum:,.0f} VND</b>"
    )
    
    query = update.callback_query
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return STATE_DELIVERY_AMOUNT

async def handle_delivery_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    pay_type = context.user_data["voucher"]["payment"].get("type", "")
    if pay_type == "Pre Paid":
        return await show_prepaid_qr(update, context)
    else:
        return await generate_and_send_pdf(update, context)

async def show_prepaid_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    
    # Send payment QR code image
    base_dir = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(base_dir, "payment_qr.jpg")
    if os.path.exists(image_path):
        try:
            with open(image_path, "rb") as photo_file:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo_file,
                    caption="💳 Pre Paid ဖြင့် ငွေချေရန် QR ကုဒ် ဖြစ်ပါသည်။"
                )
        except Exception as e:
            logger.error(f"Error sending payment QR: {e}")
            
    rows = [
        [InlineKeyboardButton("❌ Cancel Order", callback_data="v_cancel")]
    ]
    await query.edit_message_text(
        "ငွေပေးချေပြီးပါက Transition Slip (ငွေလွှဲဖြတ်ပိုင်း) ကို ပေးပို့ပေးပါရန်။",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return STATE_DELIVERY_PAID

async def handle_payment_slip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Check if a photo or document was uploaded
    photo = None
    if update.message.photo:
        photo = update.message.photo[-1]
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        photo = update.message.document

    if not photo:
        await update.message.reply_text("⚠️ ကျေးဇူးပြု၍ ငွေလွှဲစလစ် ဓာတ်ပုံကိုသာ ပေးပို့ပေးပါရန်။")
        return STATE_DELIVERY_PAID

    msg = await update.message.reply_text("📥 ငွေလွှဲစလစ်ကို သိမ်းဆည်းနေပါသည်...")

    try:
        # Download photo
        file_obj = await context.bot.get_file(photo.file_id)
        
        import tempfile
        import uuid
        customer_name = context.user_data["voucher"]["customer"].get("name", "customer")
        ext = ".jpg"
        if hasattr(photo, "file_name") and photo.file_name:
            _, ext = os.path.splitext(photo.file_name)
        if not ext:
            ext = ".jpg"
            
        local_filename = f"slip_{uuid.uuid4().hex[:8]}{ext}"
        local_path = os.path.join(tempfile.gettempdir(), local_filename)
        await file_obj.download_to_drive(local_path)
        
        # Upload to Google Drive
        drive_folder_id = "1ztev83FQZfqgNbUKNTKAmri0RQ5mCASY"
        drive_filename = f"Slip_{customer_name}_{datetime.now().strftime('%y%m%d_%H%M%S')}{ext}"
        
        drive_file_id = sheet.upload_file_to_drive(local_path, drive_filename, drive_folder_id)
        
        # Save drive file ID in context payment info if needed
        context.user_data["voucher"]["payment"]["slip_drive_id"] = drive_file_id
        
        # Clean up local file
        if os.path.exists(local_path):
            os.remove(local_path)
            
        await msg.edit_text("✅ ငွေလွှဲစလစ်ကို Google Drive သို့ သိမ်းဆည်းပြီးပါပြီ။")
    except Exception as exc:
        logger.error(f"Error handling payment slip: {exc}")
        await msg.edit_text("⚠️ ငွေလွှဲစလစ် သိမ်းဆည်းရာတွင် အမှားအယွင်းရှိခဲ့သော်လည်း ဘောက်ချာ ဆက်လက်ထုတ်ပေးပါမည်။")

    # Generate and send PDF
    return await generate_and_send_pdf(update, context)

import uuid

async def generate_and_send_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    customer = context.user_data["voucher"]["customer"]
    items = context.user_data["voucher"]["items"]
    payment = context.user_data["voucher"]["payment"]
    chat_id = update.effective_chat.id
    
    msg = await update.effective_message.reply_text("📄 ဘောက်ချာ PDF နှင့် အချက်အလက်များ သိမ်းဆည်းနေပါသည်...")
    
    # Generate Unique Order ID
    order_id = str(uuid.uuid4())[:8].upper()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Generate Tracking Number (datetime-based, at least 6 digits: YYMMDDHHmmss)
    tracking_number = datetime.now().strftime("%y%m%d%H%M%S")
    
    # Save to Google Sheets
    sheet.save_order_record(order_id, date_str, customer, items, payment, tracking_number)
    
    # Reduce stock in product sheet
    sheet.reduce_stock(items)
    
    pdf_filename = f"voucher_{chat_id}_{int(datetime.now().timestamp())}.pdf"
    import tempfile
    pdf_path = os.path.join(tempfile.gettempdir(), pdf_filename)
    
    try:
        generate_voucher_pdf(customer, items, payment, pdf_path, tracking_number)
        
        # Send PDF document to user
        with open(pdf_path, "rb") as pdf_file:
            await context.bot.send_document(
                chat_id=chat_id,
                document=pdf_file,
                filename="Voucher.pdf",
                caption="📄 အလင်းအိမ် မုန့်ဆိုင် ဘောက်ချာ ဖြစ်ပါသည်။"
            )
            
        # Clean up local file
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            
    except Exception as exc:
        logger.error(f"Error generating or sending PDF: {exc}")
        await msg.edit_text("❌ ဘောက်ချာ PDF ဖန်တီးရာတွင် အမှားအယွင်းရှိခဲ့ပါသည်။")
        
    # Return to Main Menu options
    from bot import main_menu_kb
    await context.bot.send_message(
        chat_id=chat_id,
        text="🏠 ပင်မစာမျက်နှာသို့ ပြန်ရောက်ပါပြီ။",
        reply_markup=main_menu_kb()
    )
    
    return ConversationHandler.END

async def cancel_voucher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Handles cancel at any stage
    query = update.callback_query
    chat_id = None
    if query:
        await query.answer()
        chat_id = query.message.chat.id
        await query.edit_message_text("❌ ဘောက်ချာ ဖွင့်ခြင်းကို ဖျက်သိမ်းလိုက်ပါပြီ။")
    else:
        chat_id = update.message.chat.id
        await update.message.reply_text("❌ ဘောက်ချာ ဖွင့်ခြင်းကို ဖျက်သိမ်းလိုက်ပါပြီ။")
        
    # Clear user data
    if "voucher" in context.user_data:
        del context.user_data["voucher"]
        
    # Import main menu keyboard
    from bot import main_menu_kb
    await context.bot.send_message(
        chat_id=chat_id,
        text="🏠 ပင်မစာမျက်နှာသို့ ပြန်ရောက်ပါပြီ။",
        reply_markup=main_menu_kb()
    )
    return ConversationHandler.END

def build_voucher_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_voucher, pattern="^menu_voucher$")
        ],
        states={
            STATE_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_name),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_address),
                CallbackQueryHandler(back_to_name, pattern="^back_to_name$"),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_PHONE1: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_phone1),
                CallbackQueryHandler(back_to_address, pattern="^back_to_address$"),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_PHONE2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_phone2),
                CallbackQueryHandler(skip_phone2, pattern="^v_skip$"),
                CallbackQueryHandler(back_to_phone1, pattern="^back_to_phone1$"),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_SELECT_CATEGORY: [
                CallbackQueryHandler(handle_voucher_category_select, pattern="^vcat_"),
                CallbackQueryHandler(handle_all_products_select, pattern="^v_all_products$"),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_SELECT_PRODUCT: [
                CallbackQueryHandler(handle_voucher_product_select, pattern="^vprod_"),
                CallbackQueryHandler(send_voucher_categories, pattern="^v_back_categories$"),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_PRODUCT_DETAIL: [
                CallbackQueryHandler(handle_add_confirm, pattern="^v_add_confirm$"),
                CallbackQueryHandler(handle_voucher_category_select, pattern="^vcat_"),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_INPUT_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input_count),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_DECIDE_NEXT: [
                CallbackQueryHandler(handle_one_more, pattern="^v_one_more$"),
                CallbackQueryHandler(handle_finish_order, pattern="^v_finish$"),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_PAYMENT_TYPE: [
                CallbackQueryHandler(handle_payment_type, pattern="^pay_"),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_FULL_PAID_METHOD: [
                CallbackQueryHandler(handle_full_paid_method, pattern="^method_"),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_DELIVERY_AMOUNT: [
                CallbackQueryHandler(handle_delivery_confirm, pattern="^del_confirm_ok$"),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ],
            STATE_DELIVERY_PAID: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_payment_slip),
                CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_voucher),
            CallbackQueryHandler(cancel_voucher, pattern="^v_cancel$")
        ],
        name="voucher_conversation",
        persistent=False
    )
