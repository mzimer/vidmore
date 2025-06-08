import os
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000/api")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(",", " ").split() if x]

bot = Bot(token=BOT_TOKEN, default=types.DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# FSM States
class AddTask(StatesGroup):
    waiting_for_video_url = State()

async def api_get_user(telegram_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/users/{telegram_id}") as resp:
            if resp.status == 404:
                return None
            return await resp.json()

async def api_register_user(telegram_id):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BACKEND_URL}/users/register", params={"telegram_id": telegram_id}) as resp:
            return await resp.json()

async def api_create_task(telegram_id, video_url):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BACKEND_URL}/tasks/create", params={
            "telegram_id": telegram_id,
            "video_url": video_url
        }) as resp:
            return await resp.json()

async def api_get_tasks(telegram_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/tasks/{telegram_id}") as resp:
            return await resp.json()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    telegram_id = str(message.from_user.id)
    user = await api_get_user(telegram_id)
    if user:
        status = user.get("status")
        if status == "pending":
            await message.answer("Вы подали заявку на регистрацию. Ожидайте подтверждения администратора.")
        elif status == "approved":
            await message.answer(
                "Вы уже зарегистрированы и одобрены. Добро пожаловать!",
                reply_markup=main_menu_keyboard()
            )
        elif status == "rejected":
            await message.answer("Ваша заявка отклонена. Доступ запрещён.")
        else:
            await message.answer("Неизвестный статус пользователя.")
        return

    reg_user = await api_register_user(telegram_id)
    if reg_user.get("status") == "pending":
        await message.answer("Вы подали заявку на регистрацию. Ожидайте подтверждения администратора.")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=f"approve:{telegram_id}:{message.chat.id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{telegram_id}:{message.chat.id}"
                ),
            ]
        ])
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"⏳ <b>Новый пользователь</b>\n"
                    f"ID: <code>{telegram_id}</code>\n"
                    f"Имя: {message.from_user.full_name}",
                    reply_markup=kb
                )
            except Exception as e:
                print(f"Ошибка при отправке админу {admin_id}: {e}")

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Добавить задачу")],
            [KeyboardButton(text="📋 Мои задачи")]
        ],
        resize_keyboard=True
    )

@dp.message(F.text == "🎬 Добавить задачу")
async def ask_video_url(message: types.Message, state: FSMContext):
    telegram_id = str(message.from_user.id)
    user = await api_get_user(telegram_id)
    if not user or user.get("status") != "approved":
        await message.answer("Вы не одобрены для использования сервиса.")
        return
    await message.answer("Пожалуйста, отправьте ссылку на видео.")
    await state.set_state(AddTask.waiting_for_video_url)

@dp.message(AddTask.waiting_for_video_url)
async def get_video_url(message: types.Message, state: FSMContext):
    telegram_id = str(message.from_user.id)
    user = await api_get_user(telegram_id)
    if not user or user.get("status") != "approved":
        await message.answer("Вы не одобрены для использования сервиса.")
        await state.clear()
        return
    video_url = message.text.strip()
    if not video_url.startswith("http"):
        await message.answer("Похоже, это не ссылка. Пожалуйста, попробуйте снова.")
        return
    result = await api_create_task(telegram_id, video_url)
    await message.answer(
        f"Задача добавлена!\nID: <b>{result.get('task_id')}</b>\nСтатус: <b>{result.get('status')}</b>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )
    await state.clear()

@dp.message(F.text == "📋 Мои задачи")
async def show_my_tasks(message: types.Message):
    telegram_id = str(message.from_user.id)
    tasks = await api_get_tasks(telegram_id)
    if not tasks or (isinstance(tasks, dict) and tasks.get("detail") == "User not found"):
        await message.answer("У вас пока нет задач.")
        return
    text = "<b>Ваши задачи:</b>\n"
    for task in tasks:
        text += f"ID: <b>{task['task_id']}</b> | Статус: <b>{task['status']}</b>\nВидео: {task['video_url']}\n\n"
    await message.answer(text, parse_mode="HTML")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
