"""
Hawassa Rental & Marketplace Telegram Bot â€” Fully Integrated Production Code (Railway Persistent Edition)
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
    "tabor": "Tabor", "á‰³á‰¦áˆ­": "Tabor",
    "hawela": "Hawela-Tula", "á‰±áˆ‹": "Hawela-Tula", "áˆá‹‹áˆ‹": "Hawela-Tula",
    "addis ketema": "Addis Ketema", "áŠ á‹²áˆµ áŠ¨á‰°áˆ›": "Addis Ketema",
    "hayek dare": "Hayek Dare", "áŠƒá‹­á‰… á‹³áˆ­": "Hayek Dare", "áˆ€á‹­á‰… á‹³áˆ­": "Hayek Dare",
    "menehariya": "Menehariya", "áˆ˜áŠáˆ€áˆªá‹«": "Menehariya", "áˆ˜áŠáˆƒáˆªá‹«": "Menehariya",
    "misrak": "Misrak", "áˆáˆµáˆ«á‰…": "Misrak",
    "bahile adarash": "Bahile Adarash", "á‰£áˆ…áˆˆ áŠ á‹³áˆ«áˆ½": "Bahile Adarash", "á‰£áˆ…áˆ áŠ á‹³áˆ«áˆ½": "Bahile Adarash",
    "mehal ketema": "Mehal Ketema", "áˆ›á‹•áŠ¨áˆ áŠ¨á‰°áˆ›": "Mehal Ketema", "áˆ˜áˆ€áˆ áŠ¨á‰°áˆ›": "Mehal Ketema"
}

PHONE_BUDGETS = [
    ("5000 - 10000 á‰¥áˆ­ / ETB", 5000, 10000),
    ("10000 - 20000 á‰¥áˆ­ / ETB", 10000, 20000),
    ("20000 - 30000 á‰¥áˆ­ / ETB", 20000, 30000),
    ("30000 - 50000 á‰¥áˆ­ / ETB", 30000, 50000),
    ("50000 - 100000 á‰¥áˆ­ / ETB", 50000, 100000),
    ("100000+ á‰¥áˆ­ / ETB", 100000, None),
]

LAPTOP_BUDGETS = [
    ("10000 - 20000 á‰¥áˆ­ / ETB", 10000, 20000),
    ("20000 - 30000 á‰¥áˆ­ / ETB", 20000, 30000),
    ("30000 - 50000 á‰¥áˆ­ / ETB", 30000, 50000),
    ("50000 - 100000 á‰¥áˆ­ / ETB", 50000, 100000),
    ("100000+ á‰¥áˆ­ / ETB", 100000, None),
]

ELECTRONIC_BUDGETS = [
    ("1000 - 3000 á‰¥áˆ­ / ETB", 1000, 3000),
    ("3000 - 7000 á‰¥áˆ­ / ETB", 3000, 7000),
    ("7000 - 15000 á‰¥áˆ­ / ETB", 7000, 15000),
    ("15000 - 30000 á‰¥áˆ­ / ETB", 15000, 30000),
    ("30000+ á‰¥áˆ­ / ETB", 30000, None),
]

CAR_BUDGETS = [
    ("500,000 - 1,000,000 á‰¥áˆ­ / ETB", 500000, 1000000),
    ("1,000,000 - 2,500,000 á‰¥áˆ­ / ETB", 1000000, 2500000),
    ("2,500,000 - 5,000,000 á‰¥áˆ­ / ETB", 2500000, 5000000),
    ("5,000,000+ á‰¥áˆ­ / ETB", 5000000, None),
]

HOME_BUDGETS = [
    ("2000 - 5000 á‰¥áˆ­ / ETB", 2000, 5000),
    ("5000 - 10000 á‰¥áˆ­ / ETB", 5000, 10000),
    ("10000 - 15000 á‰¥áˆ­ / ETB", 10000, 15000),
    ("15000+ á‰¥áˆ­ / ETB", 15000, None),
]

ROOM_TYPES = ["á‰£áˆˆ 1", "á‰£áˆˆ 2", "á‰£áˆˆ 3", "á‰£áˆˆ 4", "áˆ™áˆ‰ áŒá‰¢"]
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
    ("áˆáˆ‰áˆ á‹‹áŒ‹ / Any price", 0, None),
    ("áŠ¥áˆµáŠ¨ 500 á‰¥áˆ­ / Up to 500 ETB", 0, 500),
    ("500 - 2000 á‰¥áˆ­ / ETB", 500, 2000),
    ("2000 - 10000 á‰¥áˆ­ / ETB", 2000, 10000),
    ("10000 - 50000 á‰¥áˆ­ / ETB", 10000, 50000),
    ("50000+ á‰¥áˆ­ / ETB", 50000, None),
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
        return "âŒ áˆµáˆ™ áŠ¨2 áŠ¥áˆµáŠ¨ 40 áŠá‹°áˆ áˆ˜áˆ†áŠ• áŠ áˆˆá‰ á‰µ / Name must be 2-40 characters. Try again:"
    if name.lower() in {c.lower() for c in BUILTIN_CATEGORIES}:
        return "âŒ á‹­áˆ… áˆá‹µá‰¥ áŠ áˆµá‰€á‹µáˆž áŠ áˆˆ / This is already a built-in category. Type a different name:"
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
    """'ðŸ” Food / áˆáŒá‰¥' -> {'food', 'áˆáŒá‰¥', 'ðŸ” food / áˆáŒá‰¥' (cleaned)}"""
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
    elif any(k in text_lower for k in ["gimbal", "áŒ‚áˆá‰£áˆ"]):
        category = "Electronics"
        item_type = "Gimbal"
    elif any(k in text_lower for k in ["ring light", "light", "áˆ˜á‰¥áˆ«á‰µ"]):
        category = "Electronics"
        item_type = "Ring light / Light"
    elif any(k in text_lower for k in ["mic", "microphone", "áˆ›á‹­áŠ­"]):
        category = "Electronics"
        item_type = "Mic / Microphone"
    elif any(k in text_lower for k in ["camera", "áŠ«áˆœáˆ«"]):
        category = "Electronics"
        item_type = "Camera / Video"
    elif any(k in text_lower for k in ["iphone", "samsung", "tecno", "infinix", "xiaomi", "áˆµáˆáŠ­", "phone"]):
        category = "Phone"
        item_type = "Other Phone"
        for brand in PHONE_BRANDS:
            if brand.lower().split("/")[0].strip() in text_lower:
                item_type = brand
                break
    elif any(k in text_lower for k in ["hp", "dell", "lenovo", "macbook", "asus", "laptop", "core i", "áˆ‹á•á‰¶á•"]):
        category = "Laptop"
        item_type = "Other Laptop"
        for brand in LAPTOP_BRANDS:
            if brand.lower().split("/")[0].strip() in text_lower:
                item_type = brand
                break
    elif any(k in text_lower for k in ["toyota", "hyundai", "suzuki", "nissan", "áˆ˜áŠªáŠ“", "car", "vitz", "yaris"]):
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

    room = "á‰£áˆˆ 1"
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
    return InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ“¢ á‰»áŠ“áˆ‰áŠ• á‹­á‰€áˆ‹á‰€áˆ‰ (Join Channel)", url=CHANNEL_LINK)],[InlineKeyboardButton("âœ… áŠ áˆ¨áŒ‹áŒáŒ¥ (Verify Join)", callback_data="check_join")]])

def get_language_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("áŠ áˆ›áˆ­áŠ› ðŸ‡ªðŸ‡¹", callback_data="lang:am"), InlineKeyboardButton("English ðŸ‡¬ðŸ‡§", callback_data="lang:en")]])

def get_role_keyboard(lang="am"):
    if lang == "am":
        buttons = [
            [InlineKeyboardButton("ðŸ  áˆ›áˆµá‰³á‹ˆá‰‚á‹« áˆ›á‹áŒ£á‰µ (Post / Advertise)", callback_data="role:landlord")],
            [InlineKeyboardButton("ðŸ” á‰¤á‰µ á‹ˆá‹­áˆ á‹•á‰ƒ áˆ˜áˆáˆˆáŒ (Search)", callback_data="role:tenant")],
            [InlineKeyboardButton("ðŸŒ á‰‹áŠ•á‰‹ á‰€á‹­áˆ­ (Change Language)", callback_data="back_to_lang")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("ðŸ  Post / Advertise Property", callback_data="role:landlord")],
            [InlineKeyboardButton("ðŸ” Search / Find Property", callback_data="role:tenant")],
            [InlineKeyboardButton("ðŸŒ Change Language", callback_data="back_to_lang")]
        ]
    return InlineKeyboardMarkup(buttons)

def get_category_keyboard(lang="am"):
    if lang == "am":
        buttons = [
            [InlineKeyboardButton("ðŸ  á‰¤á‰µ (Home / Residential)", callback_data="cat:Home")],
            [InlineKeyboardButton("ðŸ“± áˆµáˆáŠ­ (Phones)", callback_data="cat:Phone")],
            [InlineKeyboardButton("ðŸ’» áˆ‹á•á‰¶á• (Laptops)", callback_data="cat:Laptop")],
            [InlineKeyboardButton("ðŸ“· áŠ¤áˆŒáŠ­á‰µáˆ®áŠ’áŠ­áˆµ (Electronics)", callback_data="cat:Electronics")],
            [InlineKeyboardButton("ðŸš— áˆ˜áŠªáŠ“ (Car / Vehicle)", callback_data="cat:Car")],
            [InlineKeyboardButton("â¬…ï¸ á‰°áˆ˜áˆˆáˆµ (Back)", callback_data="back_to_role")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("ðŸ  Home (Residential)", callback_data="cat:Home")],
            [InlineKeyboardButton("ðŸ“± Phone", callback_data="cat:Phone")],
            [InlineKeyboardButton("ðŸ’» Laptop", callback_data="cat:Laptop")],
            [InlineKeyboardButton("ðŸ“· Electronics", callback_data="cat:Electronics")],
            [InlineKeyboardButton("ðŸš— Car / Vehicle", callback_data="cat:Car")],
            [InlineKeyboardButton("â¬…ï¸ Back", callback_data="back_to_role")]
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
    back_label = "â¬…ï¸ á‰°áˆ˜áˆˆáˆµ (Back)" if lang == "am" else "â¬…ï¸ Back"
    buttons.append([InlineKeyboardButton(back_label, callback_data="back_to_category")])
    return InlineKeyboardMarkup(buttons)

def get_landlord_keyboard(lang="am"):
    buttons = []
    for u in SUPPORT_USERNAMES:
        label = f"ðŸ’¬ áŠ á‹µáˆšáŠ• á‹«áŠ“áŒáˆ© (@{u})" if lang == "am" else f"ðŸ’¬ Contact Admin (@{u})"
        buttons.append([InlineKeyboardButton(label, url=f"https://t.me/{u}")])
    main_menu_label = "ðŸ  á‹ˆá‹° á‹‹áŠ“á‹ áˆ›á‹áŒ« á‹­áˆ˜áˆˆáˆ±" if lang == "am" else "ðŸ  Main Menu"
    buttons.append([InlineKeyboardButton(main_menu_label, callback_data="restart_search")])
    return InlineKeyboardMarkup(buttons)

def get_subcity_keyboard(lang="am"):
    buttons = [[InlineKeyboardButton(sc, callback_data=f"subcity:{sc}")] for sc in SUBCITIES]
    back_label = "â¬…ï¸ á‰°áˆ˜áˆˆáˆµ (Back)" if lang == "am" else "â¬…ï¸ Back"
    buttons.append([InlineKeyboardButton(back_label, callback_data
