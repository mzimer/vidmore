import os
import aiohttp
import asyncio
import subprocess
import re
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
DOWNLOADS_PATH = "/downloads"  # В docker-compose пробросить ./downloads:/downloads

# Для aiogram >=3.4
try:
    bot = Bot(token=BOT_TOKEN, default=types.DefaultBotProperties(parse_mode=ParseMode.HTML))
except AttributeError:
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)

dp = Dispatcher()

class AddTask(StatesGroup):
    waiting_for_video_url = State()

def is_supported_link(url: str):
    supported_patterns = [
        r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/',
        r'(https?://)?(www\.)?vk\.com/video',
        r'(https?://)?(www\.)?rutube\.ru/video',
        r'(https?://)?(www\.)?dzen\.ru/video',
    ]
    return any(re.search(p, url) for p in supported_patterns)

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

async def api_create_task(telegram_id, video_url, action=None):
    async with aiohttp.ClientSession() as session:
        params = {
            "telegram_id": telegram_id,
            "video_url": video_url
        }
        if action:
            params["action"] = action
        async with session.post(f"{BACKEND_URL}/tasks/create", params=params) as resp:
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
    if not is_supported_link(video_url):
        await message.answer("Пока поддерживаются только YouTube, VK Видео, RuTube и Яндекс.Дзен.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬇️ Скачать", callback_data=f"download:{video_url}"),
            InlineKeyboardButton(text="♻️ Перезалить", callback_data=f"reupload:{video_url}")
        ]
    ])
    await message.answer("Что сделать с этим видео?", reply_markup=kb)
    await state.clear()

@dp.message(F.text == "📋 Мои задачи")
async def show_my_tasks(message: types.Message):
    telegram_id = str(message.from_user.id)
    tasks = await api_get_tasks(telegram_id)
    if not tasks or (isinstance(tasks, dict) and tasks.get("detail") == "User not found") or len(tasks) == 0:
        await message.answer("У вас пока нет задач.")
        return
    text = "<b>Ваши задачи:</b>\n"
    for task in tasks:
        text += f"ID: <b>{task['task_id']}</b> | Статус: <b>{task['status']}</b>\nВидео: {task['video_url']}\n\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text.regexp(r'https?://'))
async def process_link_message(message: types.Message, state: FSMContext):
    url = message.text.strip()
    telegram_id = str(message.from_user.id)
    user = await api_get_user(telegram_id)
    if not user or user.get("status") != "approved":
        await message.answer("Вы не одобрены для использования сервиса.")
        return

    if is_supported_link(url):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⬇️ Скачать", callback_data=f"download:{url}"),
                InlineKeyboardButton(text="♻️ Перезалить", callback_data=f"reupload:{url}")
            ]
        ])
        await message.answer("Что сделать с этим видео?", reply_markup=kb)
    else:
        await message.answer("Пока поддерживаются только YouTube, VK Видео, RuTube и Яндекс.Дзен.")

@dp.callback_query(F.data.startswith("download:"))
async def handle_download(callback: types.CallbackQuery):
    url = callback.data.split(":", 1)[1]
    telegram_id = str(callback.from_user.id)
    await callback.answer("⏳ Скачиваем видео...")

    # Добавляем задачу в БД
    await api_create_task(telegram_id, url, action="download")

    await bot.send_message(telegram_id, "Начинаю скачивание видео. Это может занять несколько минут.")
    os.makedirs(DOWNLOADS_PATH, exist_ok=True)
    try:
        # Запускаем скачивание (worker должен быть в папке backend)
        result = subprocess.run(
            ["python", "backend/download_worker.py", url, DOWNLOADS_PATH],
            capture_output=True, text=True
        )
        filepath = result.stdout.strip()
        if os.path.isfile(filepath):
            await bot.send_document(telegram_id, types.FSInputFile(filepath))
            await bot.send_message(telegram_id, "✅ Видео успешно скачано!")
        else:
            await bot.send_message(telegram_id, "❌ Не удалось скачать видео (файл не найден).")
    except Exception as e:
        await bot.send_message(telegram_id, f"Ошибка при скачивании: {e}")

@dp.message()
async def catch_all(message: types.Message):
    if message.text and not message.text.startswith("/"):
        await message.answer("Пожалуйста, отправьте ссылку на видео или воспользуйтесь меню.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
