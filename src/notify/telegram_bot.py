
import os, asyncio
from aiogram import Bot

async def send_signal_async(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    bot = Bot(token=token)
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview=True)
    finally:
        await bot.session.close()

def send_signal(text: str):
    # Safe run even if loop already exists
    try:
        asyncio.run(send_signal_async(text))
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.create_task(send_signal_async(text))
