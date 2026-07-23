import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! My Telegram Bot is Active!")

if __name__ == '__main__':
    # Telegram Bot Token එක Railway Variables වලින් ලබාගනී
    TOKEN = os.environ.get("8447401830:AAE0dVuYXAuJljd8bo5zP6U3pfJBqQIT5hk")
    
    if not TOKEN:
        print("Error: BOT_TOKEN Environment Variable is missing!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        
        print("Bot is running...")
        app.run_polling()