# main.py
import asyncio
import logging
import io
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

import database as db

# --- SOZLAMALAR ---
BOT_TOKEN = "BOT_TOKEN_SHU_YERGA_YOZING"
ADMIN_ID = 123456789  # O'zingizning Telegram ID raqamingizni yozing

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
router = Router()

# --- FSM HOLATLAR ---
class AddService(StatesGroup):
    car_model = State()
    modifications = State()
    price = State()
    coworkers = State()
    vin_code = State()

# --- KEYBOARDS ---
def main_menu():
    kb = [
        [KeyboardButton(text="🚗 Yangi avtomobil qo'shish")],
        [KeyboardButton(text="📊 Mening natijalarim")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def cancel_keyboard():
    kb = [[KeyboardButton(text="⬅️ Orqaga"), KeyboardButton(text="❌ Bekor qilish")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- XODIMLAR UCHUN START VA RO'YXATDAN O'TISH ---
@router.message(CommandStart())
async def start_cmd(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.add_user(message.from_user.id, message.from_user.full_name)
        
        # Adminga xabar yuborish
        ikb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{message.from_user.id}"),
             InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{message.from_user.id}")]
        ])
        await message.bot.send_message(
            ADMIN_ID, 
            f"🆕 Yangi xodim so'rovi:\nIsmi: {message.from_user.full_name}\nID: {message.from_user.id}", 
            reply_markup=ikb
        )
        await message.answer("Sizning so'rovingiz adminga yuborildi. Tasdiqlanishini kuting⏳")
    elif user['status'] == 'pending':
        await message.answer("Sizning so'rovingiz hali admin tomonidan tasdiqlanmagan⏳")
    elif user['status'] == 'approved' or user['status'] == 'admin':
        await message.answer("Asosiy menyuga xush kelibsiz!", reply_markup=main_menu())
    else:
        await message.answer("Siz tizimdan chetlashtirilgansiz🚫")

# --- ADMIN PANEL ---
@router.callback_query(F.data.startswith("approve_"))
async def approve_user(call: CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await db.update_user_status(user_id, 'approved')
    await call.message.edit_text(f"{call.message.text}\n\n✅ Tasdiqlandi!")
    try:
        await call.bot.send_message(user_id, "Tabriklaymiz! Admin sizni tasdiqladi🎉", reply_markup=main_menu())
    except: pass

@router.callback_query(F.data.startswith("reject_"))
async def reject_user(call: CallbackQuery):
    user_id = int(call.data.split("_")[1])
    await db.update_user_status(user_id, 'fired')
    await call.message.edit_text(f"{call.message.text}\n\n❌ Rad etildi!")

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Siz admin emassiz🚫")
    
    total_cars, total_revenue = await db.get_general_stats()
    top_workers = await db.get_top_workers()
    
    text = f"👑 <b>Super Admin Panel</b>\n\n"
    text += f"🚗 Umumiy xizmat ko'rsatilgan avtomobillar: <b>{total_cars} ta</b>\n"
    text += f"💰 Umumiy tushum: <b>{total_revenue:,} UZS</b>\n\n"
    text += "🏆 <b>Top 5 xodimlar:</b>\n"
    
    for i, w in enumerate(top_workers, 1):
        text += f"{i}. {w[0]} - {w[1]} ta ish\n"
        
    await message.answer(text, parse_mode="HTML")

# --- FSM: YANGI AVTOMOBIL QO'SHISH ---
@router.message(F.text == "❌ Bekor qilish")
async def cancel_fsm(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Jarayon bekor qilindi.", reply_markup=main_menu())

@router.message(F.text == "🚗 Yangi avtomobil qo'shish")
async def start_add_service(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if user['status'] not in ['approved', 'admin']: return
    
    await state.set_state(AddService.car_model)
    await message.answer("Avtomobil modeli va yilini kiriting (Masalan: McLaren 765LT, 2023):", reply_markup=cancel_keyboard())

@router.message(AddService.car_model)
async def process_car_model(message: Message, state: FSMContext):
    if message.text == "⬅️ Orqaga": return await message.answer("Bu birinchi qadam. Bekor qilish uchun ❌ ni bosing.")
    
    await state.update_data(car_model=message.text)
    await state.set_state(AddService.modifications)
    await message.answer("Qilingan o'zgartirishlar/tyuning haqida batafsil yozing:")

@router.message(AddService.modifications)
async def process_modifications(message: Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await state.set_state(AddService.car_model)
        return await message.answer("Avtomobil modeli va yilini qaytadan kiriting:")
        
    await state.update_data(modifications=message.text)
    await state.set_state(AddService.price)
    await message.answer("Xizmat summasini kiriting (Faqat raqamlar, masalan: 5000000):")

@router.message(AddService.price)
async def process_price(message: Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await state.set_state(AddService.modifications)
        return await message.answer("Qilingan o'zgartirishlarni qaytadan kiriting:")
        
    if not message.text.isdigit():
        return await message.answer("⚠️ Iltimos, faqat raqam kiriting!")
        
    await state.update_data(price=int(message.text))
    await state.set_state(AddService.coworkers)
    
    # Hamkorlarni tanlash uchun inline keyboard
    workers = await db.get_all_active_workers()
    data = await state.get_data()
    data['selected_workers'] = [] # O'zini ham qo'shish kerak bo'lsa, shu yerda ID sini qo'shib qo'yish mumkin
    await state.update_data(selected_workers=data['selected_workers'])
    
    kb = await generate_workers_keyboard(workers, data['selected_workers'])
    await message.answer("Kimlar bilan ishladingiz? (O'zingizni ham belgilang)", reply_markup=kb)

async def generate_workers_keyboard(workers, selected_ids):
    buttons = []
    for w in workers:
        status = "✅ " if w['id'] in selected_ids else ""
        buttons.append([InlineKeyboardButton(text=f"{status}{w['full_name']}", callback_data=f"worker_{w['id']}")])
    buttons.append([InlineKeyboardButton(text="💾 Saqlash va Davom etish", callback_data="save_workers")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.callback_query(F.data.startswith("worker_"))
async def toggle_worker(call: CallbackQuery, state: FSMContext):
    worker_id = int(call.data.split("_")[1])
    data = await state.get_data()
    selected = data.get('selected_workers', [])
    
    if worker_id in selected:
        selected.remove(worker_id)
    else:
        selected.append(worker_id)
        
    await state.update_data(selected_workers=selected)
    workers = await db.get_all_active_workers()
    kb = await generate_workers_keyboard(workers, selected)
    await call.message.edit_reply_markup(reply_markup=kb)

@router.callback_query(F.data == "save_workers")
async def save_workers_step(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('selected_workers'):
        return await call.answer("Kamida bir kishini tanlang!", show_alert=True)
        
    await state.set_state(AddService.vin_code)
    await call.message.delete()
    await call.message.answer("Ajoyib! Fayl qanday nomlanishi uchun avtomobil VIN kodi yoki Davlat raqamini kiriting:")

@router.message(AddService.vin_code)
async def process_vin(message: Message, state: FSMContext):
    if message.text == "⬅️ Orqaga":
        await state.set_state(AddService.price)
        return await message.answer("Xizmat summasini qayta kiriting:")
        
    data = await state.get_data()
    vin_code = message.text.replace(" ", "_")
    
    # BAZAGA SAQLASH
    await db.add_service(
        car_model=data['car_model'],
        modifications=data['modifications'],
        price=data['price'],
        vin_code=vin_code,
        worker_ids=data['selected_workers']
    )
    
    # EXCEL GENERATSIYASI (Asinxron thread'da ishlatamiz)
    excel_file = await asyncio.to_thread(generate_premium_excel, data, vin_code)
    
    await message.answer_document(
        document=BufferedInputFile(excel_file, filename=f"{vin_code}_hisobot.xlsx"),
        caption="✅ Muvaffaqiyatli saqlandi va hisobot shakllantirildi!",
        reply_markup=main_menu()
    )
    await state.clear()

# --- PREMIUM EXCEL GENERATOR ---
def generate_premium_excel(data, vin_code):
    wb = Workbook()
    ws = wb.active
    ws.title = "Hisobot"
    
    headers = ["Sana", "Avtomobil", "Qilingan ishlar batafsil", "Summa", "Ishchilar ID lari"]
    ws.append(headers)
    
    # Sarlavha dizayni
    header_fill = PatternFill(start_color="B4D4FF", end_color="B4D4FF", fill_type="solid") # Och ko'k
    bold_font = Font(bold=True, color="000000")
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = bold_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
    import datetime
    today = datetime.datetime.now().strftime("%d.%m.%Y")
    
    ws.append([
        today,
        data['car_model'],
        data['modifications'],
        f"{data['price']} UZS",
        ", ".join(map(str, data['selected_workers']))
    ])
    
    # Auto-width (Kenglikni matnga moslashtirish)
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 3)
        ws.column_dimensions[column].width = adjusted_width

    # Faylni xotiraga saqlash
    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream.read()

# --- BACKGROUND TASK ---
async def background_tasks():
    while True:
        await db.cleanup_old_records()
        logging.info("Ma'lumotlar bazasi eski yozuvlardan tozalandi.")
        await asyncio.sleep(86400) # Har 24 soatda ishlaydi

# --- MAIN RUN ---
async def main():
    await db.init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    # Fon vazifasini (cleanup) ishga tushirish
    asyncio.create_task(background_tasks())
    
    logging.info("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
