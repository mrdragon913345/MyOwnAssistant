import time
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.core.config import *
from bot.core.state import *
import bot.core.state as state
from bot.utils.helpers import btn, save_json, is_admin_user, load_json_dict, is_banned
from bot.utils.usage import is_premium, set_premium, add_credits, _usage_lock
from bot.hits_sender import get_today_count
from bot.handlers.shopify_cmds import safe_bin_info
from bot.utils.formatter import format_redeemed_message
import re
import os
import random

async def bin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    text = update.message.text.split(' ', 1)
    if len(text) < 2:
        return await update.message.reply_html(f"{EMOJI_CARD} <b>Usage:</b> <code>/bin 411111</code>")
    
    bin_str = re.sub(r'\D', '', text[1])
    if len(bin_str) < 6:
        return await update.message.reply_html(f"{EMOJI_WRONG} <b>Invalid BIN:</b> Must be at least 6 digits.")
        
    status_msg = await update.message.reply_html(f"{EMOJI_START} <b>Looking up BIN:</b> <code>{bin_str[:6]}...</code>")
    
    try:
        bin_info = await safe_bin_info(bin_str[:6])
        import html
        from bot.utils.formatter import _e
        from bot.utils.formatter import to_sans, to_bold_sans
        
        brand_esc = html.escape(str(bin_info.get('brand') or 'UNKNOWN').upper())
        ctype_esc = html.escape(str(bin_info.get('type') or 'UNKNOWN').upper())
        level_esc = html.escape(str(bin_info.get('level') or '').upper())
        level_str = f" - {level_esc}" if level_esc else ""
        bank_esc = html.escape(str(bin_info.get('bank') or 'UNKNOWN').upper())
        country_display = html.escape(str(bin_info.get('country') or 'UNKNOWN')).upper()

        e_bin = _e("5258274739041883702", "🔎")
        e_sword = _e("5453991094435997597", "⚔️")
        e_crown = _e("5201906965478930360", "👑")
        e_dev = _e("5258196742435787040", "👾")
        e_exo = _e("5204236147718387299", "✅")

        top_title = f"{to_bold_sans('BIN Lookup Result')} {e_bin}"
        
        res = f"""{top_title}

[{e_bin}] {to_sans("Bin")} - <code>{bin_info.get('bin')}</code>
[{e_bin}] {to_sans("Bin Details")} - <code>{brand_esc} - {ctype_esc}{level_str}</code>
[{e_bin}] {to_sans("Bank")} - <code>{bank_esc}</code>
[{e_bin}] {to_sans("Country")} - <code>{country_display}</code>

{e_sword} {to_sans("Powered By")} {to_bold_sans("WenaxChk")} {e_crown}
{e_dev} {to_sans("Developer")} ➜ {to_bold_sans("Exo")} {e_exo}"""
        await status_msg.edit_text(res, parse_mode=ParseMode.HTML)
    except Exception as e:
        await status_msg.edit_text(f"{EMOJI_WRONG} <b>Error looking up BIN:</b> {e}", parse_mode=ParseMode.HTML)

def start_logic(user):
    from bot.utils.usage import check_auth, is_premium
    from bot.utils.helpers import is_admin_user
    uid_str = str(user.id)
    if is_admin_user(user.id):
        acc_status = "Admin"
    elif is_premium(user.id):
        acc_status = "Premium"
    else:
        acc_status = "Free"
    
    import html
    user_info = f"@{user.username}" if user.username else f"<code>{html.escape(user.first_name)}</code>"
    first_name_safe = html.escape(user.first_name) if user.first_name else "User"
    text = (
        f"<b>Welcome <code>{first_name_safe}</code>!</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<b>User:</b> {user_info}\n"
        f"<b>ID:</b> <code>{uid_str}</code>\n"
        f"<b>Status:</b> {acc_status}\n"
        f"━━━━━━━━━━━━━━\n"
        f"Use the buttons below to navigate."
    )

    keyboard = [
        [
            btn("Gates", callback_data="chk_help", style="primary", icon_id=ID_GATE)
        ],
        [
            btn("Referral Program", callback_data="ref_menu", style="success", icon_id="6179411633371095707")
        ],
        [
            btn("Support", url="https://t.me/trackyyyy", style="primary", icon_id=ID_ID),
            btn("Close", callback_data="close_menu", style="danger", icon_id=ID_DEAD)
        ]
    ]

        
    from bot.utils.helpers import is_admin_user
    if is_admin_user(user.id):
        keyboard.append([btn("Admin Menu", callback_data="admin_menu", style="success", icon_id=ID_TOOLS)])
        
    return text, keyboard

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.utils.usage import is_premium, get_premium_time_left
    from bot.utils.helpers import is_admin_user
    from bot.utils.db import db_get_total_charged
    import html

    user = update.effective_user
    uid = user.id
    target_uid = uid
    target_name = html.escape(user.first_name) if user.first_name else "User"

    if is_admin_user(uid):
        if update.message.reply_to_message:
            target_uid = update.message.reply_to_message.from_user.id
            target_name = html.escape(update.message.reply_to_message.from_user.first_name) if update.message.reply_to_message.from_user.first_name else f"User {target_uid}"
        elif context.args:
            try:
                target_uid = int(context.args[0])
                target_name = f"User {target_uid}"
            except ValueError:
                pass

    if is_admin_user(target_uid):
        plan = "Admin"
        expire_str = ""
    elif is_premium(target_uid):
        plan = "𝗣𝗿𝗲𝗺𝗶𝘂𝗺"
        time_left = get_premium_time_left(target_uid)
        expire_str = f"┣ ➜ 𝗘𝘅𝗽𝗶𝗿𝗲 𝗜𝗻 : {time_left}\n"
    else:
        plan = "𝗡𝗼𝗻𝗲"
        expire_str = ""

    total_charged = db_get_total_charged(target_uid)

    title = "𝗬𝗼𝘂𝗿 𝗔𝗰𝗰𝗼𝘂𝗻𝘁 𝗜𝗻𝗳𝗼" if target_uid == uid else "𝗨𝘀𝗲𝗿 𝗔𝗰𝗰𝗼𝘂𝗻𝘁 𝗜𝗻𝗳𝗼"

    text = (
        f"{title}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"┣ ➜ 𝗡𝗮𝗺𝗲 : ⏤ ↯{target_name}\n"
        f"┣ ➜ 𝗣𝗹𝗮𝗻 : {plan}\n"
        f"{expire_str}"
        f"┣ ➜ 𝗜𝗗 : <code>{target_uid}</code>\n"
        f"┣ ➜ 𝗧𝗼𝘁𝗮𝗹 𝗖𝗵𝗮𝗿𝗴𝗲𝘀 : {total_charged}"
    )

    await update.message.reply_text(text, parse_mode='HTML')

async def close_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.message and query.message.reply_to_message:
        from bot.utils.helpers import is_admin_user
        if query.from_user.id != query.message.reply_to_message.from_user.id and not is_admin_user(query.from_user.id):
            await query.answer("This button is not for you.", show_alert=True)
            return
    await query.answer()
    await query.message.delete()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    # Process referral links
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("ref_"):
            inviter_id = arg.split("_")[1]
            if str(inviter_id) != str(uid):
                from bot.utils.db import db_set_invited_by, db_add_referral_reward, db_get_user
                # Ensure the new user is actually in the DB before trying to update invited_by
                db_get_user(uid)
                
                if db_set_invited_by(uid, inviter_id):
                    if db_add_referral_reward(inviter_id, max_days=10):
                        from bot.utils.usage import set_premium
                        set_premium(inviter_id, 1)
                        # Notify the inviter
                        try:
                            from bot.utils.formatter import _e
                            # Using the exact emojis from the screenshot
                            e_party = _e("6181381563071077485", "🎉")
                            e_star = _e("5893494861612455015", "🌟")
                            e_clock = _e("5893149782465057649", "⏱️")
                            
                            ref_msg = (
                                f"<b>{e_party} New Referral</b>\n\n"
                                f"{e_star} A new user just joined the bot using your invite link\n\n"
                                f"{e_clock} +1 Day has been added to your balance"
                            )
                            await context.bot.send_message(
                                chat_id=int(inviter_id),
                                text=ref_msg,
                                parse_mode=ParseMode.HTML
                            )
                        except Exception as e:
                            import logging
                            logging.getLogger(__name__).error(f"Failed to send referral notification: {e}")

    text, keyboard = start_logic(user)
    
    # Using a cleaner direct Giphy URL
    gif_url = "https://i.giphy.com/media/bqSkJ4IwNcoZG/giphy.gif"
    

    
    try:
        await update.message.reply_animation(
            animation=gif_url,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        # If the GIF fails to send, log it and fall back to normal text
        import logging
        logging.getLogger(__name__).error(f"Failed to send start GIF: {e}")
        await update.message.reply_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode=ParseMode.HTML, 
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.utils.helpers import is_admin_user
    from bot.core.config import EMOJI_TOOLS
    
    help_text = (
        f"{EMOJI_BULB} <b>Shopify Checker Bot Help</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>User Commands</b>\n"
        f"• <code>/start</code> - Check bot status & user menu\n"
        f"• <code>/redeem code</code> - Redeem premium/credits\n"
        f"• <code>/bin 123456</code> - Check BIN info\n"
        f"• <code>/setproxy ip:port</code> - Set your custom proxy\n"
        f"• <code>/rmproxy</code> - Remove custom proxy\n\n"
        f"🛒 <b>Shopify Gateway Commands</b>\n"
        f"• <code>/sh</code> - Shopify Auth Single Check\n"
        f"• <code>/msh</code> - Shopify Auth Mass Check (reply to .txt)\n"
    )
    
    if is_admin_user(update.effective_user.id):
        help_text += (
            f"\n<b>Admin Commands:</b>\n"
            f"📢 <code>/broadcast</code> - Message all users\n"
            f"📊 <code>/status</code> - System health\n"
            f"🚫 <code>/ban</code> | <code>/unban</code> - Ban control\n"
            f"💎 <code>/rmprem</code> | <code>/keysdays</code> | <code>/preusers</code> - Premium Management\n"
            f"💰 <code>/addcredits</code> | <code>/distribute</code> - Credits Management\n"
            f"🎟 <code>/gen</code> [prem/credit] [val] - Generate code\n"
            f"⏳ <code>/setdelay</code> [prem/free] - Set delay per check\n"
            f"📊 <code>/setlimit</code> [prem/free] - Set daily quota limits\n"
            f"📦 <code>/setmasslimit</code> [prem/free] - Set mass check batch size\n"
            f"🛍️ <code>/addsite</code> | <code>/delsite</code> | <code>/sites</code> - Shopify sites\n"
            f"⚙️ <code>/setapi</code> - Backend configs\n"
        )
        
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def ref_menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    from bot.utils.db import db_get_referral_stats
    from bot.utils.formatter import _e
    
    stats = db_get_referral_stats(uid)
    invited = stats.get('total_invited', 0)
    days = stats.get('earned_days', 0)
    
    bot_username = context.bot.username
    invite_link = f"https://t.me/{bot_username}?start=ref_{uid}"
    
    # Emojis from screenshot 2
    e_trophy = _e("6179411633371095707", "🏆")
    e_chart = _e("5895444149699612825", "📊")
    e_user = _e("5445174334031166029", "👤")
    e_diamond = _e("5343636681473935403", "💎")
    e_link = _e("5902449142575141204", "🔗")
    
    msg = (
        f"<b>{e_trophy} Referral Program</b>\n\n"
        f"Invite your friends to the bot and earn rewards! For every user that joins using your link, you will receive 1 Day of premium\n\n"
        f"<b>{e_chart} Your Stats</b>\n"
        f"➔ {e_user} Total Invited: {invited} user\n"
        f"➔ {e_diamond} Total Premium Days: {days} Days\n\n"
        f"<b>{e_link} Your Invite Link</b>\n"
        f"<code>{invite_link}</code>"
    )
    
    keyboard = [
        [btn("Back to Menu", callback_data="start_menu", style="danger", icon_id=ID_DEAD)]
    ]
    
    if query:
        await query.answer()
        await query.edit_message_caption(
            caption=msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )

async def redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not update.message or not update.message.text: return
    
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text(f"{EMOJI_RANK} <b>Usage:</b> <code>/redeem YOUR_CODE</code>", parse_mode=ParseMode.HTML)
        return
        
    code = parts[1].strip()
    
    from bot.utils.db import db_get_code, db_delete_code_atomic
    code_info = db_get_code(code)
    if not code_info:
        fail_msg = (
            '<tg-emoji emoji-id="6066522498214659917">🤖</tg-emoji> <b>Redemption Failed!</b>\n\n'
            '<tg-emoji emoji-id="6188140239572179895">🤖</tg-emoji> <b>Key already redeemed</b>'
        )
        await update.message.reply_text(fail_msg, parse_mode=ParseMode.HTML)
        return
    ctype = code_info.get('type', 'credits')
    val = code_info.get('value', 0)

    from bot.utils.usage import is_premium, get_all_premium_dict
    if is_premium(uid):
        if ctype == 'credits':
            fail_msg = (
                '<tg-emoji emoji-id="6066522498214659917">🤖</tg-emoji> <b>Redemption Failed!</b>\n\n'
                '<b>You already have an active Premium plan and do not need credits.</b>'
            )
            await update.message.reply_text(fail_msg, parse_mode=ParseMode.HTML)
            return
        if ctype == 'premium':
            fail_msg = (
                '<tg-emoji emoji-id="6181467651395558500">❌</tg-emoji> <b>Redemption Failed!</b>\n\n'
                '<b>You already have an active Premium plan. You cannot redeem another Premium key.</b>'
            )
            await update.message.reply_text(fail_msg, parse_mode=ParseMode.HTML)
            return
        if get_all_premium_dict().get(str(uid)) == "lifetime":
            fail_msg = (
                '<tg-emoji emoji-id="6066522498214659917">🤖</tg-emoji> <b>Redemption Failed!</b>\n\n'
                '<b>You already have Lifetime Premium.</b>'
            )
            await update.message.reply_text(fail_msg, parse_mode=ParseMode.HTML)
            return

    if not db_delete_code_atomic(code):
        fail_msg = (
            '<tg-emoji emoji-id="6066522498214659917">🤖</tg-emoji> <b>Redemption Failed!</b>\n\n'
            '<tg-emoji emoji-id="6188140239572179895">🤖</tg-emoji> <b>Key already redeemed</b>'
        )
        await update.message.reply_text(fail_msg, parse_mode=ParseMode.HTML)
        return

    import html
    user = update.effective_user
    username = html.escape(user.username) if user.username else None
    first_name = html.escape(user.first_name) if user.first_name else "User"
    user_tag = f"@{username}" if username else f"<code>{first_name}</code>"

    if ctype == 'premium':
        set_premium(uid, val)
    else:
        add_credits(uid, val)

    msg = format_redeemed_message(user_tag, ctype, val)
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    fsub_group = bot_settings.get("fsub_group")
    if fsub_group:
        fsub_group_id = None
        try:
            fsub_group_id = int(fsub_group)
        except ValueError:
            fsub_group_id = fsub_group
            
        if str(update.effective_chat.id) != str(fsub_group) and update.effective_chat.id != fsub_group_id:
            try:
                from telegram import LinkPreviewOptions
                await context.bot.send_message(
                    chat_id=fsub_group,
                    text=msg,
                    parse_mode=ParseMode.HTML,
                    link_preview_options=LinkPreviewOptions(is_disabled=True)
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to send redeem message to fsub_group {fsub_group}: {e}")

async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import asyncio
    import html
    import re
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaDocument
    from telegram.constants import ParseMode
    from bot.core.config import ADMIN_IDS, EMOJI_DONE, EMOJI_WRONG
    import bot.core.state as state

    user = update.effective_user
    msg = update.message
    
    if not ADMIN_IDS:
        return
    admin_id = ADMIN_IDS[0]

    # Handle albums (media groups)
    group_id = msg.media_group_id or str(msg.message_id)

    if not hasattr(state, 'feedback_albums'):
        state.feedback_albums = {}

    if group_id not in state.feedback_albums:
        state.feedback_albums[group_id] = {
            'msgs': [],
            'timer_started': False,
            'caption_html': ""
        }

    state.feedback_albums[group_id]['msgs'].append(msg)

    # Extract caption if it exists
    raw_html = ""
    cmd_text = msg.text or msg.caption or ""
    cmd_text_stripped = cmd_text.replace("/f", "", 1).strip()

    if cmd_text_stripped:
        if msg.text:
            raw_html = msg.text_html
            raw_html = re.sub(r'(?i)(?:^|\s)/f\b\s*', ' ', raw_html).strip()
            raw_html = re.sub(r'<span class="tg-custom-emoji" data-custom-emoji-id="([^"]+)">([^<]+)</span>', r'<tg-emoji emoji-id="\1">\2</tg-emoji>', raw_html)
        else:
            raw_html = msg.caption_html
            raw_html = re.sub(r'(?i)(?:^|\s)/f\b\s*', ' ', raw_html).strip()
            raw_html = re.sub(r'<span class="tg-custom-emoji" data-custom-emoji-id="([^"]+)">([^<]+)</span>', r'<tg-emoji emoji-id="\1">\2</tg-emoji>', raw_html)
    elif msg.reply_to_message:
        raw_html = msg.reply_to_message.text_html or msg.reply_to_message.caption_html or ""
        raw_html = re.sub(r'<span class="tg-custom-emoji" data-custom-emoji-id="([^"]+)">([^<]+)</span>', r'<tg-emoji emoji-id="\1">\2</tg-emoji>', raw_html)

    if raw_html:
        state.feedback_albums[group_id]['caption_html'] = raw_html

    # Start the collection timer only for the first message in the group
    if not state.feedback_albums[group_id]['timer_started']:
        state.feedback_albums[group_id]['timer_started'] = True
        
        # Wait for other media in the same group to arrive
        if msg.media_group_id:
            await asyncio.sleep(1.2)
            
        album_data = state.feedback_albums.pop(group_id, None)
        if not album_data:
            return
            
        msgs = album_data['msgs']
        final_caption = album_data['caption_html']
        
        has_media = any(m.photo or m.document or (m.reply_to_message and (m.reply_to_message.photo or m.reply_to_message.document)) for m in msgs)
        if not final_caption.strip() and not has_media:
            await msgs[0].reply_text(f"{EMOJI_WRONG} <b>Usage:</b> Reply to a photo/message or send <code>/f your feedback</code>", parse_mode=ParseMode.HTML)
            return

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve", callback_data=f"fb_appr_{user.id}_{group_id}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"fb_rej_{user.id}_{group_id}")]
        ])

        user_name_esc = html.escape(user.first_name)
        
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
        
        feedback_str = (
            f'{e_pin}{e_fire} <b>𝙒𝙚𝙣𝙖𝙭𝘾𝙝𝙠 𝙐𝙨𝙚𝙧 𝙁𝙚𝙚𝙙𝙗𝙖𝙘𝙠</b> {e_check}\n'
            f'━━━━━━━━━━━━━━━━━━━━\n\n'
            f'┣ {e_alien} <b>𝗙𝗲𝗲𝗱𝗯𝗮𝗰𝗸 𝗙𝗿𝗼𝗺 ➜</b> <u>{user_name_esc}</u>\n'
            f'┣ {e_dia} <b>𝗨𝘀𝗲𝗿 𝗜𝗗 ➜</b> <code>{user.id}</code>\n'
            f'┣ {e_heart} <b>𝗙𝗲𝗲𝗱𝗯𝗮𝗰𝗸</b>\n'
            f'┣ {final_caption}\n\n'
            f'{e_devil} <b>𝗧𝗵𝗮𝗻𝗸𝘀 𝗳𝗼𝗿 𝘂𝘀𝗶𝗻𝗴 𝗪𝗲𝗻𝗮𝘅𝗖𝗵𝗸!</b> {e_doge}'
        )
        
        admin_text = feedback_str

        media_list = []
        file_refs = []
        for m in msgs:
            p = m.photo or (m.reply_to_message.photo if m.reply_to_message else None)
            d = m.document or (m.reply_to_message.document if m.reply_to_message else None)
            if p:
                media_list.append(InputMediaPhoto(media=p[-1].file_id))
                file_refs.append((p[-1].file_id, 'photo'))
            elif d:
                media_list.append(InputMediaDocument(media=d.file_id))
                file_refs.append((d.file_id, 'document'))

        if not hasattr(state, 'pending_fb_media'):
            state.pending_fb_media = {}

        try:
            if len(media_list) > 1:
                # Telegram does not allow inline keyboards on media groups
                await context.bot.send_media_group(chat_id=admin_id, media=media_list)
                state.pending_fb_media[group_id] = { 'media': file_refs, 'caption': final_caption, 'template': admin_text, 'feedback_str': feedback_str }
                await context.bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=kb, parse_mode=ParseMode.HTML)
            elif len(media_list) == 1:
                state.pending_fb_media[group_id] = { 'media': file_refs, 'caption': final_caption, 'template': admin_text, 'feedback_str': feedback_str }
                if file_refs[0][1] == 'photo':
                    await context.bot.send_photo(chat_id=admin_id, photo=file_refs[0][0], caption=admin_text, reply_markup=kb, parse_mode=ParseMode.HTML)
                else:
                    await context.bot.send_document(chat_id=admin_id, document=file_refs[0][0], caption=admin_text, reply_markup=kb, parse_mode=ParseMode.HTML)
            else:
                state.pending_fb_media[group_id] = { 'media': [], 'caption': final_caption, 'template': admin_text, 'feedback_str': feedback_str }
                await context.bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=kb, parse_mode=ParseMode.HTML)
                
            await msgs[0].reply_text(f"{EMOJI_DONE} <b>Your feedback has been sent to the admins for approval.</b>", parse_mode=ParseMode.HTML)
        except Exception as e:
            await msgs[0].reply_text(f"{EMOJI_WRONG} <b>Failed to send feedback:</b> {e}", parse_mode=ParseMode.HTML)

async def set_proxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import html
    uid = update.effective_user.id
    if is_banned(uid): return
    if not state.bot_operational and not is_admin_user(uid):
        await update.message.reply_text(f"{EMOJI_WRONG} <b>Bot Maintenance:</b> Offline.", parse_mode=ParseMode.HTML)
        return
    if not update.message: return
    
    proxy_line = ""
    # Check for document upload
    if update.message.document:
        doc = update.message.document
        f = await context.bot.get_file(doc.file_id)
        content = await f.download_as_bytearray()
        proxy_line = content.decode('utf-8', errors='ignore')
    elif update.message.reply_to_message and update.message.reply_to_message.document:
        doc = update.message.reply_to_message.document
        f = await context.bot.get_file(doc.file_id)
        content = await f.download_as_bytearray()
        proxy_line = content.decode('utf-8', errors='ignore')
        
    # Append text arguments if any
    text = update.message.text or update.message.caption or ""
    parts = text.split(None, 1)
    if len(parts) > 1:
        proxy_line += "\n" + parts[1].strip()
        
    if not proxy_line.strip():
        await update.message.reply_html(
            f"{EMOJI_WRONG} <b>Usage:</b> <code>/setproxy ip:port</code> or reply to a .txt file."
        )
        return

    force_save = False
    subparts = proxy_line.split(None, 1)
    if subparts[0].lower() == 'force' and len(subparts) > 1:
        force_save = True
        proxy_line = subparts[1].strip()

    from bot.utils.helpers import normalize_proxy_raw, test_proxy_connection, get_user_proxy
    
    # Split lines by newlines/spaces/commas to support multiple proxies
    raw_lines = proxy_line.replace(",", "\n").split()
    normalized_list = []
    for line in raw_lines:
        norm = normalize_proxy_raw(line.strip())
        if norm:
            normalized_list.append(norm)

    if not normalized_list:
        await update.message.reply_html(
            f"{EMOJI_WRONG} <b>Error:</b> Invalid proxy format.\nUse <code>ip:port</code> or <code>user:pass@ip:port</code>"
        )
        return

    # Append to existing proxies
    existing = get_user_proxy(uid)
    if existing:
        existing_list = [normalize_proxy_raw(l.strip()) for l in existing.split("\n") if l.strip()]
        normalized_list = existing_list + normalized_list
        # Remove duplicates while preserving order
        normalized_list = list(dict.fromkeys(normalized_list))

    if force_save:
        from bot.utils.helpers import set_user_proxy
        set_user_proxy(uid, "\n".join(normalized_list))
        preview = normalized_list[-1] if normalized_list else ""
        extra_info = f" (+{len(normalized_list)-1} more)" if len(normalized_list) > 1 else ""
        await update.message.reply_html(
            f"{EMOJI_DONE} <b>Success!</b> Proxies saved (Force Save).\n"
            f"{EMOJI_PROXY} <b>Total Proxies Loaded:</b> <code>{len(normalized_list)}</code>\n"
            f"🔍 <b>Preview:</b> <code>{html.escape(preview)}</code>{extra_info}\n"
            f"⚠️ <i>Note: Connections were not tested.</i>",
            parse_mode=ParseMode.HTML
        )
        return
        
    status_msg = await update.message.reply_html(
        f"{EMOJI_TIME} <b>Testing proxy connections...</b>"
    )
    
    import asyncio
    tasks = [test_proxy_connection(p) for p in normalized_list]
    results = await asyncio.gather(*tasks)
    
    live_proxies = []
    rotating_count = 0
    for idx, r in enumerate(results):
        if r[0]:
            p_str = normalized_list[idx]
            if r[4]: # is_rotating
                p_str += "|ROTATING"
                rotating_count += 1
            live_proxies.append(p_str)
    
    if live_proxies:
        from bot.utils.helpers import set_user_proxy
        set_user_proxy(uid, "\n".join(live_proxies))
        # Find first successful results for stats
        working = [r for r in results if r[0]]
        latency = working[0][1]
        ip = working[0][2]
        lat_str = f"{latency}ms" if isinstance(latency, int) else latency
        
        msg = (
            f"{EMOJI_DONE} <b>Success!</b> {len(live_proxies)}/{len(normalized_list)} proxies active and saved.\n"
            f"{EMOJI_PROXY} <b>IP (first working):</b> {ip}\n"
            f"⚡ <b>Latency:</b> {lat_str}\n"
        )
        if rotating_count > 0:
            msg += f'<tg-emoji emoji-id="5334904192622403796">🔄</tg-emoji> <b>Rotating Detected:</b> {rotating_count} (30 workers each)\n'
        msg += f'<tg-emoji emoji-id="5904542823167824187">🗑️</tg-emoji> <i>Use /rmproxy to clear them.</i>'
        if len(live_proxies) < len(normalized_list):
            msg += f"\n⚠️ <i>Note: {len(normalized_list) - len(live_proxies)} dead proxies were filtered out.</i>"
        await status_msg.edit_text(msg, parse_mode=ParseMode.HTML)
    else:
        errors = [r[1] for r in results if not r[0]]
        last_err = errors[0] if errors else "Connection timed out"
        await status_msg.edit_text(
            f"{EMOJI_WRONG} <b>Proxy Connection Failed!</b>\n"
            f"All {len(normalized_list)} proxies failed to connect.\n"
            f"❌ <b>Error:</b> <code>{html.escape(str(last_err))}</code>\n"
            f"⚠️ Proxies were <b>not</b> saved.\n\n"
            f"{EMOJI_BULB} <i>If you know these proxies work, bypass this check using:</i>\n"
            f"<code>/setproxy force your_proxies</code>",
            parse_mode=ParseMode.HTML
        )

async def rm_proxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_banned(uid): return
    if not state.bot_operational and not is_admin_user(uid):
        await update.message.reply_text(f"{EMOJI_WRONG} <b>Bot Maintenance:</b> Offline.", parse_mode=ParseMode.HTML)
        return
        
    from bot.utils.helpers import delete_user_proxy
    if delete_user_proxy(uid):
        await update.message.reply_html(f"{EMOJI_DONE} <b>Success:</b> Your Shopify proxy has been removed.")
    else:
        await update.message.reply_html(f"{EMOJI_WRONG} <b>Error:</b> You do not have any proxy configured.")


def luhn_checksum(card_number: str) -> bool:
    digits = [int(x) for x in card_number if x.isdigit()]
    if not digits: return False
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0

def generate_luhn_card(bin_prefix: str, length: int = 16) -> str:
    """Generates a card starting with bin_prefix to match length, valid by Luhn."""
    if len(bin_prefix) >= length:
        return bin_prefix[:length]
    
    # Fill with random digits except the last one
    card_base = bin_prefix + "".join([str(random.randint(0, 9)) for _ in range(length - len(bin_prefix) - 1)])
    
    # Find the correct check digit
    for i in range(10):
        if luhn_checksum(card_base + str(i)):
            return card_base + str(i)
    
    return card_base + "0" # Fallback, shouldn't happen

async def gen_cc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Format: /gencc 411111|12|2026|random 10
    Format: /gencc 411111 20
    """
    if not update.message or not update.message.text: return
    
    parts = update.message.text.split()
    if len(parts) < 2:
        return await update.message.reply_html(
            f"{EMOJI_CARD} <b>Usage:</b> <code>/gencc BIN [AMOUNT]</code>\n"
            f"<b>Example:</b> <code>/gencc 411111 20</code>\n"
            f"<b>Example:</b> <code>/gencc 411111|12|2026|rnd 50</code>"
        )
        
    bin_input = parts[1]
    amount = 10
    if len(parts) >= 3:
        try:
            amount = int(parts[2])
            if amount > 10000: amount = 10000
            if amount < 1: amount = 1
        except:
            amount = 10
            
    # Parse the bin input
    segments = bin_input.split('|')
    bin_base = re.sub(r'\\D', '', segments[0])
    
    if len(bin_base) < 6:
        return await update.message.reply_html(f"{EMOJI_WRONG} <b>Error:</b> BIN must be at least 6 digits.")
        
    length = 15 if bin_base.startswith('3') else 16
    
    mm = segments[1] if len(segments) > 1 and segments[1].lower() not in ['rnd', 'random', ''] else 'rnd'
    yy = segments[2] if len(segments) > 2 and segments[2].lower() not in ['rnd', 'random', ''] else 'rnd'
    cvv = segments[3] if len(segments) > 3 and segments[3].lower() not in ['rnd', 'random', ''] else 'rnd'

    cards = []
    
    for _ in range(amount):
        cc = generate_luhn_card(bin_base, length)
        
        c_mm = str(random.randint(1, 12)).zfill(2) if mm == 'rnd' else mm.zfill(2)
        
        if yy == 'rnd':
            current_year = int(str(datetime.now().year)[2:])
            c_yy = str(random.randint(current_year, current_year + 8))
        else:
            c_yy = yy[-2:] if len(yy) > 2 else yy
            
        c_cvv = "".join([str(random.randint(0, 9)) for _ in range(4 if length == 15 else 3)]) if cvv == 'rnd' else cvv
        
        cards.append(f"{cc}|{c_mm}|20{c_yy}|{c_cvv}")
        
    # Output logic
    if amount <= 20:
        res = f"{EMOJI_DONE} <b>Generated {amount} CCs from BIN {bin_base}:</b>\n\n<code>" + "\n".join(cards) + "</code>"
        await update.message.reply_html(res)
    else:
        # Save to file
        os.makedirs("Data", exist_ok=True)
        filename = f"Data/gen_{bin_base}_{int(time.time())}.txt"
        with open(filename, 'w') as f:
            f.write("\n".join(cards))
            
        try:
            with open(filename, 'rb') as doc:
                await update.message.reply_document(
                    document=doc,
                    filename=f"{bin_base}_gen_{amount}.txt",
                    caption=f"{EMOJI_DONE} <b>Generated {amount} CCs successfully!</b>",
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            await update.message.reply_html(f"{EMOJI_WRONG} <b>Error sending file:</b> {e}")
        finally:
            if os.path.exists(filename):
                try: os.remove(filename)
                except: pass


async def split_cmd(update, context):
    from telegram.constants import ParseMode
    import html
    import io
    
    doc = None
    if update.message.document:
        doc = update.message.document
    elif update.message.reply_to_message and update.message.reply_to_message.document:
        doc = update.message.reply_to_message.document

    if not doc:
        await update.message.reply_text("<b>Usage:</b> Reply to a `.txt` file with <code>/split &lt;lines_per_file&gt;</code> or attach a file with the command.\n\nExample: <code>/split 500</code>", parse_mode=ParseMode.HTML)
        return
        
    args = context.args
    if not args:
        msg_text = update.message.text or update.message.caption or ""
        msg_parts = msg_text.split()
        if len(msg_parts) > 1:
            args = msg_parts[1:]

    try:
        lines_per_file = int(args[0])
        if lines_per_file <= 0:
            raise ValueError()
    except (IndexError, ValueError, TypeError):
        await update.message.reply_text("<b>Error:</b> Please provide a valid number of lines. Example: <code>/split 500</code>", parse_mode=ParseMode.HTML)
        return

    if not doc.file_name.lower().endswith('.txt'):
        await update.message.reply_text("<b>Error:</b> Please provide a .txt file.", parse_mode=ParseMode.HTML)
        return
        
    if doc.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("<b>Error:</b> File is too large.", parse_mode=ParseMode.HTML)
        return

    status_msg = await update.message.reply_text("<i>Downloading file...</i>", parse_mode=ParseMode.HTML)
    
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        text = file_bytes.decode('utf-8', errors='ignore')
        lines = text.splitlines()
        
        if not lines:
            await status_msg.edit_text("<b>Error:</b> File is empty.", parse_mode=ParseMode.HTML)
            return
            
        total_lines = len(lines)
        if total_lines <= lines_per_file:
            await status_msg.edit_text("<b>Error:</b> File has fewer lines than the split amount.", parse_mode=ParseMode.HTML)
            return
            
        await status_msg.edit_text(f"<i>Splitting {total_lines} lines into files of {lines_per_file} lines each...</i>", parse_mode=ParseMode.HTML)
        
        import os
        base_name, _ = os.path.splitext(doc.file_name)
        chunks = [lines[i:i + lines_per_file] for i in range(0, total_lines, lines_per_file)]
        
        for idx, chunk in enumerate(chunks, 1):
            chunk_text = "\n".join(chunk)
            bio = io.BytesIO(chunk_text.encode('utf-8'))
            bio.name = f"{base_name}_part_{idx}.txt"
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=bio,
                filename=bio.name,
                caption=f"<b>Part {idx}/{len(chunks)}</b> ({len(chunk)} lines)",
                parse_mode=ParseMode.HTML,
                reply_to_message_id=update.message.message_id
            )
            import asyncio
            await asyncio.sleep(1.0)
            
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"<b>Error:</b> {html.escape(str(e))}", parse_mode=ParseMode.HTML)


async def parse_cmd(update, context):
    from telegram.constants import ParseMode
    import html
    import io
    import re
    
    doc = None
    if update.message.document:
        doc = update.message.document
    elif update.message.reply_to_message and update.message.reply_to_message.document:
        doc = update.message.reply_to_message.document

    if not doc:
        await update.message.reply_text("<b>Usage:</b> Reply to a `.txt` file with <code>/parse</code> or attach a file with the command.", parse_mode=ParseMode.HTML)
        return
        
    if not doc.file_name.lower().endswith('.txt'):
        await update.message.reply_text("<b>Error:</b> Please provide a .txt file.", parse_mode=ParseMode.HTML)
        return
        
    if doc.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("<b>Error:</b> File is too large.", parse_mode=ParseMode.HTML)
        return

    status_msg = await update.message.reply_text("<i>Downloading and parsing file...</i>", parse_mode=ParseMode.HTML)
    
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        text = file_bytes.decode('utf-8', errors='ignore')
        
        parsed_cards = []
        for line in text.splitlines():
            # Try specific format first
            match = re.search(r'^(\d{15,16}).*?CVV:(\d{3,4})EXPIRE:(\d{2})/(\d{2})', line, re.IGNORECASE)
            if match:
                cc = match.group(1)
                cvv = match.group(2)
                mm = match.group(3)
                yy = match.group(4)
                if len(yy) == 2: yy = '20' + yy
                parsed_cards.append(f"{cc}|{mm}|{yy}|{cvv}")
                continue
                
            # Generic extractor as fallback
            gen_match = re.search(r'(\d{15,16})[\s|:/]+(\d{1,2})[\s|:/]+(\d{2,4})[\s|:/]+(\d{3,4})', line)
            if gen_match:
                cc, mm, yy, cvv = gen_match.groups()
                if len(mm) == 1: mm = '0' + mm
                if len(yy) == 2: yy = '20' + yy
                parsed_cards.append(f"{cc}|{mm}|{yy}|{cvv}")
                
        if not parsed_cards:
            await status_msg.edit_text("<b>Error:</b> Could not find any valid credit cards in that file.", parse_mode=ParseMode.HTML)
            return
            
        # Deduplicate
        seen = set()
        unique_cards = []
        for c in parsed_cards:
            if c not in seen:
                seen.add(c)
                unique_cards.append(c)
                
        output_text = "\n".join(unique_cards)
        bio = io.BytesIO(output_text.encode('utf-8'))
        import os
        base_name, _ = os.path.splitext(doc.file_name)
        bio.name = f"{base_name}_parsed.txt"
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=bio,
            filename=bio.name,
            caption=f"<b>Parsed {len(unique_cards)} unique cards!</b>",
            parse_mode=ParseMode.HTML,
            reply_to_message_id=update.message.message_id
        )
        await status_msg.delete()
        
    except Exception as e:
        await status_msg.edit_text(f"<b>Error:</b> {html.escape(str(e))}", parse_mode=ParseMode.HTML)


async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.utils.db import db_get_leaderboard
    import html

    board = db_get_leaderboard(10)
    if not board:
        await update.message.reply_text("Leaderboard is empty!")
        return

    text = "🏆 <b>Top Hitters Leaderboard</b> 🏆\n\n"
    
    E_BOSS = "<tg-emoji emoji-id='6089102266571168199'>👑</tg-emoji>"
    E_TOP = "<tg-emoji emoji-id='6089306715604392889'>🔝</tg-emoji>"
    E_MEDAL = "<tg-emoji emoji-id='6089185885289454318'>🥇</tg-emoji>"
    E_ADMIN = "<tg-emoji emoji-id='5406711411541823609'>👨‍💻</tg-emoji>"

    admin_id = "8171100881"

    for idx, row in enumerate(board):
        uid = str(row['user_id'])
        hits = row['total_hits']

        try:
            chat = await context.bot.get_chat(int(uid))
            name = chat.first_name if chat.first_name else (chat.username if chat.username else f"User {uid}")
        except:
            name = f"User {uid}"
        
        name = html.escape(name)
        
        if uid == admin_id:
            emoji = E_ADMIN
        elif idx == 0:
            emoji = E_BOSS
        elif idx == 1:
            emoji = E_TOP
        elif idx == 2:
            emoji = E_MEDAL
        else:
            emoji = "<tg-emoji emoji-id='6181722102438042117'>🔹</tg-emoji>"

        text += f"{emoji} <b>{name}</b> ⤏ {hits:,} Hits\n"

    await update.message.reply_text(text, parse_mode='HTML')
