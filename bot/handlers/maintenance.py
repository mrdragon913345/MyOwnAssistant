from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ApplicationHandlerStop
from bot.core import state
from bot.utils.helpers import is_admin_user
from bot.utils.formatter import EMOJI_WRONG

async def maintenance_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = None
    if update.effective_user:
        uid = update.effective_user.id
        
    if not uid:
        return
    if not state.bot_operational and not is_admin_user(uid):
        try:
            if update.message:
                text = update.message.text or update.message.caption or ""
                if text.startswith("/"):
                    await update.message.reply_text(
                        f"{EMOJI_WRONG} <b>Maintenance Mode:</b> The bot is currently undergoing maintenance and is temporarily offline. Please try again later.", 
                        parse_mode=ParseMode.HTML
                    )
            elif update.callback_query:
                await update.callback_query.answer("Bot is currently in Maintenance Mode.", show_alert=True)
        except:
            pass
        raise ApplicationHandlerStop()
