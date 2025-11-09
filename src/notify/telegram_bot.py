
import os, asyncio
from aiogram import Bot
from loguru import logger

async def send_signal_async(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.debug("Telegram not configured, skipping message")
        return
    bot = Bot(token=token)
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        logger.exception("Failed to send telegram message: {}", exc)
    finally:
        await bot.session.close()

def send_signal(text: str):
    # Safe run even if loop already exists
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(send_signal_async(text))
    else:
        loop.create_task(send_signal_async(text))
