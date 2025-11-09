
# Quick check for TELEGRAM_BOT_TOKEN/CHAT_ID and send a test message
import os, asyncio
from aiogram import Bot
from pathlib import Path
from dotenv import load_dotenv

# load .env from project root
root = Path(__file__).resolve().parents[1]
env = root/".env"
if env.exists():
    load_dotenv(env)

async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat  = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("❗ Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        print(f"Bot: @{me.username} ({me.id}) — sending test message...")
        await bot.send_message(chat_id=chat, text="✅ AI Coin Hunter: test message OK")
        print("✅ Sent. If you don't see it: check bot is added to the chat/channel and has rights.")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
