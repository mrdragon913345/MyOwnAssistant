import sys

code = """
async def inclimit_cmd(update, context):
    from bot.utils.helpers import is_admin_user
    from bot.core.config import bot_settings, save_settings
    from telegram.constants import ParseMode
    
    if not is_admin_user(update.effective_user.id): return
    parts = update.message.text.split()
    if len(parts) < 3:
        await update.message.reply_text("<b>Usage:</b> <code>/inclimit USER_ID LIMIT</code>", parse_mode=ParseMode.HTML)
        return
        
    uid = parts[1]
    try:
        limit = int(parts[2])
    except ValueError:
        await update.message.reply_text("<b>Error:</b> LIMIT must be a number.", parse_mode=ParseMode.HTML)
        return
        
    bot_settings[f"custom_limit_{uid}"] = limit
    save_settings()
    await update.message.reply_text(f"<b>Success:</b> User <code>{uid}</code> custom limit set to <b>{limit}</b>.", parse_mode=ParseMode.HTML)

async def op_cmd(update, context):
    from bot.utils.helpers import is_admin_user
    from bot.core.config import bot_settings, save_settings
    from telegram.constants import ParseMode
    
    if not is_admin_user(update.effective_user.id): return
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("<b>Usage:</b> <code>/op USER_ID</code>", parse_mode=ParseMode.HTML)
        return
        
    uid = parts[1]
    ops = bot_settings.get("operators", [])
    if uid not in ops:
        ops.append(uid)
        bot_settings["operators"] = ops
        save_settings()
        
    await update.message.reply_text(f"✅ <b>Success:</b> User <code>{uid}</code> is now an Operator. They can use /auth and /gen.", parse_mode=ParseMode.HTML)

async def deop_cmd(update, context):
    from bot.utils.helpers import is_admin_user
    from bot.core.config import bot_settings, save_settings
    from telegram.constants import ParseMode
    
    if not is_admin_user(update.effective_user.id): return
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("<b>Usage:</b> <code>/deop USER_ID</code>", parse_mode=ParseMode.HTML)
        return
        
    uid = parts[1]
    ops = bot_settings.get("operators", [])
    if uid in ops:
        ops.remove(uid)
        bot_settings["operators"] = ops
        save_settings()
        
    await update.message.reply_text(f"❌ <b>Success:</b> User <code>{uid}</code> is no longer an Operator.", parse_mode=ParseMode.HTML)
"""

with open('bot/handlers/admin.py', 'a', encoding='utf-8') as f:
    f.write(code)
print("Done")
