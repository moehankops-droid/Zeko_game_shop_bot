import asyncio
import sqlite3
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ================= ဆက်တင်များ ပြင်ဆင်ရန် =================
TOKEN = "YOUR_BOT_TOKEN_HERE"  # BotFather မှရသော Token ထည့်ပါ
SUPER_ADMIN_ID = 123456789     # သင့်ရဲ့ Telegram User ID (ဂဏန်းသီးသန့်) ထည့်ပါ
PAYMENT_INFO = "KPay / Wave: 09123456789 (Zeko)" # ငွေလွှဲလက်ခံမည့် ဖုန်းနံပါတ်
# ========================================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= DATABASE ချိတ်ဆက်ခြင်း =================
conn = sqlite3.connect("zeko_shop.db")
cursor = conn.cursor()

# Tables များ တည်ဆောက်ခြင်း
cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    price INTEGER
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    package_name TEXT,
    price INTEGER,
    game_id TEXT,
    photo_id TEXT,
    status TEXT,
    created_at TEXT
)
""")

# Super Admin အား အလိုအလျောက် ထည့်သွင်းခြင်း
cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (SUPER_ADMIN_ID,))

# မူလ Diamond ဈေးနှုန်းများ (Database တွင် မရှိသေးမှသာ ထည့်မည်)
cursor.execute("SELECT COUNT(*) FROM packages")
if cursor.fetchone()[0] == 0:
    default_packages = [
        ("Weekly Pass", 7000),
        ("Twilight Pass", 37000),
        ("11 Diamond", 1500),
        ("86 Diamond", 5700),
        ("172 Diamond", 11200),
        ("257 Diamond", 16300)
    ]
    cursor.executemany("INSERT INTO packages (name, price) VALUES (?, ?)", default_packages)
conn.commit()

# ================= FSM STATES (အဆင့်ဆင့် မေးမြန်းရန်) =================
class OrderState(StatesGroup):
    waiting_for_game_id = State()
    waiting_for_screenshot = State()

class AdminState(StatesGroup):
    waiting_for_new_admin = State()
    waiting_for_new_price = State()

# Admin ဟုတ်/မဟုတ် စစ်ဆေးသည့် Function
def is_admin(user_id: int) -> bool:
    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None

# ================= CUSTOMER ဘက်ခြမ်း =================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Diamond ဈေးနှုန်းကြည့်ရန်", callback_data="view_prices")
    builder.button(text="🛒 Diamond Package ဝယ်ရန်", callback_data="buy_diamond")
    builder.button(text="📦 Order အခြေအနေကြည့်ရန်", callback_data="my_orders")
    builder.button(text="📞 ဆက်သွယ်ရန်", url="https://t.me/Zeko29")
    
    if is_admin(message.from_user.id):
        builder.button(text="⚙️ Admin Panel သို့ဝင်ရန်", callback_data="admin_panel")
        
    builder.adjust(1)
    await message.answer(
        "💎 **မင်္ဂလာပါ Zeko Game Shop မှ ကြိုဆိုပါတယ်ခင်ဗျာ!** ✨\n\n"
        "MLBB Diamond နှင့် Pass များကို ၂၄ နာရီ စိတ်ချယုံကြည်စွာ ဝယ်ယူနိုင်ပါပြီ။\n"
        "အောက်ပါခလုတ်များမှတစ်ဆင့် ရွေးချယ်အသုံးပြုပါ 👇",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

# ၁။ ဈေးနှုန်းကြည့်ရန်
@dp.callback_query(F.data == "view_prices")
async def view_prices(callback: types.CallbackQuery):
    cursor.execute("SELECT name, price FROM packages")
    rows = cursor.fetchall()
    
    text = "📋 **လက်ရှိ Diamond ဈေးနှုန်းစာရင်းများ:**\n\n"
    for name, price in rows:
        text += f"▫️ **{name}**: {price:,} ကျပ်\n"
        
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 ဝယ်ယူမည်", callback_data="buy_diamond")
    builder.button(text="🔙 ပင်မမီနူးသို့", callback_data="back_home")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# ၂။ ဝယ်ယူရန် Package ရွေးခြင်း
@dp.callback_query(F.data == "buy_diamond")
async def buy_diamond(callback: types.CallbackQuery):
    cursor.execute("SELECT id, name, price FROM packages")
    rows = cursor.fetchall()
    
    builder = InlineKeyboardBuilder()
    for pkg_id, name, price in rows:
        builder.button(text=f"{name} - {price:,} Ks", callback_data=f"select_pkg_{pkg_id}")
    builder.button(text="🔙 ပင်မမီနူးသို့", callback_data="back_home")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "🛒 **ဝယ်ယူလိုသော Package ကို ရွေးချယ်ပါ:**",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

# ၃။ Player ID / Server ID တောင်းခြင်း
@dp.callback_query(F.data.startswith("select_pkg_"))
async def select_package(callback: types.CallbackQuery, state: FSMContext):
    pkg_id = int(callback.data.split("_")[2])
    cursor.execute("SELECT name, price FROM packages WHERE id = ?", (pkg_id,))
    pkg = cursor.fetchone()
    
    if not pkg:
        await callback.answer("Package မတွေ့ပါ!", show_alert=True)
        return
        
    await state.update_data(package_name=pkg[0], price=pkg[1])
    await state.set_state(OrderState.waiting_for_game_id)
    
    await callback.message.edit_text(
        f"✅ ရွေးချယ်ထားသည်: **{pkg[0]} ({pkg[1]:,} ကျပ်)**\n\n"
        "🎮 မိမိ၏ **Player ID နှင့် Server ID** ကို ပို့ပေးပါ။\n"
        "*(ဥပမာ - 123456789 (1234))*\n\n"
        "ပယ်ဖျက်လိုပါက /start ကိုနှိပ်ပါ။",
        parse_mode="Markdown"
    )

# ၄။ ငွေပေးချေမှုအထောက်အထား တောင်းခြင်း
@dp.message(OrderState.waiting_for_game_id)
async def receive_game_id(message: types.Message, state: FSMContext):
    game_id = message.text.strip()
    await state.update_data(game_id=game_id)
    data = await state.get_data()
    
    await state.set_state(OrderState.waiting_for_screenshot)
    await message.answer(
        f"🎮 **Game ID:** `{game_id}`\n"
        f"💰 **ကျသင့်ငွေ:** {data['price']:,} ကျပ်\n\n"
        f"💳 **ငွေလွှဲရန်အကောင့်:**\n`{PAYMENT_INFO}`\n\n"
        "📸 အထက်ပါအကောင့်သို့ ငွေလွှဲပြီးပါက **ငွေလွှဲပြေစာ (Screenshot)** ပုံကို ပို့ပေးပါခင်ဗျာ။",
        parse_mode="Markdown"
    )

# ၅။ Screenshot လက်ခံပြီး Admin များထံ ပို့ခြင်း
@dp.message(OrderState.waiting_for_screenshot, F.photo)
async def receive_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Database ထဲသို့ Order သိမ်းခြင်း
    cursor.execute("""
        INSERT INTO orders (user_id, username, package_name, price, game_id, photo_id, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, data['package_name'], data['price'], data['game_id'], photo_id, "Pending (စောင့်ဆိုင်းဆဲ)", now))
    order_id = cursor.lastrowid
    conn.commit()
    await state.clear()
    
    # Customer ထံ ပြန်ကြားခြင်း
    await message.answer(
        f"✅ **အော်ဒါတင်ခြင်း အောင်မြင်ပါသည်!**\n\n"
        f"🆔 Order ID: `#{order_id}`\n"
        f"💎 Package: {data['package_name']}\n"
        f"🎮 Game ID: `{data['game_id']}`\n"
        f"⏳ အခြေအနေ: Admin မှ စစ်ဆေးနေပါသည်...",
        parse_mode="Markdown"
    )
    
    # Admin အားလုံးထံ အော်ဒါပို့ပေးခြင်း
    cursor.execute("SELECT user_id FROM admins")
    admins = cursor.fetchall()
    
    admin_kb = InlineKeyboardBuilder()
    admin_kb.button(text="✅ ငွေလက်ခံအတည်ပြုမည်", callback_data=f"ord_approve_{order_id}")
    admin_kb.button(text="💎 Diamond ဖြည့်ပြီးကြောင်း အတည်ပြုမည်", callback_data=f"ord_done_{order_id}")
    admin_kb.button(text="❌ ပယ်ဖျက်မည် (Cancel)", callback_data=f"ord_cancel_{order_id}")
    admin_kb.adjust(1)
    
    admin_msg = (
        f"🚨 **အော်ဒါအသစ် ရောက်ရှိပါသည်! (#{order_id})**\n\n"
        f"👤 ဝယ်သူ: {username} (`{user_id}`)\n"
        f"💎 ပက်ကေ့ဂျ်: **{data['package_name']}** ({data['price']:,} Ks)\n"
        f"🎮 Game ID: `{data['game_id']}`\n"
        f"🕒 အချိန်: {now}"
    )
    
    for (admin_id,) in admins:
        try:
            await bot.send_photo(chat_id=admin_id, photo=photo_id, caption=admin_msg, reply_markup=admin_kb.as_markup(), parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Admin {admin_id} ထံ ပို့မရပါ: {e}")

# ၆။ Customer မိမိ Order အခြေအနေကြည့်ရန်
@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT order_id, package_name, game_id, status FROM orders WHERE user_id = ? ORDER BY order_id DESC LIMIT 5", (user_id,))
    rows = cursor.fetchall()
    
    if not rows:
        text = "📦 သင့်တွင် မှာယူထားသော အော်ဒါမှတ်တမ်း မရှိသေးပါ။"
    else:
        text = "📦 **သင်၏ နောက်ဆုံး အော်ဒါ (၅) ခု အခြေအနေ:**\n\n"
        for oid, pkg, gid, status in rows:
            text += f"🆔 `#{oid}` | {pkg} (`{gid}`)\n➡️ အခြေအနေ: **{status}**\n\n"
            
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 ပင်မမီနူးသို့", callback_data="back_home")
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "back_home")
async def back_home(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await cmd_start(callback.message, state)

# ================= ADMIN ဘက်ခြမ်း =================
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
        
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Admin အသစ်ထည့်ရန်", callback_data="add_admin")
    builder.button(text="💲 ဈေးနှုန်းပြင်ဆင်ရန်", callback_data="edit_prices")
    builder.button(text="📊 အရောင်းစာရင်းကြည့်ရန်", callback_data="sales_report")
    builder.button(text="🔙 ပင်မမီနူးသို့", callback_data="back_home")
    builder.adjust(1)
    
    await callback.message.edit_text("⚙️ **Admin ထိန်းချုပ်ခန်း (Admin Panel)**", reply_markup=builder.as_markup(), parse_mode="Markdown")

# Admin အများကြီး ထည့်နိုင်ရန်
@dp.callback_query(F.data == "add_admin")
async def add_admin_start(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    await state.set_state(AdminState.waiting_for_new_admin)
    await callback.message.edit_text("➕ Admin အဖြစ် ထည့်သွင်းလိုသူ၏ **Telegram User ID (ဂဏန်း)** ကို ပို့ပေးပါ။\n*(User ID မသိပါက @userinfobot တွင် စစ်ခိုင်းပါ)*", parse_mode="Markdown")

@dp.message(AdminState.waiting_for_new_admin)
async def add_admin_save(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ဂဏန်းသီးသန့်သာ ရိုက်ထည့်ပါ။")
        return
    new_admin_id = int(message.text)
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_admin_id,))
    conn.commit()
    await state.clear()
    await message.answer(f"✅ User ID `{new_admin_id}` ကို Admin အဖြစ် ထည့်သွင်းပြီးပါပြီ။ /start ကိုပြန်နှိပ်ပါ။", parse_mode="Markdown")

# Admin ဈေးပြင်နိုင်ရန်
@dp.callback_query(F.data == "edit_prices")
async def edit_prices_list(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cursor.execute("SELECT id, name, price FROM packages")
    rows = cursor.fetchall()
    
    builder = InlineKeyboardBuilder()
    for pkg_id, name, price in rows:
        builder.button(text=f"✏️ {name} ({price:,} Ks)", callback_data=f"edit_pkg_{pkg_id}")
    builder.button(text="🔙 Admin Panel သို့", callback_data="admin_panel")
    builder.adjust(1)
    await callback.message.edit_text("💲 **ဈေးနှုန်းပြင်ဆင်လိုသော Package ကို ရွေးပါ:**", reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("edit_pkg_"))
async def edit_pkg_prompt(callback: types.CallbackQuery, state: FSMContext):
    pkg_id = int(callback.data.split("_")[2])
    await state.update_data(edit_pkg_id=pkg_id)
    await state.set_state(AdminState.waiting_for_new_price)
    await callback.message.edit_text("💵 ပြောင်းလဲလိုသော **ဈေးနှုန်းအသစ် (ဂဏန်းသီးသန့်)** ကို ရိုက်ထည့်ပါ။ (ဥပမာ: `7200`)", parse_mode="Markdown")

@dp.message(AdminState.waiting_for_new_price)
async def edit_pkg_save(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ဂဏန်းသီးသန့်သာ ရိုက်ထည့်ပါ။")
        return
    new_price = int(message.text)
    data = await state.get_data()
    cursor.execute("UPDATE packages SET price = ? WHERE id = ?", (new_price, data['edit_pkg_id']))
    conn.commit()
    await state.clear()
    await message.answer(f"✅ ဈေးနှုန်းကို **{new_price:,} ကျပ်** သို့ ပြောင်းလဲပြီးပါပြီ။ /start ကိုပြန်နှိပ်ပါ။", parse_mode="Markdown")

# အရောင်းစာရင်းကြည့်ရန်
@dp.callback_query(F.data == "sales_report")
async def sales_report(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    cursor.execute("SELECT COUNT(*), SUM(price) FROM orders WHERE status = 'Completed (Diamond ဖြည့်ပြီး)'")
    total_count, total_sales = cursor.fetchone()
    total_sales = total_sales or 0
    
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status LIKE 'Pending%'")
    pending_count = cursor.fetchone()[0]
    
    text = (
        "📊 **Zeko Game Shop အရောင်းစာရင်းချုပ်**\n\n"
        f"✅ ဖြည့်ပြီးစီးသော အော်ဒါစုစုပေါင်း: **{total_count} ခု**\n"
        f"💰 စုစုပေါင်း ရောင်းရငွေ: **{total_sales:,} ကျပ်**\n"
        f"⏳ စောင့်ဆိုင်းဆဲ အော်ဒါ: **{pending_count} ခု**"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Admin Panel သို့", callback_data="admin_panel")
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# Order အတည်ပြု / Diamond ဖြည့်ပြီး / ပယ်ဖျက်ခြင်း
@dp.callback_query(F.data.startswith("ord_"))
async def handle_order_action(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    action = parts[1]
    order_id = int(parts[2])
    
    cursor.execute("SELECT user_id, package_name, game_id FROM orders WHERE order_id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        await callback.answer("Order မတွေ့ပါ!", show_alert=True)
        return
        
    cust_id, pkg_name, game_id = order
    
    if action == "approve":
        new_status = "Approved (ငွေလက်ခံပြီး - ဖြည့်နေဆဲ)"
        cust_msg = f"👍 သင်၏ Order `#{order_id}` ({pkg_name}) အတွက် ငွေလွှဲအတည်ပြုပြီးပါပြီ။ Diamond ဖြည့်ပေးနေပါပြီ ခင်ဗျာ။"
    elif action == "done":
        new_status = "Completed (Diamond ဖြည့်ပြီး)"
        cust_msg = f"🎉 **ဂုဏ်ယူပါတယ်!** သင်၏ Order `#{order_id}` ({pkg_name}) ကို Game ID `{game_id}` ထဲသို့ Diamond ဖြည့်သွင်းပြီးပါပြီ။ ဝယ်ယူအားပေးမှုကို ကျေးဇူးတင်ပါတယ်!"
    elif action == "cancel":
        new_status = "Cancelled (ပယ်ဖျက်လိုက်သည်)"
        cust_msg = f"❌ တောင်းပန်ပါတယ်ခင်ဗျာ။ သင်၏ Order `#{order_id}` ({pkg_name}) ကို ပယ်ဖျက်လိုက်ပါသည်။ အသေးစိတ်သိလိုပါက @Zeko29 သို့ ဆက်သွယ်ပါ။"
        
    cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
    conn.commit()
    
    # Customer ထံ အကြောင်းကြားစာပို့ခြင်း
    try:
        await bot.send_message(chat_id=cust_id, text=cust_msg, parse_mode="Markdown")
    except Exception:
        pass
        
    # Admin ၏ Message တွင် အခြေအနေ ပြောင်းပြခြင်း
    await callback.message.edit_caption(
        caption=f"{callback.message.caption}\n\n📌 **လက်ရှိအခြေအနေ:** {new_status}",
        reply_markup=callback.message.reply_markup if action == "approve" else None,
        parse_mode="Markdown"
    )
    await callback.answer("လုပ်ဆောင်ပြီးပါပြီ!")

async def main():
    print("Zeko Game Shop Bot စတင်အလုပ်လုပ်နေပါပြီ...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
  
