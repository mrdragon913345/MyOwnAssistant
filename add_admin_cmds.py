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
    from bot.utils.db import db_add_code
    from bot.utils.usage import override_premium
    from telegram.constants import ParseMode
    import string
    import random
    import html
    
    if not is_admin_user(update.effective_user.id): return
    parts = update.message.text.split()
    if len(parts) < 3:
        await update.message.reply_text("<b>Usage:</b>\\n<code>/op gen [days] [count]</code> - Generate keys\\n<code>/op [userid] [days]</code> - Auth user directly", parse_mode=ParseMode.HTML)
        return
        
    mode = parts[1].lower()
    
    if mode == "gen":
        try:
            val = int(parts[2])
            if val <= 0: raise ValueError
        except ValueError:
            await update.message.reply_text("<b>Error:</b> DAYS must be a positive number.", parse_mode=ParseMode.HTML)
            return
            
        count = 1
        if len(parts) >= 4:
            try:
                count = int(parts[3])
                if count <= 0: raise ValueError
                if count > 50:
                    await update.message.reply_text("<b>Count cannot exceed 50.</b>", parse_mode=ParseMode.HTML)
                    return
            except ValueError:
                await update.message.reply_text("<b>Error:</b> COUNT must be a positive number.", parse_mode=ParseMode.HTML)
                return

        def _pe(eid, fallback):
            return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'
        
        e_pin = _pe('5039600026809009149', '📌')
        e_fire = _pe('5039644681583985437', '🔥')
        e_check = _pe('5895231943955451762', '✅')
        e_alien = _pe('5895254947800291880', '👾')
        e_dia = _pe('5042050649248760772', '💎')
        e_heart = _pe('5039544445637231745', '💖')
        e_devil = _pe('6181349715888577684', '👿')
        e_doge = _pe('6064122088237566417', '🐶')
        
        msg = f"{e_pin}{e_fire} <b>𝙊𝙉𝙇𝙂𝙀𝙉 𝙆𝙚𝙮𝙨</b> {e_check}\\n"
        msg += f"━━━━━━━━━━━━━━━━━━━━\\n\\n"
        msg += f"┣ {e_alien} <b>𝗖𝗼𝘂𝗻𝘁 ➜</b> {count:02d}\\n"
        msg += f"┣ {e_dia} <b>𝗣𝗹𝗮𝗻 ➜</b> {val} Days Premium\\n"
        msg += f"┣ {e_heart} <b>𝗞𝗲𝘆𝘀</b>\\n"

        for _ in range(count):
            suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
            code = f"ONLGEN-{suffix}"
            db_add_code(code, 'premium', val)
            msg += f"┣ <code>{code}</code>\\n"
            
        msg += f"\\n{e_devil} <b>𝗨𝘀𝗲𝗿𝘀 𝗿𝗲𝗱𝗲𝗲𝗺 𝘄𝗶𝘁𝗵 /redeem [key]</b> {e_doge}"
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
        
    else:
        # Auth mode
        target = parts[1]
        days = parts[2]
        
        if target.startswith("@"):
            try:
                chat = await context.bot.get_chat(target)
                target = str(chat.id)
            except Exception as e:
                await update.message.reply_text(f"<b>Error:</b> Could not resolve username <code>{html.escape(target)}</code>.", parse_mode=ParseMode.HTML)
                return
                
        try:
            if str(days).lower() == 'lifetime':
                d_val = 'lifetime'
            else:
                d_val = int(days)
        except ValueError:
            await update.message.reply_text(f"<b>Error:</b> DAYS must be a number or 'lifetime'.", parse_mode=ParseMode.HTML)
            return
            
        override_premium(target, d_val)
        await update.message.reply_text(f"✅ <b>Authorized:</b> <code>{target}</code> is now a Premium User for <b>{days}</b> days.", parse_mode=ParseMode.HTML)
"""

with open('bot/handlers/admin.py', 'a', encoding='utf-8') as f:
    f.write(code)
print("Done")
