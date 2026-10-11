"""
Hawassa Rental & Marketplace Telegram Bot — Fully Integrated Production Code (Railway Persistent Edition)
========================================================================================================
Features:
- Multi-Photo Posting Support (Album/Media Group publishing)
- Custom Product Description Step in /post
- Strict Item-Level Filtering
- Price Proximity Sorting for Out-of-Budget Related Items
- Railway Persistent Volume + DB_PATH Environment Variable
- Multi-Category Support with Bilingual Admin Post Creator
- Expanded Categories: Home, Phone, Laptop, Electronics, and Car/Vehicle
- Dynamic Custom Categories (e.g. Food): created from /post, saved in DB, shown in search
"""

import html
import logging
import os
import re
import sqlite3
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters
)

# ---------- Configuration & Setup ----------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/hawassa_rental")

raw_admin_ids = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "0"))
ADMIN_IDS = {int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()}

raw_support = os.getenv("SUPPORT_USERNAME", "Jatech_support")
SUPPORT_USERNAMES = [u.strip().lstrip("@") for u in raw_support.split(",") if u.strip()]
if not SUPPORT_USERNAMES:
    SUPPORT_USERNAMES = ["Jatech_support"]

DB_FILE = os.getenv("DB_PATH", "/data/rental_bot.db")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SUBCITIES = [
    "Tabor", "Hawela-Tula", "Addis Ketema", "Hayek Dare",
    "Menehariya", "Misrak", "Bahile Adarash", "Mehal Ketema",
]

PHONE_BRANDS = ["iPhone", "Samsung", "Tecno / Infinix", "Xiaomi", "Other Phone"]
LAPTOP_BRANDS = ["HP", "Dell", "Lenovo", "MacBook / Apple", "ASUS", "Other Laptop"]
ELECTRONIC_ITEMS = ["Gimbal", "Ring light / Light", "Mic / Microphone", "Camera / Video", "Other Electronics"]
CAR_BRANDS = ["Toyota", "Hyundai", "Suzuki", "Nissan", "Other Car"]

SUBCITY_MAP = {
    "tabor": "Tabor", "ታቦር": "Tabor",
    "hawela": "Hawela-Tula", "ቱላ": "Hawela-Tula", "ሐዋላ": "Hawela-Tula",
    "addis ketema": "Addis Ketema", "አዲስ ከተማ": "Addis Ketema",
    "hayek dare": "Hayek Dare", "ኃይቅ ዳር": "Hayek Dare", "ሀይቅ ዳር": "Hayek Dare",
    "menehariya": "Menehariya", "መነሀሪያ": "Menehariya", "መነሃሪያ": "Menehariya",
    "misrak": "Misrak", "ምስራቅ": "Misrak",
    "bahile adarash": "Bahile Adarash", "ባህለ አዳራሽ": "Bahile Adarash", "ባህል አዳራሽ": "Bahile Adarash",
    "mehal ketema": "Mehal Ketema", "ማዕከል ከተማ": "Mehal Ketema", "መሀል ከተማ": "Mehal Ketema"
}

PHONE_BUDGETS = [
    ("5000 - 10000 ብር / ETB", 5000, 10000),
    ("10000 - 20000 ብር / ETB", 10000, 20000),
    ("20000 - 30000 ብር / ETB", 20000, 30000),
    ("30000 - 50000 ብር / ETB", 30000, 50000),
    ("50000 - 100000 ብር / ETB", 50000, 100000),
    ("100000+ ብር / ETB", 100000, None),
]

LAPTOP_BUDGETS = [
    ("10000 - 20000 ብር / ETB", 10000, 20000),
    ("20000 - 30000 ብር / ETB", 20000, 30000),
    ("30000 - 50000 ብር / ETB", 30000, 50000),
    ("50000 - 100000 ብር / ETB", 50000, 100000),
    ("100000+ ብር / ETB", 100000, None),
]

ELECTRONIC_BUDGETS = [
    ("1000 - 3000 ብር / ETB", 1000, 3000),
    ("3000 - 7000 ብር / ETB", 3000, 7000),
    ("7000 - 15000 ብር / ETB", 7000, 15000),
    ("15000 - 30000 ብር / ETB", 15000, 30000),
    ("30000+ ብር / ETB", 30000, None),
]

CAR_BUDGETS = [
    ("500,000 - 1,000,000 ብር / ETB", 500000, 1000000),
    ("1,000,000 - 2,500,000 ብር / ETB", 1000000, 2500000),
    ("2,500,000 - 5,000,000 ብር / ETB", 2500000, 5000000),
    ("5,000,000+ ብር / ETB", 5000000, None),
]

HOME_BUDGETS = [
    ("2000 - 5000 ብር / ETB", 2000, 5000),
    ("5000 - 10000 ብር / ETB", 5000, 10000),
    ("10000 - 15000 ብር / ETB", 10000, 15000),
    ("15000+ ብር / ETB", 15000, None),
]

ROOM_TYPES = ["ባለ 1", "ባለ 2", "ባለ 3", "ባለ 4", "ሙሉ ግቢ"]
PHONE_REGEX = re.compile(r"(?:\+251|0)9\d{8}")


# ---------- Database Helper Functions ----------

def get_db():
    db_dir = os.path.dirname(DB_FILE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER UNIQUE,
                category TEXT DEFAULT 'Home',
                item_type TEXT,
                room TEXT,
                price INTEGER,
                phone TEXT,
                raw_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_category TEXT,
                last_item_type TEXT,
                last_room TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS category_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                UNIQUE(category_id, name)
            )
        """)
        conn.commit()


def register_user(user):
    with get_db() as conn:
        user_exists = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user.id,)).fetchone()
        if not user_exists:
            conn.execute("""
                INSERT INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
            """, (user.id, user.username, user.first_name))
        else:
            conn.execute("""
                UPDATE users SET username = ?, first_name = ? WHERE user_id = ?
            """, (user.username, user.first_name, user.id))
        conn.commit()


def update_user_search(user_id, category=None, item_type=None, room=None):
    with get_db() as conn:
        if category:
            conn.execute("UPDATE users SET last_category = ? WHERE user_id = ?", (category, user_id))
        if item_type:
            conn.execute("UPDATE users SET last_item_type = ? WHERE user_id = ?", (item_type, user_id))
        if room:
            conn.execute("UPDATE users SET last_room = ? WHERE user_id = ?", (room, user_id))
        conn.commit()


def save_listing(message_id, category, item_type, room, price, phone, raw_text):
    if not message_id:
        return
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO listings (message_id, category, item_type, room, price, phone, raw_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (message_id, category, item_type, room, price, phone, raw_text))
        conn.commit()


def delete_listing(message_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM listings WHERE message_id = ?", (message_id,))
        conn.commit()
        return cursor.rowcount > 0


# ---------- Custom (Admin-Created) Categories ----------

BUILTIN_CATEGORIES = {"Home", "Phone", "Laptop", "Electronics", "Car"}

CUSTOM_BUDGETS = [
    ("ሁሉም ዋጋ / Any price", 0, None),
    ("እስከ 500 ብር / Up to 500 ETB", 0, 500),
    ("500 - 2000 ብር / ETB", 500, 2000),
    ("2000 - 10000 ብር / ETB", 2000, 10000),
    ("10000 - 50000 ብር / ETB", 10000, 50000),
    ("50000+ ብር / ETB", 50000, None),
]


def get_custom_categories():
    with get_db() as conn:
        return conn.execute("SELECT id, name FROM categories ORDER BY id").fetchall()


def get_custom_category_by_id(cat_id):
    with get_db() as conn:
        return conn.execute("SELECT id, name FROM categories WHERE id = ?", (cat_id,)).fetchone()


def get_custom_category_by_name(name):
    with get_db() as conn:
        return conn.execute("SELECT id, name FROM categories WHERE name = ?", (name,)).fetchone()


def validate_category_name(name):
    if len(name) < 2 or len(name) > 40:
        return "❌ ስሙ ከ2 እስከ 40 ፊደል መሆን አለበት / Name must be 2-40 characters. Try again:"
    if name.lower() in {c.lower() for c in BUILTIN_CATEGORIES}:
        return "❌ ይህ ምድብ አስቀድሞ አለ / This is already a built-in category. Type a different name:"
    return None


def add_custom_category(name):
    """Returns (category_id, created). If the name already exists, returns the existing id."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM categories WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if existing:
            return existing["id"], False
        cursor = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        return cursor.lastrowid, True


def delete_custom_category(cat_id):
    with get_db() as conn:
        conn.execute("DELETE FROM category_items WHERE category_id = ?", (cat_id,))
        cursor = conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_category_items(cat_id):
    with get_db() as conn:
        return conn.execute(
            "SELECT id, name FROM category_items WHERE category_id = ? ORDER BY id", (cat_id,)
        ).fetchall()


def get_category_item_by_id(item_id):
    with get_db() as conn:
        return conn.execute("SELECT id, name FROM category_items WHERE id = ?", (item_id,)).fetchone()


def add_category_item(cat_id, name):
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM category_items WHERE category_id = ? AND LOWER(name) = LOWER(?)",
            (cat_id, name)
        ).fetchone()
        if existing:
            return existing["id"]
        cursor = conn.execute("INSERT INTO category_items (category_id, name) VALUES (?, ?)", (cat_id, name))
        conn.commit()
        return cursor.lastrowid


def category_aliases(name):
    """'🍔 Food / ምግብ' -> {'food', 'ምግብ', '🍔 food / ምግብ' (cleaned)}"""
    aliases = set()
    for part in [name] + re.split(r"[/|()]", name):
        cleaned = re.sub(r"^[^\w]+|[^\w]+$", "", part.strip()).lower()
        if len(cleaned) >= 2:
            aliases.add(cleaned)
    return aliases


def detect_custom_category(text_lower):
    """Detects a custom category inside a channel post / forwarded post."""
    for cat in get_custom_categories():
        if any(alias in text_lower for alias in category_aliases(cat["name"])):
            item_type = "Other"
            for item in get_category_items(cat["id"]):
                if item["name"].lower() in text_lower:
                    item_type = item["name"]
                    break
            return cat["name"], item_type
    return None


def parse_listing_text(text):
    text_lower = text.lower()
    
    category = "Home"
    custom_match = detect_custom_category(text_lower)
    if custom_match:
        category, item_type = custom_match
    elif any(k in text_lower for k in ["gimbal", "ጂምባል"]):
        category = "Electronics"
        item_type = "Gimbal"
    elif any(k in text_lower for k in ["ring light", "light", "መብራት"]):
        category = "Electronics"
        item_type = "Ring light / Light"
    elif any(k in text_lower for k in ["mic", "microphone", "ማይክ"]):
        category = "Electronics"
        item_type = "Mic / Microphone"
    elif any(k in text_lower for k in ["camera", "ካሜራ"]):
        category = "Electronics"
        item_type = "Camera / Video"
    elif any(k in text_lower for k in ["iphone", "samsung", "tecno", "infinix", "xiaomi", "ስልክ", "phone"]):
        category = "Phone"
        item_type = "Other Phone"
        for brand in PHONE_BRANDS:
            if brand.lower().split("/")[0].strip() in text_lower:
                item_type = brand
                break
    elif any(k in text_lower for k in ["hp", "dell", "lenovo", "macbook", "asus", "laptop", "core i", "ላፕቶፕ"]):
        category = "Laptop"
        item_type = "Other Laptop"
        for brand in LAPTOP_BRANDS:
            if brand.lower().split("/")[0].strip() in text_lower:
                item_type = brand
                break
    elif any(k in text_lower for k in ["toyota", "hyundai", "suzuki", "nissan", "መኪና", "car", "vitz", "yaris"]):
        category = "Car"
        item_type = "Other Car"
        for brand in CAR_BRANDS:
            if brand.lower().split("/")[0].strip() in text_lower:
                item_type = brand
                break
    else:
        category = "Home"
        item_type = "Tabor"
        for key, val in SUBCITY_MAP.items():
            if key in text_lower:
                item_type = val
                break

    room = "ባለ 1"
    if category == "Home":
        for r in ROOM_TYPES:
            if r in text:
                room = r
                break

    price = None
    price_match = re.findall(r'\b\d{3,8}\b', text)
    if price_match:
        price = int(price_match[0])
        
    phone_match = PHONE_REGEX.search(text)
    phone = phone_match.group(0) if phone_match else ""
    
    return category, item_type, room, price, phone


def search_listings(category, item_type, room, budget_low, budget_high):
    with get_db() as conn:
        cursor = conn.cursor()
        
        if category == "Home":
            cursor.execute("SELECT * FROM listings WHERE category = ? AND item_type = ? AND room = ?", (category, item_type, room))
            rows = cursor.fetchall()
            if not rows:
                cursor.execute("SELECT * FROM listings WHERE category = ? AND item_type = ?", (category, item_type))
                rows = cursor.fetchall()
        else:
            cursor.execute("SELECT * FROM listings WHERE category = ? AND item_type = ?", (category, item_type))
            rows = cursor.fetchall()

    exact = []
    related = []

    if budget_low is not None and budget_high is not None:
        target_price = (budget_low + budget_high) / 2
    elif budget_low is not None:
        target_price = budget_low
    else:
        target_price = 0

    for row in rows:
        price = row["price"]
        if price is not None and budget_low is not None:
            in_range = True
            if price < budget_low: in_range = False
            if budget_high is not None and price > budget_high: in_range = False
            
            if in_range:
                exact.append(row)
            else:
                related.append(row)
        else:
            exact.append(row)

    if target_price and related:
        related.sort(key=lambda r: abs((r["price"] or 0) - target_price))

    return exact, related


async def is_user_joined(bot, user_id: int) -> bool:
    if not CHANNEL_ID: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        return True


# ---------- Inline Keyboards ----------

def get_force_join_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📢 ቻናሉን ይቀላቀሉ (Join Channel)", url=CHANNEL_LINK)],[InlineKeyboardButton("✅ አረጋግጥ (Verify Join)", callback_data="check_join")]])

def get_language_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="lang:am"), InlineKeyboardButton("English 🇬🇧", callback_data="lang:en")]])

def get_role_keyboard(lang="am"):
    if lang == "am":
        buttons = [
            [InlineKeyboardButton("🏠 ማስታወቂያ ማውጣት (Post / Advertise)", callback_data="role:landlord")],
            [InlineKeyboardButton("🔍 ቤት ወይም ዕቃ መፈለግ (Search)", callback_data="role:tenant")],
            [InlineKeyboardButton("🌐 ቋንቋ ቀይር (Change Language)", callback_data="back_to_lang")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("🏠 Post / Advertise Property", callback_data="role:landlord")],
            [InlineKeyboardButton("🔍 Search / Find Property", callback_data="role:tenant")],
            [InlineKeyboardButton("🌐 Change Language", callback_data="back_to_lang")]
        ]
    return InlineKeyboardMarkup(buttons)

def get_category_keyboard(lang="am"):
    if lang == "am":
        buttons = [
            [InlineKeyboardButton("🏠 ቤት (Home / Residential)", callback_data="cat:Home")],
            [InlineKeyboardButton("📱 ስልክ (Phones)", callback_data="cat:Phone")],
            [InlineKeyboardButton("💻 ላፕቶፕ (Laptops)", callback_data="cat:Laptop")],
            [InlineKeyboardButton("📷 ኤሌክትሮኒክስ (Electronics)", callback_data="cat:Electronics")],
            [InlineKeyboardButton("🚗 መኪና (Car / Vehicle)", callback_data="cat:Car")],
            [InlineKeyboardButton("⬅️ ተመለስ (Back)", callback_data="back_to_role")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("🏠 Home (Residential)", callback_data="cat:Home")],
            [InlineKeyboardButton("📱 Phone", callback_data="cat:Phone")],
            [InlineKeyboardButton("💻 Laptop", callback_data="cat:Laptop")],
            [InlineKeyboardButton("📷 Electronics", callback_data="cat:Electronics")],
            [InlineKeyboardButton("🚗 Car / Vehicle", callback_data="cat:Car")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_role")]
        ]
    # Admin-created categories (e.g. Food) appear before the Back button
    custom_buttons = [
        [InlineKeyboardButton(c["name"], callback_data=f"cat:custom_{c['id']}")]
        for c in get_custom_categories()
    ]
    buttons[-1:-1] = custom_buttons
    return InlineKeyboardMarkup(buttons)


def get_custom_item_keyboard(cat_id, lang="am"):
    buttons = [
        [InlineKeyboardButton(i["name"], callback_data=f"citem:{i['id']}")]
        for i in get_category_items(cat_id)
    ]
    back_label = "⬅️ ተመለስ (Back)" if lang == "am" else "⬅️ Back"
    buttons.append([InlineKeyboardButton(back_label, callback_data="back_to_category")])
    return InlineKeyboardMarkup(buttons)

def get_landlord_keyboard(lang="am"):
    buttons = []
    for u in SUPPORT_USERNAMES:
        label = f"💬 አድሚን ያናግሩ (@{u})" if lang == "am" else f"💬 Contact Admin (@{u})"
        buttons.append([InlineKeyboardButton(label, url=f"https://t.me/{u}")])
    main_menu_label = "🏠 ወደ ዋናው ማውጫ ይመለሱ" if lang == "am" else "🏠 Main Menu"
    buttons.append([InlineKeyboardButton(main_menu_label, callback_data="restart_search")])
    return InlineKeyboardMarkup(buttons)

def get_subcity_keyboard(lang="am"):
    buttons = [[InlineKeyboardButton(sc, callback_data=f"subcity:{sc}")] for sc in SUBCITIES]
    back_label = "⬅️ ተመለስ (Back)" if lang == "am" else "⬅️ Back"
    buttons.append([InlineKeyboardButton(back_label, callback_data="back_to_category")])
    return InlineKeyboardMarkup(buttons)

def get_phone_brand_keyboard(lang="am"):
    buttons = [[InlineKeyboardButton(brand, callback_data=f"phone_brand:{brand}")] for brand in PHONE_BRANDS]
    back_label = "⬅️ ተመለስ (Back)" if lang == "am" else "⬅️ Back"
    buttons.append([InlineKeyboardButton(back_label, callback_data="back_to_category")])
    return InlineKeyboardMarkup(buttons)

def get_laptop_brand_keyboard(lang="am"):
    buttons = [[InlineKeyboardButton(brand, callback_data=f"laptop_brand:{brand}")] for brand in LAPTOP_BRANDS]
    back_label = "⬅️ ተመለስ (Back)" if lang == "am" else "⬅️ Back"
    buttons.append([InlineKeyboardButton(back_label, callback_data="back_to_category")])
    return InlineKeyboardMarkup(buttons)

def get_electronics_item_keyboard(lang="am"):
    buttons = [[InlineKeyboardButton(item, callback_data=f"elec_item:{item}")] for item in ELECTRONIC_ITEMS]
    back_label = "⬅️ ተመለስ (Back)" if lang == "am" else "⬅️ Back"
    buttons.append([InlineKeyboardButton(back_label, callback_data="back_to_category")])
    return InlineKeyboardMarkup(buttons)

def get_car_brand_keyboard(lang="am"):
    buttons = [[InlineKeyboardButton(brand, callback_data=f"car_brand:{brand}")] for brand in CAR_BRANDS]
    back_label = "⬅️ ተመለስ (Back)" if lang == "am" else "⬅️ Back"
    buttons.append([InlineKeyboardButton(back_label, callback_data="back_to_category")])
    return InlineKeyboardMarkup(buttons)

def get_budget_keyboard(category, lang="am"):
    if category == "Phone":
        budgets = PHONE_BUDGETS
        back_target = "back_to_phone_brand"
    elif category == "Laptop":
        budgets = LAPTOP_BUDGETS
        back_target = "back_to_laptop_brand"
    elif category == "Electronics":
        budgets = ELECTRONIC_BUDGETS
        back_target = "back_to_elec_item"
    elif category == "Car":
        budgets = CAR_BUDGETS
        back_target = "back_to_car_brand"
    elif category not in BUILTIN_CATEGORIES:
        budgets = CUSTOM_BUDGETS
        back_target = "back_to_custom_item"
    else:
        budgets = HOME_BUDGETS
        back_target = "back_to_subcity"

    buttons = [[InlineKeyboardButton(label, callback_data=f"budget:{low}:{high or ''}")] for label, low, high in budgets]
    back_label = "⬅️ ተመለስ (Back)" if lang == "am" else "⬅️ Back"
    main_menu_label = "🏠 ወደ ዋናው ማውጫ ይመለሱ" if lang == "am" else "🏠 Main Menu"
    buttons.append([InlineKeyboardButton(back_label, callback_data=back_target)])
    buttons.append([InlineKeyboardButton(main_menu_label, callback_data="restart_search")])
    return InlineKeyboardMarkup(buttons)

def get_room_keyboard(lang="am"):
    buttons = [[InlineKeyboardButton(r, callback_data=f"room:{r}")] for r in ROOM_TYPES]
    back_label = "⬅️ ተመለስ (Back)" if lang == "am" else "⬅️ Back"
    main_menu_label = "🏠 ወደ ዋናው ማውጫ ይመለሱ" if lang == "am" else "🏠 Main Menu"
    buttons.append([InlineKeyboardButton(back_label, callback_data="back_to_subcity")])
    buttons.append([InlineKeyboardButton(main_menu_label, callback_data="restart_search")])
    return InlineKeyboardMarkup(buttons)

def get_result_action_keyboard(lang="am"):
    buttons = []
    for u in SUPPORT_USERNAMES:
        label = f"💬 ያናግሩ / Contact (@{u})"
        buttons.append([InlineKeyboardButton(label, url=f"https://t.me/{u}")])
    main_menu_label = "🏠 ወደ ዋናው ማውጫ ይመለሱ" if lang == "am" else "🏠 Main Menu"
    buttons.append([InlineKeyboardButton(main_menu_label, callback_data="restart_search")])
    return InlineKeyboardMarkup(buttons)

def get_broadcast_action_keyboard():
    buttons = []
    for u in SUPPORT_USERNAMES:
        buttons.append([InlineKeyboardButton(f"💬 አድሚን ያናግሩ / Contact (@{u})", url=f"https://t.me/{u}")])
    buttons.append([InlineKeyboardButton("🏠 ዋና ማውጫ / Main Menu", callback_data="restart_search")])
    return InlineKeyboardMarkup(buttons)


# ---------- Channel Listener & Forward Import ----------

async def on_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post or update.edited_channel_post
    if not post or not (post.text or post.caption): return
    if CHANNEL_ID and post.chat.id != CHANNEL_ID: return

    post_text = post.text or post.caption
    category, item_type, room, price, phone = parse_listing_text(post_text)

    save_listing(
        message_id=post.message_id,
        category=category,
        item_type=item_type,
        room=room,
        price=price,
        phone=phone,
        raw_text=post_text
    )


async def handle_forwarded_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    msg = update.message
    if not msg or not (msg.text or msg.caption): return

    text = msg.text or msg.caption
    category, item_type, room, price, phone = parse_listing_text(text)

    save_listing(msg.message_id, category, item_type, room, price, phone, text)
    await msg.reply_text(
        f"✅ <b>Post Imported Successfully!</b>\n\n"
        f"📦 <b>Category:</b> {category}\n"
        f"🏷️ <b>Item/Location:</b> {item_type}\n"
        f"🚪 <b>Room:</b> {room if category == 'Home' else 'N/A'}\n"
        f"💰 <b>Price:</b> {price} ETB\n"
        f"📞 <b>Phone:</b> {phone}",
        parse_mode="HTML"
    )


# ---------- States for Conversations ----------
(
    POST_PHOTO, POST_CATEGORY, POST_ITEM_TYPE, POST_ROOM, POST_PRICE,
    POST_DESCRIPTION, POST_PHONE, BROADCAST_MSG, POST_CUSTOM_NAME,
    POST_NEW_CATEGORY
) = range(10)


# ---------- Admin Post Creation Wizard ----------

async def start_post_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    context.user_data["admin_post"] = {"photos": []}
    
    done_button = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Done Sending Photos (ጨርሻለሁ)", callback_data="done_photos")]])
    await update.message.reply_text(
        "📸 <b>ማስታወቂያ መፍጠሪያ / Post Creator</b>\n\n"
        "እባክዎ የቤቱን ወይም የዕቃውን ፎቶዎች ይላኩ። (አንዱን ወይም በርካታ ፎቶዎችን መላክ ይችላሉ)\n"
        "ፎቶዎቹን ልከው ሲጨርሱ ከታች ያለውን <b>'Done Sending Photos'</b> የሚለውን ይጫኑ:",
        reply_markup=done_button,
        parse_mode="HTML"
    )
    return POST_PHOTO

def build_post_category_buttons():
    buttons = [
        [InlineKeyboardButton("🏠 ቤት (House / Residential)", callback_data="post_cat:Home")],
        [InlineKeyboardButton("📱 ስልክ (Phone)", callback_data="post_cat:Phone")],
        [InlineKeyboardButton("💻 ላፕቶፕ (Laptop)", callback_data="post_cat:Laptop")],
        [InlineKeyboardButton("📷 ኤሌክትሮኒክስ (Electronics)", callback_data="post_cat:Electronics")],
        [InlineKeyboardButton("🚗 መኪና (Car / Vehicle)", callback_data="post_cat:Car")],
    ]
    for c in get_custom_categories():
        buttons.append([InlineKeyboardButton(c["name"], callback_data=f"post_cat:custom_{c['id']}")])
    buttons.append([InlineKeyboardButton("➕ አዲስ ምድብ ጨምር (Add New Category)", callback_data="post_cat:NEW_CATEGORY")])
    return buttons


def build_post_custom_item_menu(cat_row):
    buttons = [
        [InlineKeyboardButton(i["name"], callback_data=f"post_item:#{i['id']}")]
        for i in get_category_items(cat_row["id"])
    ]
    buttons.append([InlineKeyboardButton("➕ አዲስ ጨምር (Add New)", callback_data="post_item:ADD_CUSTOM")])
    text = (
        f"🏷️ <b>{html.escape(cat_row['name'], quote=False)}</b>\n"
        "ዓይነት ይምረጡ ወይም አዲስ ይጨምሩ / Select item type or add a new one:"
    )
    return text, InlineKeyboardMarkup(buttons)


async def process_post_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        photos = context.user_data.get("admin_post", {}).get("photos", [])
        if not photos:
            await query.message.reply_text("❌ እባክዎ ቢያንስ አንድ ፎቶ ይላኩ! / Please send at least one photo first.")
            return POST_PHOTO

        buttons = build_post_category_buttons()
        await query.message.reply_text(
            "📦 <b>ምድብ ይምረጡ / Select Category:</b>\n\n"
            "እባክዎ የሚለጥፉትን ምድብ ይምረጡ (Choose category to post):",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
        return POST_CATEGORY

    photo_id = update.message.photo[-1].file_id
    if "admin_post" not in context.user_data:
        context.user_data["admin_post"] = {"photos": []}
    
    context.user_data["admin_post"]["photos"].append(photo_id)
    count = len(context.user_data["admin_post"]["photos"])
    
    done_button = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Done Sending Photos (ጨርሻለሁ)", callback_data="done_photos")]])
    await update.message.reply_text(
        f"✅ <b>{count} ፎቶ(ዎች) ተቀብለናል!</b> ተጨማሪ መላክ ይችላሉ ወይም ሲጨርሱ 'Done' የሚለውን ይጫኑ።",
        reply_markup=done_button,
        parse_mode="HTML"
    )
    return POST_PHOTO

async def process_post_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split(":", 1)[1]

    if category == "NEW_CATEGORY":
        await query.edit_message_text(
            "✍️ <b>አዲሱን ምድብ ስም ያስገቡ / Type the new category name:</b>\n"
            "<i>ምሳሌ / Example: 🍔 Food / ምግብ</i>",
            parse_mode="HTML"
        )
        return POST_NEW_CATEGORY

    if category.startswith("custom_"):
        cat_row = get_custom_category_by_id(int(category.split("_", 1)[1]))
        if not cat_row:
            await query.edit_message_text(
                "❌ ምድቡ አልተገኘም / Category not found. Choose again:",
                reply_markup=InlineKeyboardMarkup(build_post_category_buttons())
            )
            return POST_CATEGORY
        context.user_data["admin_post"]["category"] = cat_row["name"]
        context.user_data["admin_post"]["custom_cat_id"] = cat_row["id"]
        text, markup = build_post_custom_item_menu(cat_row)
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
        return POST_ITEM_TYPE

    context.user_data["admin_post"]["category"] = category

    if category == "Home":
        buttons = [[InlineKeyboardButton(sc, callback_data=f"post_item:{sc}")] for sc in SUBCITIES]
        await query.edit_message_text(
            "📍 <b>ክፍለ ከተማ ይምረጡ / Select Subcity (House):</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
        return POST_ITEM_TYPE
    elif category == "Phone":
        buttons = [[InlineKeyboardButton(b, callback_data=f"post_item:{b}")] for b in PHONE_BRANDS]
        buttons.append([InlineKeyboardButton("➕ አዲስ ጨምር (Add New)", callback_data="post_item:ADD_CUSTOM")])
        await query.edit_message_text(
            "📱 <b>የስልክ ብራንድ ይምረጡ / Select Phone Brand:</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
        return POST_ITEM_TYPE
    elif category == "Laptop":
        buttons = [[InlineKeyboardButton(b, callback_data=f"post_item:{b}")] for b in LAPTOP_BRANDS]
        buttons.append([InlineKeyboardButton("➕ አዲስ ጨምር (Add New)", callback_data="post_item:ADD_CUSTOM")])
        await query.edit_message_text(
            "💻 <b>የላፕቶፕ ብራንድ ይምረጡ / Select Laptop Brand:</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
        return POST_ITEM_TYPE
    elif category == "Car":
        buttons = [[InlineKeyboardButton(b, callback_data=f"post_item:{b}")] for b in CAR_BRANDS]
        buttons.append([InlineKeyboardButton("➕ አዲስ ጨምር (Add New)", callback_data="post_item:ADD_CUSTOM")])
        await query.edit_message_text(
            "🚗 <b>የመኪና ብራንድ ይምረጡ / Select Car Brand:</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
        return POST_ITEM_TYPE
    else:
        buttons = [[InlineKeyboardButton(item, callback_data=f"post_item:{item}")] for item in ELECTRONIC_ITEMS]
        buttons.append([InlineKeyboardButton("➕ አዲስ ጨምር (Add New Custom Item)", callback_data="post_item:ADD_CUSTOM")])
        await query.edit_message_text(
            "📷 <b>የኤሌክትሮኒክስ ዓይነት ይምረጡ / Select Electronic Item:</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
        return POST_ITEM_TYPE

async def process_post_item_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_type = query.data.split(":", 1)[1]
    category = context.user_data["admin_post"]["category"]

    if item_type.startswith("#"):
        item_row = get_category_item_by_id(int(item_type[1:]))
        if not item_row:
            await query.edit_message_text(
                "❌ ዓይነቱ አልተገኘም / Item not found. Choose a category again:",
                reply_markup=InlineKeyboardMarkup(build_post_category_buttons())
            )
            return POST_CATEGORY
        item_type = item_row["name"]

    if item_type == "ADD_CUSTOM":
        await query.edit_message_text(
            "✍️ <b>እባክዎ አዲሱን ስም/ዓይነት ያስገቡ (Type custom item/brand name):</b>",
            parse_mode="HTML"
        )
        return POST_CUSTOM_NAME

    context.user_data["admin_post"]["item_type"] = item_type

    if category == "Home":
        buttons = [[InlineKeyboardButton(r, callback_data=f"post_room:{r}")] for r in ROOM_TYPES]
        await query.edit_message_text(
            "🚪 <b>የክፍል ብዛት ይምረጡ / Select Room Type:</b>",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
        return POST_ROOM
    else:
        context.user_data["admin_post"]["room"] = "N/A"
        await query.edit_message_text(
            "💰 <b>ዋጋ ያስገቡ (በብር / ETB):\n<i>ምሳሌ: 25000 (Enter price in numbers):</i></b>",
            parse_mode="HTML"
        )
        return POST_PRICE

async def process_custom_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    custom_name = update.message.text.strip()
    if not custom_name or len(custom_name) > 40:
        await update.message.reply_text("❌ ስሙ ከ1 እስከ 40 ፊደል መሆን አለበት / Name must be 1-40 characters. Try again:")
        return POST_CUSTOM_NAME
    category = context.user_data["admin_post"]["category"]
    
    context.user_data["admin_post"]["item_type"] = custom_name
    
    if category == "Phone" and custom_name not in PHONE_BRANDS:
        PHONE_BRANDS.insert(-1, custom_name)
    elif category == "Laptop" and custom_name not in LAPTOP_BRANDS:
        LAPTOP_BRANDS.insert(-1, custom_name)
    elif category == "Electronics" and custom_name not in ELECTRONIC_ITEMS:
        ELECTRONIC_ITEMS.insert(-1, custom_name)
    elif category == "Car" and custom_name not in CAR_BRANDS:
        CAR_BRANDS.insert(-1, custom_name)
    elif category not in BUILTIN_CATEGORIES:
        custom_cat_id = context.user_data["admin_post"].get("custom_cat_id")
        if custom_cat_id:
            add_category_item(custom_cat_id, custom_name)

    context.user_data["admin_post"]["room"] = "N/A"
    await update.message.reply_text(
        "💰 <b>ዋጋ ያስገቡ (በብር / ETB):\n<i>ምሳሌ: 25000 (Enter price in numbers):</i></b>",
        parse_mode="HTML"
    )
    return POST_PRICE


async def process_new_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    error = validate_category_name(name)
    if error:
        await update.message.reply_text(error)
        return POST_NEW_CATEGORY

    cat_id, created = add_custom_category(name)
    cat_row = get_custom_category_by_id(cat_id)
    context.user_data["admin_post"]["category"] = cat_row["name"]
    context.user_data["admin_post"]["custom_cat_id"] = cat_row["id"]

    note = (
        "✅ አዲስ ምድብ ተጨምሯል! / New category added!\n\n" if created
        else "ℹ️ ምድቡ አስቀድሞ አለ / Category already exists, using it.\n\n"
    )
    text, markup = build_post_custom_item_menu(cat_row)
    await update.message.reply_text(note + text, reply_markup=markup, parse_mode="HTML")
    return POST_ITEM_TYPE


async def process_post_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["admin_post"]["room"] = query.data.split(":", 1)[1]
    await query.edit_message_text(
        "💰 <b>የቤቱን ዋጋ ያስገቡ (በብር / ETB):\n<i>ምሳሌ: 8000 (Enter price):</i></b>",
        parse_mode="HTML"
    )
    return POST_PRICE

async def process_post_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clean_price = re.sub(r"[^\d]", "", update.message.text.strip())
    if not clean_price:
        await update.message.reply_text("❌ እባክዎ ቁጥር ብቻ ያስገቡ / Please enter numbers only:")
        return POST_PRICE
    context.user_data["admin_post"]["price"] = int(clean_price)
    
    await update.message.reply_text(
        "📝 <b>ስለ እቃው/ቤቱ ማብራሪያ ያስገቡ / Add Description:</b>\n"
        "<i>(የእቃውን ሁኔታ፣ ዝርዝር መረጃ ወይም ተጨማሪ መግለጫ እዚህ ይጻፉ)</i>",
        parse_mode="HTML"
    )
    return POST_DESCRIPTION

async def process_post_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["admin_post"]["description"] = update.message.text.strip()
    await update.message.reply_text(
        "📞 <b>የስልክ ቁጥር ያስገቡ / Enter Phone Number:</b>\n<i>ምሳሌ: 0911223344</i>",
        parse_mode="HTML"
    )
    return POST_PHONE

async def process_post_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["admin_post"]["phone"] = update.message.text.strip()
    data = context.user_data["admin_post"]

    admin_contacts_str = " | ".join([f"@{u}" for u in SUPPORT_USERNAMES])
    room_line = f"🚪 <b>ክፍል (Room):</b> {data['room']}\n" if data['category'] == "Home" else ""
    desc_line = f"📝 <b>መግለጫ (Description):</b> {data.get('description', 'N/A')}\n"
    
    caption = (
        f"🔥 <b>{html.escape(data['category'], quote=False)} ማስታወቂያ</b>\n\n"
        f"🏷️ <b>ዓይነት/ቦታ (Type/Location):</b> {html.escape(data['item_type'], quote=False)}\n"
        f"{room_line}"
        f"💰 <b>ዋጋ (Price):</b> {data['price']} ብር / ETB\n"
        f"{desc_line}"
        f"📞 <b>ስልክ (Phone):</b> {data['phone']}\n\n"
        f"💬 <b>ለበለጠ መረጃ (Contact):</b> {admin_contacts_str}"
    )
    
    buttons = [[InlineKeyboardButton(f"💬 አድሚን ያናግሩ (@{u})", url=f"https://t.me/{u}")] for u in SUPPORT_USERNAMES]
    contact_keyboard = InlineKeyboardMarkup(buttons)

    photos = data.get("photos", [])
    try:
        if len(photos) > 1:
            media_group = [InputMediaPhoto(media=photos[0], caption=caption, parse_mode="HTML")]
            for photo_id in photos[1:]:
                media_group.append(InputMediaPhoto(media=photo_id))
            
            msgs = await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)
            published_msg_id = msgs[0].message_id
            await context.bot.send_message(chat_id=CHANNEL_ID, text="👇 ለበለጠ መረጃ እና ግዢ ያናግሩን:", reply_markup=contact_keyboard)
        else:
            msg = await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photos[0],
                caption=caption,
                parse_mode="HTML",
                reply_markup=contact_keyboard
            )
            published_msg_id = msg.message_id

        save_listing(published_msg_id, data['category'], data['item_type'], data['room'], data['price'], data['phone'], caption)
        await update.message.reply_text("✅ ማስታወቂያው በስኬት ተለጥፎ ዳታቤዝ ውስጥ ገብቷል!\n(Post successfully published & saved!)")
    except Exception as e:
        await update.message.reply_text(f"❌ Post failed.\nError: {e}")

    context.user_data.pop("admin_post", None)
    return ConversationHandler.END


# ---------- Interactive Broadcast Wizard ----------

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return ConversationHandler.END
    await update.message.reply_text(
        "📢 <b>Broadcast Mode Started</b>\n\n"
        "Send your message, photo, or video. The bilingual button menu will be attached automatically.\n\n"
        "<i>(Type /cancel to abort)</i>",
        parse_mode="HTML"
    )
    return BROADCAST_MSG

async def receive_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with get_db() as conn:
        users = conn.execute("SELECT user_id FROM users").fetchall()

    success_count = 0
    fail_count = 0
    
    await update.message.reply_text("⏳ Sending broadcast with buttons, please wait...")

    for user in users:
        try:
            await context.bot.copy_message(
                chat_id=user["user_id"],
                from_chat_id=update.message.chat_id,
                message_id=update.message.message_id,
                reply_markup=get_broadcast_action_keyboard()
            )
            success_count += 1
        except Exception:
            fail_count += 1

    await update.message.reply_text(
        f"📢 <b>Broadcast Finished!</b>\n\n"
        f"✅ Sent to: {success_count}\n"
        f"❌ Failed: {fail_count}",
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("admin_post", None)
    await update.message.reply_text("❌ Action cancelled.")
    return ConversationHandler.END


# ---------- User Handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    context.user_data.clear()

    joined = await is_user_joined(context.bot, user.id)
    if not joined:
        text = "ቦቱን ለመጠቀም እባክዎ አስቀድመው የቴሌግራም ቻናላችንን ይቀላቀሉ!\nPlease join our channel first to use this bot!"
        if update.message: await update.message.reply_text(text, reply_markup=get_force_join_keyboard())
        elif update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=get_force_join_keyboard())
        return

    text = "እባክዎ ቋንቋ ይምረጡ / Please choose your language:"
    if update.message: await update.message.reply_text(text, reply_markup=get_language_keyboard())
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=get_language_keyboard())


async def on_check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    joined = await is_user_joined(context.bot, update.effective_user.id)
    if joined:
        await query.answer("ተረጋግጧል! / Verified!")
        await query.edit_message_text("እባክዎ ቋንቋ ይምረጡ / Please choose your language:", reply_markup=get_language_keyboard())
    else:
        await query.answer("እባክዎ አስቀድመው ቻናሉን ይቀላቀሉ! / Please join the channel first!", show_alert=True)


async def on_language_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("lang:"): context.user_data["lang"] = query.data.split(":", 1)[1]
    lang = context.user_data.get("lang", "am")
    text = "እባክዎ ከታች ካሉት ይምረጡ:\nማስታወቂያ ማውጣት ይፈልጋሉ ወይስ ቤት/ዕቃ መፈለግ?" if lang == "am" else "What would you like to do?"
    await query.edit_message_text(text, reply_markup=get_role_keyboard(lang))


async def on_role_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("role:"): context.user_data["role"] = query.data.split(":", 1)[1]
    role, lang = context.user_data.get("role", "tenant"), context.user_data.get("lang", "am")

    if role == "landlord":
        text = "ቤት ወይም ዕቃ ለማስተዋወቅ እባክዎ አድሚንን ያናግሩ።" if lang == "am" else "To advertise an item or property, please contact the admin."
        await query.edit_message_text(text, reply_markup=get_landlord_keyboard(lang))
    else:
        text = "ምን ዓይነት አገልግሎት ይፈልጋሉ? (እባክዎ ምድብ ይምረጡ)" if lang == "am" else "What are you looking for? (Please choose category)"
        await query.edit_message_text(text, reply_markup=get_category_keyboard(lang))


async def on_category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("cat:"):
        category = query.data.split(":", 1)[1]
        if category.startswith("custom_"):
            cat_row = get_custom_category_by_id(int(category.split("_", 1)[1]))
            if not cat_row:
                lang = context.user_data.get("lang", "am")
                await query.edit_message_text(
                    "❌ ምድቡ አልተገኘም / This category no longer exists.",
                    reply_markup=get_category_keyboard(lang)
                )
                return
            category = cat_row["name"]
        context.user_data["category"] = category
        update_user_search(update.effective_user.id, category=category)

    category = context.user_data.get("category", "Home")
    lang = context.user_data.get("lang", "am")

    if category == "Home":
        text = "የትኛው ክፍለ ከተማ ውስጥ ቤት ይፈልጋሉ?" if lang == "am" else "Which sub-city are you looking in?"
        await query.edit_message_text(text, reply_markup=get_subcity_keyboard(lang))
    elif category == "Phone":
        text = "የትኛውን የስልክ ብራንድ ይፈልጋሉ?" if lang == "am" else "Which phone brand are you looking for?"
        await query.edit_message_text(text, reply_markup=get_phone_brand_keyboard(lang))
    elif category == "Laptop":
        text = "የትኛውን የላፕቶፕ ብራንድ ይፈልጋሉ?" if lang == "am" else "Which laptop brand are you looking for?"
        await query.edit_message_text(text, reply_markup=get_laptop_brand_keyboard(lang))
    elif category == "Car":
        text = "የትኛውን የመኪና ብራንድ ይፈልጋሉ?" if lang == "am" else "Which car brand are you looking for?"
        await query.edit_message_text(text, reply_markup=get_car_brand_keyboard(lang))
    elif category not in BUILTIN_CATEGORIES:
        cat_row = get_custom_category_by_name(category)
        if not cat_row or not get_category_items(cat_row["id"]):
            text = "ይቅርታ፣ በዚህ ምድብ ውስጥ ገና ምንም አልተለጠፈም።" if lang == "am" else "Sorry, nothing has been posted in this category yet."
            back_label = "⬅️ ተመለስ (Back)" if lang == "am" else "⬅️ Back"
            back_markup = InlineKeyboardMarkup([[InlineKeyboardButton(back_label, callback_data="back_to_category")]])
            await query.edit_message_text(text, reply_markup=back_markup)
        else:
            text = "የትኛውን ዓይነት ይፈልጋሉ?" if lang == "am" else "Which type are you looking for?"
            await query.edit_message_text(text, reply_markup=get_custom_item_keyboard(cat_row["id"], lang))
    else:
        text = "የትኛውን የኤሌክትሮኒክስ ዓይነት ይፈልጋሉ?" if lang == "am" else "Which electronic item are you looking for?"
        await query.edit_message_text(text, reply_markup=get_electronics_item_keyboard(lang))


async def show_category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")
    text = "ምን ዓይነት አገልግሎት ይፈልጋሉ? (እባክዎ ምድብ ይምረጡ)" if lang == "am" else "What are you looking for? (Please choose category)"
    await query.edit_message_text(text, reply_markup=get_category_keyboard(lang))


async def on_custom_item_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "am")

    item = get_category_item_by_id(int(query.data.split(":", 1)[1]))
    if not item:
        await query.edit_message_text(
            "❌ ዓይነቱ አልተገኘም / This item type no longer exists.",
            reply_markup=get_category_keyboard(lang)
        )
        return

    context.user_data["item_type"] = item["name"]
    update_user_search(update.effective_user.id, item_type=item["name"])

    category = context.user_data.get("category", "")
    text = "የዋጋ መጠን ይምረጡ:" if lang == "am" else "Select budget range:"
    await query.edit_message_text(text, reply_markup=get_budget_keyboard(category, lang))


async def on_subcity_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("subcity:"):
        subcity = query.data.split(":", 1)[1]
        context.user_data["item_type"] = subcity
        update_user_search(update.effective_user.id, item_type=subcity)

    lang = context.user_data.get("lang", "am")
    text = "የገንዘብ መጠንዎን ይምረጡ:" if lang == "am" else "Select your budget range:"
    await query.edit_message_text(text, reply_markup=get_budget_keyboard("Home", lang))


async def on_phone_brand_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("phone_brand:"):
        brand = query.data.split(":", 1)[1]
        context.user_data["item_type"] = brand
        update_user_search(update.effective_user.id, item_type=brand)

    lang = context.user_data.get("lang", "am")
    text = "የስልክ ዋጋ መጠን ይምረጡ:" if lang == "am" else "Select phone budget range:"
    await query.edit_message_text(text, reply_markup=get_budget_keyboard("Phone", lang))


async def on_laptop_brand_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("laptop_brand:"):
        brand = query.data.split(":", 1)[1]
        context.user_data["item_type"] = brand
        update_user_search(update.effective_user.id, item_type=brand)

    lang = context.user_data.get("lang", "am")
    text = "የላፕቶፕ ዋጋ መጠን ይምረጡ:" if lang == "am" else "Select laptop budget range:"
    await query.edit_message_text(text, reply_markup=get_budget_keyboard("Laptop", lang))


async def on_electronics_item_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("elec_item:"):
        item = query.data.split(":", 1)[1]
        context.user_data["item_type"] = item
        update_user_search(update.effective_user.id, item_type=item)

    lang = context.user_data.get("lang", "am")
    text = "የኤሌክትሮኒክስ ዋጋ መጠን ይምረጡ:" if lang == "am" else "Select electronics budget range:"
    await query.edit_message_text(text, reply_markup=get_budget_keyboard("Electronics", lang))


async def on_car_brand_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("car_brand:"):
        brand = query.data.split(":", 1)[1]
        context.user_data["item_type"] = brand
        update_user_search(update.effective_user.id, item_type=brand)

    lang = context.user_data.get("lang", "am")
    text = "የመኪና ዋጋ መጠን ይምረጡ:" if lang == "am" else "Select car budget range:"
    await query.edit_message_text(text, reply_markup=get_budget_keyboard("Car", lang))


async def on_budget_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("budget:"):
        _, low, high = query.data.split(":")
        context.user_data["budget_low"] = int(low)
        context.user_data["budget_high"] = int(high) if high else None

    category = context.user_data.get("category", "Home")
    lang = context.user_data.get("lang", "am")

    if category == "Home":
        text = "ባለ ስንት ክፍል ነው መከራየት የፈለጉት?" if lang == "am" else "How many rooms are you looking for?"
        await query.edit_message_text(text, reply_markup=get_room_keyboard(lang))
    else:
        await execute_search(query, context)


async def on_room_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    room = query.data.split(":", 1)[1]
    context.user_data["room"] = room
    update_user_search(update.effective_user.id, room=room)
    await execute_search(query, context)


async def execute_search(query, context):
    category = context.user_data.get("category", "Home")
    item_type = context.user_data.get("item_type")
    room = context.user_data.get("room", "ባለ 1")
    budget_low = context.user_data.get("budget_low")
    budget_high = context.user_data.get("budget_high")
    lang = context.user_data.get("lang", "am")

    exact_results, related_results = search_listings(category, item_type, room, budget_low, budget_high)

    if not exact_results and not related_results:
        await query.edit_message_text("ይቅርታ፣ ተዛማጅ ዕቃ/ቤት አልተገኘም። No matching items found yet.", reply_markup=get_result_action_keyboard(lang))
        return

    header_text = f"🎯 <b>ትክክለኛ ፍለጋ ({len(exact_results)})</b>" if lang == "am" else f"🎯 <b>Exact Matches ({len(exact_results)})</b>"
    await query.edit_message_text(header_text, parse_mode="HTML")

    for r in exact_results[:5]:
        try: await context.bot.forward_message(chat_id=query.message.chat_id, from_chat_id=CHANNEL_ID or query.message.chat_id, message_id=r["message_id"])
        except Exception: await context.bot.send_message(chat_id=query.message.chat_id, text=r["raw_text"])

    if related_results:
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"\n💡 <b>ተዛማጅ ፍለጋዎች / Related Searches ({len(related_results[:3])}):</b>", parse_mode="HTML")
        for r in related_results[:3]:
            try: await context.bot.forward_message(chat_id=query.message.chat_id, from_chat_id=CHANNEL_ID or query.message.chat_id, message_id=r["message_id"])
            except Exception: await context.bot.send_message(chat_id=query.message.chat_id, text=r["raw_text"])

    admin_contacts_str = " | ".join([f"@{u}" for u in SUPPORT_USERNAMES])
    comp_text = f"ለበለጠ መረጃ ያናግሩ: {admin_contacts_str}\nወደ ዋናው ማውጫ ለመመለስ ይጫኑ:" if lang == "am" else f"Contact: {admin_contacts_str}\nTap below to go back:"
    await context.bot.send_message(chat_id=query.message.chat_id, text=comp_text, reply_markup=get_result_action_keyboard(lang))


# ---------- Admin /stats & /delete ----------

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return

    with get_db() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_listings = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        
        recent_users = conn.execute(
            "SELECT username, first_name, last_category, last_item_type, last_room FROM users ORDER BY joined_at DESC LIMIT 30"
        ).fetchall()

    text_lines = [
        f"📊 <b>Bot Statistics</b>",
        f"🏠 <b>Total Active Listings:</b> {total_listings}",
        f"👥 <b>Total Registered Users:</b> {total_users}\n",
        f"<b>📋 Recent User Searches:</b>"
    ]

    for u in recent_users:
        name = u["username"]
        display_name = f"@{name}" if name else (u["first_name"] or "Unknown User")
        cat = u["last_category"] or "Home"
        item = u["last_item_type"] or "N/A"
        rm = f" | 🚪 {u['last_room']}" if cat == "Home" and u['last_room'] else ""
        
        text_lines.append(f"👤 {display_name} | 📦 {cat} ({item}{rm})")

    final_text = "\n".join(text_lines)
    await update.message.reply_text(final_text[:4000], parse_mode="HTML")


async def admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: `/delete <message_id>`")
        return
    msg_id = int(context.args[0])
    removed = delete_listing(msg_id)
    if removed: await update.message.reply_text(f"✅ Listing <b>{msg_id}</b> successfully removed from database.", parse_mode="HTML")
    else: await update.message.reply_text(f"❌ Listing <b>{msg_id}</b> not found in database.", parse_mode="HTML")


# ---------- Admin: manage custom categories ----------

async def admin_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    cats = get_custom_categories()
    if not cats:
        await update.message.reply_text(
            "No custom categories yet.\nCreate one with /post -> ➕ Add New Category."
        )
        return

    lines = ["🗂 <b>Custom Categories</b>\n"]
    with get_db() as conn:
        for c in cats:
            n_items = len(get_category_items(c["id"]))
            n_listings = conn.execute(
                "SELECT COUNT(*) FROM listings WHERE category = ?", (c["name"],)
            ).fetchone()[0]
            lines.append(f"<b>{c['id']}.</b> {html.escape(c['name'], quote=False)} - {n_items} types, {n_listings} listings")
    lines.append("\nDelete a category: <code>/delcategory &lt;id&gt;</code>")
    await update.message.reply_text("\n".join(lines)[:4000], parse_mode="HTML")


async def admin_delcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /delcategory <id>   (see ids with /categories)")
        return
    cat_id = int(context.args[0])
    cat_row = get_custom_category_by_id(cat_id)
    if not cat_row:
        await update.message.reply_text("❌ Category not found.")
        return
    delete_custom_category(cat_id)
    await update.message.reply_text(
        f"✅ Category <b>{html.escape(cat_row['name'], quote=False)}</b> removed from the menus.\n"
        "Its old listings stay in the database; they show up again if you re-create a category with the same name.",
        parse_mode="HTML"
    )


# ---------- Main Execution ----------

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    post_handler = ConversationHandler(
        entry_points=[CommandHandler("post", start_post_wizard)],
        states={
            POST_PHOTO: [
                MessageHandler(filters.PHOTO, process_post_photo),
                CallbackQueryHandler(process_post_photo, pattern=r"^done_photos$")
            ],
            POST_CATEGORY: [CallbackQueryHandler(process_post_category, pattern=r"^post_cat:")],
            POST_ITEM_TYPE: [CallbackQueryHandler(process_post_item_type, pattern=r"^post_item:")],
            POST_CUSTOM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_custom_name)],
            POST_ROOM: [CallbackQueryHandler(process_post_room, pattern=r"^post_room:")],
            POST_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_post_price)],
            POST_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_post_description)],
            POST_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_post_phone)],
            POST_NEW_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_category)],
        },
        fallbacks=[CommandHandler("cancel", cancel_wizard)],
    )
    
    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("broadcast", start_broadcast)],
        states={
            BROADCAST_MSG: [MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, receive_broadcast)],
        },
        fallbacks=[CommandHandler("cancel", cancel_wizard)],
    )

    app.add_handler(post_handler)
    app.add_handler(broadcast_handler)

    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, on_channel_post))
    app.add_handler(MessageHandler(filters.FORWARDED & filters.TEXT & filters.ChatType.PRIVATE, handle_forwarded_import))
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("status", admin_stats))
    app.add_handler(CommandHandler("delete", admin_delete))
    app.add_handler(CommandHandler("categories", admin_categories))
    app.add_handler(CommandHandler("delcategory", admin_delcategory))

    app.add_handler(CallbackQueryHandler(start, pattern=r"^restart_search$"))
    app.add_handler(CallbackQueryHandler(start, pattern=r"^back_to_lang$"))
    app.add_handler(CallbackQueryHandler(on_role_chosen, pattern=r"^back_to_role$"))
    app.add_handler(CallbackQueryHandler(show_category_menu, pattern=r"^back_to_category$"))
    app.add_handler(CallbackQueryHandler(on_category_chosen, pattern=r"^back_to_custom_item$"))
    app.add_handler(CallbackQueryHandler(on_subcity_chosen, pattern=r"^back_to_subcity$"))
    app.add_handler(CallbackQueryHandler(on_phone_brand_chosen, pattern=r"^back_to_phone_brand$"))
    app.add_handler(CallbackQueryHandler(on_laptop_brand_chosen, pattern=r"^back_to_laptop_brand$"))
    app.add_handler(CallbackQueryHandler(on_electronics_item_chosen, pattern=r"^back_to_elec_item$"))
    app.add_handler(CallbackQueryHandler(on_car_brand_chosen, pattern=r"^back_to_car_brand$"))

    app.add_handler(CallbackQueryHandler(on_check_join, pattern=r"^check_join$"))
    app.add_handler(CallbackQueryHandler(on_language_chosen, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(on_role_chosen, pattern=r"^role:"))
    app.add_handler(CallbackQueryHandler(on_category_chosen, pattern=r"^cat:"))
    app.add_handler(CallbackQueryHandler(on_subcity_chosen, pattern=r"^subcity:"))
    app.add_handler(CallbackQueryHandler(on_phone_brand_chosen, pattern=r"^phone_brand:"))
    app.add_handler(CallbackQueryHandler(on_laptop_brand_chosen, pattern=r"^laptop_brand:"))
    app.add_handler(CallbackQueryHandler(on_electronics_item_chosen, pattern=r"^elec_item:"))
    app.add_handler(CallbackQueryHandler(on_car_brand_chosen, pattern=r"^car_brand:"))
    app.add_handler(CallbackQueryHandler(on_custom_item_chosen, pattern=r"^citem:"))
    app.add_handler(CallbackQueryHandler(on_budget_chosen, pattern=r"^budget:"))
    app.add_handler(CallbackQueryHandler(on_room_chosen, pattern=r"^room:"))

    logger.info("Bot starting with multi-photo, description and custom category support...")
    app.run_polling()

if __name__ == "__main__":
    main()
