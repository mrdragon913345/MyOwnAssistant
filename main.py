import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# /start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ආයුබෝවන්! 👋 I am Telegram Assistant Bot.!")

# Echo message (එවන පණිවිඩ වලට පිළිතුරු දීම)
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"ඔයා කිව්වේ: {update.message.text}")

if __name__ == '__main__':
    # Railway Variables වලින් හෝ direct token එක ලබාගැනීම
    TOKEN = os.environ.get("BOT_TOKEN", "8447401830:AAE0dVuYXAuJljd8bo5zP6U3pfJBqQIT5hk")
    
    print("Bot starting...")
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    # Run Bot
    app.run_polling()
