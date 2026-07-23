import asyncio
class DummyEngine:
    accounts = []
    proxies = []
    _accounts_lock = asyncio.Lock()
    def check_session(self, *args, **kwargs): return False, None, None
    def _save_accounts(self, *args, **kwargs): pass
    def _load_accounts(self, *args, **kwargs): return []
    def _load_proxies(self, *args, **kwargs): return []
braintree_engine = DummyEngine()
frbt_engine = DummyEngine()
import os
import time
import asyncio
import traceback
import html
import logging
import re
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, LinkPreviewOptions, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.core.config import *
from bot.core import state
from bot.core.state import _io_lock

from bot.utils.helpers import btn, is_admin_user, load_json_dict, save_json, normalize_proxy_line, get_random_proxy
from bot.utils.usage import is_premium, remove_premium
from bot.hits_sender import get_today_count

logger = logging.getLogger(__name__)


def _is_admin_action(callback_data: str) -> bool:
    return callback_data.startswith("adm_") or callback_data in {
        "admin_menu",
        "stop_menu",
    }

def admin_menu_logic():
    text = (
        f"{EMOJI_TOOLS} <b>Admin Control Center</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<b>Available Commands:</b>\n"
        f"📢 <code>/broadcast</code> - Message all\n"
        f"📊 <code>/status</code> - System health\n"
        f"🚫 <code>/ban</code> | <code>/unban</code> - Ban control\n"
        f"💎 <code>/rmprem</code> | <code>/keysdays</code> | <code>/preusers</code>\n"
        f"💰 <code>/addcredits</code> | <code>/distribute</code>\n"
        f"🎟 <code>/gen</code> [prem/credit] [val] - Gen code\n"
        f"⏳ <code>/setdelay</code> | 📊 <code>/setlimit</code> | <code>/setfreelimit</code>\n"
        f"🛍️ <code>/addsite</code> | <code>/delsite</code> | <code>/sites</code>\n\n"
        f"<i>Use the buttons below for interactive management.</i>"
    )
    kb = [
        [btn("Bot Stats", callback_data="adm_stats", icon_id=ID_CHART), btn("Settings", callback_data="adm_settings_menu", icon_id=ID_TOOLS)],
        [btn("User Manager", callback_data="adm_users_menu", icon_id=ID_PROFILE), btn("Broadcast", callback_data="adm_bc", icon_id=ID_BROADCAST)],
        [btn("Credit Codes", callback_data="adm_cred_codes", icon_id=ID_TIME), btn("Premium Codes", callback_data="adm_prem_codes", icon_id=ID_RANK)],
        [btn("Stop Controls", callback_data="stop_menu", icon_id=ID_STOP), btn("Error Console", callback_data="adm_errors", icon_id=ID_DEAD)],
        [btn("Global Proxy Pool", callback_data="adm_proxy_pool_menu", icon_id="6181682949516173646")],
        [btn("SYSTEM: LIVE" if state.bot_operational else "MAINTENANCE", callback_data="adm_toggle_op", style="success" if state.bot_operational else "danger", icon_id=ID_STOP)],
        [btn("Clear All Premium", callback_data="adm_clear_prem", style="danger", icon_id=ID_TRASH)],
        [btn("Back to Main Dashboard", callback_data="start_menu", icon_id=ID_BC)]
    ]
    return text, kb


def _admin_back_kb():
    return InlineKeyboardMarkup([[btn("Back to Admin", callback_data="admin_menu", icon_id=ID_BC)]])

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, override_data=None):
    def _admin_back_kb():
        return InlineKeyboardMarkup([[btn("Back", callback_data="admin_menu", icon_id=ID_BC)]])

    query = update.callback_query
    if not query: return
    uid = query.from_user.id
    data = override_data or query.data

    if not data:
        await query.answer("Invalid action.", show_alert=True)
        return

    if query.message and query.message.reply_to_message:
        if uid != query.message.reply_to_message.from_user.id and not is_admin_user(uid):
            await query.answer("This button is not for you.", show_alert=True)
            return

    if _is_admin_action(data) and not is_admin_user(uid):
        await query.answer("Admin access required.", show_alert=True)
        return
    
    if not state.bot_operational and not is_admin_user(uid):
        await query.answer("Bot Maintenance: Offline.", show_alert=True)
        return
         
    if override_data is None and data != "fsub_check_joined":
        try:
            await query.answer()
        except Exception as exc:
            logger.debug("Callback answer failed uid=%s data=%s err=%s", uid, data, exc)
    
    async def nav_reply(text, reply_markup=None):
        try:
            if query.message.animation or query.message.photo or query.message.video or query.message.document:
                return await query.edit_message_caption(caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else:
                return await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
        except Exception as e:
            err_str = str(e)
            if "Message is not modified" in err_str:
                return
            try:
                return await context.bot.send_message(chat_id=uid, text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            except Exception as exc:
                logger.warning("Fallback nav send failed uid=%s data=%s err=%s", uid, data, exc)
                # If even fallback fails (e.g. invalid markup), send without markup as last resort
                return await context.bot.send_message(chat_id=uid, text=text, parse_mode=ParseMode.HTML)


    if data in ("chk_help", "shopify_help"):
        text = (
            "<tg-emoji emoji-id='6026218958900695642'>💎</tg-emoji> 𝗦𝗵𝗼𝗽𝗶𝗳𝘆 𝗚𝗮𝘁𝗲𝘄𝗮𝘆\n\n"
            "<tg-emoji emoji-id='6026367225466720832'>🌩</tg-emoji> 𝗦𝗶𝗻𝗴𝗹𝗲 𝗖𝗵𝗸 - <code>/sh card|mm|yy|cvv</code>\n\n"
            "<tg-emoji emoji-id='6026367225466720832'>🌩</tg-emoji> 𝗠𝗮𝘀𝘀/𝗙𝗶𝗹𝗲 𝗖𝗵𝗸 - Reply To .txt With <code>/msh</code>"
        )
        kb = [
            [btn("Manage Proxy", callback_data="shopify_proxy_menu", icon_id=ID_TOOLS)],
            [btn("Back", callback_data="start_menu", icon_id=ID_BC)]
        ]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "shopify_proxy_menu":
        from bot.utils.helpers import get_user_proxy
        from bot.utils.db import db_get_use_pool
        use_pool = db_get_use_pool(uid)
        user_proxy = get_user_proxy(uid)
        
        if use_pool:
            proxy_disp = "<i>Using Global Proxy Pool</i>"
        elif user_proxy:
            proxy_lines = [p.strip() for p in user_proxy.split("\n") if p.strip()]
            if len(proxy_lines) > 1:
                proxy_disp = f"<code>{len(proxy_lines)} proxies loaded</code>\n🔍 <b>Preview:</b> <code>{html.escape(proxy_lines[0])}</code>"
            else:
                proxy_disp = f"<code>{html.escape(user_proxy)}</code>"
        else:
            proxy_disp = "<i>None Configured</i>"
            
        text = (
            f"{EMOJI_TOOLS} <b>Shopify Proxy Settings</b>\n\n"
            f"Shopify gateway requires you to set your own proxy to run checks.\n\n"
            f"{EMOJI_CURRENT_PROXY} <b>Current Proxy:</b> {proxy_disp}\n\n"
            f"{EMOJI_BULB} <b>To Set/Update:</b>\n"
            f"Send <code>/setproxy ip:port</code> or <code>/setproxy ip:port:user:pass</code> in chat.\n"
            f"Supports SOCKS and HTTP proxies."
        )
        kb = []
        if use_pool:
            # When ON, show green button to toggle OFF
            kb.append([btn("Use Proxy Pool (ON)", callback_data="toggle_proxy_pool_off", style="success", icon_id="6181682949516173646")])
        else:
            # When OFF, show red button to toggle ON
            kb.append([btn("Use Proxy Pool (OFF)", callback_data="toggle_proxy_pool_on", style="danger", icon_id="6181682949516173646")])
            
        if user_proxy and not use_pool:
            kb.append([
                btn("Test Proxy", callback_data="shopify_proxy_test", style="success", icon_id=ID_LIVE),
                btn("Remove Proxy", callback_data="shopify_proxy_remove", style="danger", icon_id=ID_STOP)
            ])
        kb.append([btn("Back", callback_data="shopify_help", icon_id=ID_BC)])
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "shopify_proxy_test":
        from bot.utils.helpers import get_user_proxy, test_proxy_connection, delete_user_proxy
        user_proxy = get_user_proxy(uid)
        if not user_proxy:
            await query.answer("No proxy configured!", show_alert=True)
            return
            
        try:
            await query.answer("Testing proxy connections in parallel... please wait.", show_alert=False)
        except:
            pass
            
        proxy_list = [p.strip() for p in user_proxy.split("\n") if p.strip()]
        
        # Display progress status
        proxy_disp = f"<code>{len(proxy_list)} proxies loaded</code>" if len(proxy_list) > 1 else f"<code>{html.escape(user_proxy)}</code>"
        text_updating = (
            f"{EMOJI_TOOLS} <b>Shopify Proxy Settings</b>\n\n"
            f"Shopify gateway requires you to set your own proxy to run checks.\n\n"
            f"{EMOJI_CURRENT_PROXY} <b>Current Proxy:</b> {proxy_disp}\n"
            f"🔄 <b>Testing connections in parallel...</b>\n\n"
            f"{EMOJI_BULB} <b>To Set/Update:</b>\n"
            f"Send <code>/setproxy ip:port</code> or <code>/setproxy ip:port:user:pass</code> in chat.\n"
            f"Supports SOCKS and HTTP proxies."
        )
        try:
            await query.edit_message_text(text_updating, reply_markup=query.message.reply_markup, parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
        except:
            pass
        
        # Test in batches and update UI so user doesn't think it's frozen
        results = []
        batch_size = 5
        for i in range(0, len(proxy_list), batch_size):
            batch = proxy_list[i:i+batch_size]
            tasks = [test_proxy_connection(p) for p in batch]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            
            # Update progress UI
            try:
                prog_text = text_updating.replace(
                    "🔄 <b>Testing connections in parallel...</b>", 
                    f"🔄 <b>Testing connections: {len(results)}/{len(proxy_list)}...</b>"
                )
                await query.message.edit_text(prog_text, reply_markup=query.message.reply_markup, parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
            except:
                pass
                
        success_count = sum(1 for r in results if r[0])
        success = success_count > 0
        
        kb = []
        if success:
            working = [r for r in results if r[0]]
            latency = working[0][1]
            ip = working[0][2]
            lat_str = f"{latency}ms" if isinstance(latency, int) else latency
            
            # Save explicit working proxies (which include the proper scheme like socks5://)
            live_proxies = [r[3] for r in results if r[0]]
            from bot.utils.helpers import set_user_proxy
            set_user_proxy(uid, "\n".join(live_proxies))
            user_proxy = "\n".join(live_proxies)
            
            status_text = f"🟢 <b>Active</b> ({success_count}/{len(proxy_list)} working | Ping: {lat_str} | IP: {ip})"
            if len(live_proxies) < len(proxy_list):
                status_text += f"\n⚠️ <i>Filtered out and removed {len(proxy_list) - len(live_proxies)} dead proxies.</i>"
            
            kb.append([
                btn("Test Again", callback_data="shopify_proxy_test", style="success", icon_id=ID_LIVE),
                btn("Remove Proxy", callback_data="shopify_proxy_remove", style="danger", icon_id=ID_STOP)
            ])
        else:
            # Auto-remove the dead proxy
            from bot.utils.helpers import delete_user_proxy
            delete_user_proxy(uid)
            errors = [r[1] for r in results if not r[0]]
            last_err = errors[0] if errors else "Connection timed out"
            status_text = f"🔴 <b>All Dead & Removed</b> (Error: {last_err})"
            user_proxy = None
            
            kb.append([
                btn("Remove Proxy", callback_data="shopify_proxy_remove", style="danger", icon_id=ID_STOP)
            ])
            
        # Re-build settings view
        if user_proxy:
            proxy_lines = [p.strip() for p in user_proxy.split("\n") if p.strip()]
            if len(proxy_lines) > 1:
                proxy_disp = f"<code>{len(proxy_lines)} proxies loaded</code>\n🔍 <b>Preview:</b> <code>{html.escape(proxy_lines[0])}</code>"
            else:
                proxy_disp = f"<code>{html.escape(user_proxy)}</code>"
        else:
            proxy_disp = "<i>None Configured</i>"
            
        text = (
            f"{EMOJI_TOOLS} <b>Shopify Proxy Settings</b>\n\n"
            f"Shopify gateway requires you to set your own proxy to run checks.\n\n"
            f"{EMOJI_CURRENT_PROXY} <b>Current Proxy:</b> {proxy_disp}\n"
            f"⚡ <b>Connection Status:</b>\n{status_text}\n\n"
            f"{EMOJI_BULB} <b>To Set/Update:</b>\n"
            f"Send <code>/setproxy ip:port</code> or <code>/setproxy ip:port:user:pass</code> in chat.\n"
            f"Supports SOCKS and HTTP proxies."
        )
        kb.append([btn("Back", callback_data="shopify_help", icon_id=ID_BC)])
        
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
        except Exception:
            try:
                await context.bot.send_message(chat_id=uid, text=f"{EMOJI_PROXY} <b>Proxy Test Result:</b>\n{status_text}", parse_mode=ParseMode.HTML)
            except:
                pass

    elif data == "shopify_proxy_remove":
        from bot.utils.helpers import delete_user_proxy, get_user_proxy
        delete_user_proxy(uid)
        try:
            await query.answer("Proxy removed successfully!", show_alert=True)
        except:
            pass
        # Refresh the menu
        proxy_disp = "<i>None Configured</i>"
        text = (
            f"{EMOJI_TOOLS} <b>Shopify Proxy Settings</b>\n\n"
            f"Shopify gateway requires you to set your own proxy to run checks.\n\n"
            f"{EMOJI_CURRENT_PROXY} <b>Current Proxy:</b> {proxy_disp}\n\n"
            f"{EMOJI_BULB} <b>To Set/Update:</b>\n"
            f"Send <code>/setproxy ip:port</code> or <code>/setproxy ip:port:user:pass</code> in chat.\n"
            f"Supports SOCKS and HTTP proxies."
        )
        kb = [[btn("Back", callback_data="shopify_help", icon_id=ID_BC)]]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))
        
    elif data == "start_menu":
        from bot.handlers.user import start_logic
        text, kb = start_logic(query.from_user)
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "ref_menu":
        from bot.handlers.user import ref_menu_cmd
        await ref_menu_cmd(update, context)

    elif data == "check_pending_cc":
        uid = update.effective_user.id
        from bot.core.state import user_pending_cards
        cards = user_pending_cards.get(uid, [])
        if not cards:
            await query.answer("No pending cards found or session expired.", show_alert=True)
            return
        await query.answer("Starting Shopify check...")
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except:
            pass
        wrapped_update = update
        if not getattr(update, "message", None) and query.message:
            class UpdateWrapper:
                def __init__(self, original_update, message):
                    self._update = original_update
                    self.message = message
                def __getattr__(self, name):
                    return getattr(self._update, name)
            wrapped_update = UpdateWrapper(update, query.message)
        user_pending_cards.pop(uid, None)
        if len(cards) == 1:
            from bot.handlers.shopify_cmds import shopify_handler
            await shopify_handler(wrapped_update, context, manual_card=cards[0])
        else:
            from bot.handlers.shopify_cmds import shopify_doc_handler
            await shopify_doc_handler(wrapped_update, context, manual_cards=cards)
            
        # Delete the original "CC/TXT DETECTED" message to keep chat clean
        try:
            await query.message.delete()
        except:
            pass


    elif data == "profile":
        from bot.utils.usage import get_all_credits_dict
        credits_data = get_all_credits_dict()
        user_credits = credits_data.get(str(uid), 0)

        rank = f"Premium {EMOJI_RANK}" if is_premium(uid) else "Free User 👤"
        if is_admin_user(uid): rank = "Admin 🛠️"
        
        text = (
            f"{EMOJI_PROFILE} <b>User Profile</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"{EMOJI_ID} <b>ID:</b> <code>{uid}</code>\n"
            f"{EMOJI_RANK} <b>Rank:</b> {rank}\n"
            f"{EMOJI_CREDITS} <b>Credits:</b> <code>{user_credits}</code>\n"
        )

        kb = [[btn("Back", callback_data="start_menu", icon_id=ID_BC)]]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "admin_menu":
        if not is_admin_user(uid): return
        text, kb = admin_menu_logic()
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))


    elif data == "stop_menu":
        if not is_admin_user(uid): return
        kb = []
        status_s = "STOPPED" if state.global_stop_signal else "LIVE"
        status_m = "STOPPED" if state.global_mass_stop_signal else "LIVE"
        style_s = "danger" if state.global_stop_signal else "success"
        style_m = "danger" if state.global_mass_stop_signal else "success"
        kb.append([btn(f"Toggle Single ({status_s})", callback_data="adm_tog_single", style=style_s)])
        kb.append([btn(f"Toggle Mass ({status_m})", callback_data="adm_tog_mass", style=style_m)])
        kb.append([btn("Force Clear Locks", callback_data="adm_clear_locks", style="danger", icon_id=ID_DEAD)])
        kb.append([btn("RESUME ALL", callback_data="adm_resume_all", style="success", icon_id=ID_LIVE)])
        kb.append([btn("View Active FRBT Accs", callback_data="adm_sel_frbt_acc_menu", icon_id=ID_LIVE)])
        kb.append([btn("Back", callback_data="admin_menu", icon_id=ID_BC)])
        msg = f"{EMOJI_DEAD} <b>Admin Stop Controls</b>\n\nManage the persistent heartbeat of all bot modules.\nUse <b>Force Clear Locks</b> if users are stuck in 'Wait!' state."
        await nav_reply(msg, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_stats":
        from bot.utils.usage import get_all_credits_dict
        credits_data = get_all_credits_dict()

        text = (
            f"{EMOJI_CHART} <b>Global Bot Statistics</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"🔥 <b>Today's Hits:</b> <code>{get_today_count()}</code>\n"
            f"🌍 <b>Total Checks:</b> <code>{state.bot_stats['total_checks']}</code>\n"
            f"💎 <b>Total Lives:</b> <code>{state.bot_stats['total_live']}</code>\n"
            f"👤 <b>Total Users:</b> <code>{len(credits_data)}</code>\n"
        )
        kb = [[btn("Back to Admin", callback_data="admin_menu", icon_id=ID_BC)]]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_toggle_op":
        if not is_admin_user(uid): return
        try:
            state.bot_operational = not state.bot_operational
            if not state.bot_operational:
                state.global_stop_signal = True
                state.global_mass_stop_signal = True
            else:
                state.global_stop_signal = False
                state.global_mass_stop_signal = False
            state.save_toggles()
                
            status_text = "ONLINE" if state.bot_operational else "OFFLINE (Maintenance Mode)"
            await query.answer(f"Bot Status: {status_text}", show_alert=True)
            return await button_handler(update, context, override_data="admin_menu")
        except Exception as e:
            state.errors.append(f"Toggle Error: {str(e)}")
            await query.answer("Error toggling maintenance.", show_alert=True)
            return

    elif data == "adm_resume_all":
        if not is_admin_user(uid): return
        state.global_stop_signal = False
        state.global_mass_stop_signal = False
        state.save_toggles()
        await query.answer("All modules resumed.", show_alert=True)
        await button_handler(update, context, override_data="stop_menu")

    elif data == "adm_clear_locks":
        if not is_admin_user(uid): return
        state.active_checks.clear()
        await query.answer("All active check locks forcibly cleared!", show_alert=True)
        await button_handler(update, context, override_data="stop_menu")

    elif data == "adm_tog_single":
        if not is_admin_user(uid): return
        state.global_stop_signal = not state.global_stop_signal
        state.save_toggles()
        await query.answer(f"Checks: {'STOPPED' if state.global_stop_signal else 'LIVE'}", show_alert=True)
        await button_handler(update, context, override_data="stop_menu")

    elif data == "adm_tog_mass":
        if not is_admin_user(uid): return
        state.global_mass_stop_signal = not state.global_mass_stop_signal
        state.save_toggles()
        await query.answer(f"Mass checks: {'STOPPED' if state.global_mass_stop_signal else 'LIVE'}", show_alert=True)
        await button_handler(update, context, override_data="stop_menu")
    
    elif data == "adm_cred_codes":
        if not is_admin_user(uid): return
        from bot.utils.db import db_get_all_codes
        codes = db_get_all_codes()
        cred_codes = [k for k,v in codes.items() if isinstance(v, dict) and v.get("type") == "credits"]
        msg = f"{EMOJI_RANK} <b>Credit Codes:</b> {len(cred_codes)}\n\nUse <code>/gen credits [value]</code>"
        kb = [[btn("Back", callback_data="admin_menu", icon_id=ID_BC)]]
        await nav_reply(msg, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_prem_codes":
        if not is_admin_user(uid): return
        from bot.utils.db import db_get_all_codes
        codes = db_get_all_codes()
        prem_codes = [k for k,v in codes.items() if isinstance(v, dict) and v.get("type") == "premium"]
        msg = f"{EMOJI_RANK} <b>Premium Codes:</b> {len(prem_codes)}\n\nUse <code>/gen premium [days]</code>"
        kb = [[btn("Back", callback_data="admin_menu", icon_id=ID_BC)]]
        await nav_reply(msg, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_shopify_sites":
        if not is_admin_user(uid): return
        from bot.handlers.admin import load_sites_raw
        sites = load_sites_raw()
        preview = "\n".join(f"• <code>{html.escape(s)}</code>" for s in sites[:10]) if sites else "No Shopify sites loaded."
        text = (
            f"{EMOJI_GATE} <b>Shopify Sites Manager</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"Loaded: <code>{len(sites)}</code> sites\n"
            f"{preview}\n\n"
            f"Commands:\n"
            f"• <code>/addsite url</code>\n"
            f"• <code>/delsite url</code>"
        )
        kb = [
            [btn("Test & Clean Sites", callback_data="adm_test_shopify_sites", icon_id=ID_TIME)],
            [btn("Back to Shopify Settings", callback_data="adm_shopify_settings", icon_id=ID_BC)]
        ]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_shopify_settings":
        if not is_admin_user(uid): return
        from bot.handlers.admin import load_sites_raw
        sites = load_sites_raw()
        status_mass = "STOPPED" if state.global_mass_stop_signal or state.shopify_stop_signal else "LIVE"
        sh_limit = bot_settings.get('shopify_mass_daily_limit', bot_settings.get('mass_daily_prem', 1000))
        is_blocked = bot_settings.get("group_block_free_sh", False)
        tier = "prem" if is_premium(uid) else "free"
        delay_val = bot_settings.get(f"shopify_mass_delay_{tier}", 0.0)
        text = (
            f"{EMOJI_SHOPIFY} <b>Shopify Gateway Settings</b>\n\n"
            f"Loaded Sites: <code>{len(sites)}</code>\n"
            f"Mass Limit: <code>{sh_limit}</code>\n"
            f"Mass Delay: <code>{delay_val}s</code>\n"
            f"Gateway Stop: <code>{status_mass}</code>\n"
            f"Block Free Users: <code>{'ON' if is_blocked else 'OFF'}</code>\n\n"
            f"Edit values in <code>settings.json</code> and press Reload All Data."
        )
        kb = [
            [btn("Manage Shopify Sites", callback_data="adm_shopify_sites", icon_id=ID_GATE)],
            [btn(f"Block Free: {'ON' if is_blocked else 'OFF'}", callback_data="adm_shopify_toggle_free", icon_id=ID_DEAD if is_blocked else ID_LIVE)],
            [btn(f"Toggle Stop ({status_mass})", callback_data="adm_shopify_toggle_stop", style="danger" if (state.global_mass_stop_signal or state.shopify_stop_signal) else "success", icon_id=ID_STOP)],
            [btn("Back to Settings", callback_data="adm_settings_menu", icon_id=ID_BC)]
        ]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_shopify_toggle_free":
        if not is_admin_user(uid): return
        bot_settings["group_block_free_sh"] = not bot_settings.get("group_block_free_sh", False)
        save_json(SETTINGS_FILE, bot_settings)
        await query.answer(f"Block Free Shopify: {'ON' if bot_settings['group_block_free_sh'] else 'OFF'}", show_alert=True)
        await button_handler(update, context, override_data="adm_shopify_settings")


    elif data == "adm_shopify_toggle_stop":
        if not is_admin_user(uid): return
        state.shopify_stop_signal = not state.shopify_stop_signal
        state.save_toggles()
        await query.answer(f"Shopify mass: {'STOPPED' if state.shopify_stop_signal else 'LIVE'}", show_alert=True)
        await button_handler(update, context, override_data="adm_shopify_settings")

    elif data == "adm_test_shopify_sites":
        if not is_admin_user(uid): return
        from bot.handlers.admin import load_sites_raw, test_single_site_api, save_sites_raw
        sites = load_sites_raw()
        if not sites:
            await query.answer("No Shopify sites to check.", show_alert=True)
            return
        from bot.utils.helpers import get_user_proxy
        user_proxy = get_user_proxy(uid)
        if user_proxy:
            proxies = [p.strip() for p in user_proxy.split("\n") if p.strip()]
        else:
            proxies = []
        if not proxies:
            await query.answer("No proxy configured. Please set your proxy first.", show_alert=True)
            return


            
        try: await query.answer("Checking Shopify sites pool...")
        except: pass
        
        status_msg = await query.edit_message_text(f"{EMOJI_TIME} <b>Checking {len(sites)} Shopify sites...</b>", parse_mode=ParseMode.HTML)
        
        alive_sites, dead_sites, unknown_sites = [], [], []
        import random
        batch_size = 10
        
        for i in range(0, len(sites), batch_size):
            batch = sites[i:i + batch_size]
            tasks = [test_single_site_api(s, random.choice(proxies)) for s in batch]
            results = await asyncio.gather(*tasks)
            for res in results:
                if res['status'] == 'alive':
                    alive_sites.append(res['site'])
                elif res['status'] == 'dead':
                    dead_sites.append(res['site'])
                else:
                    unknown_sites.append(res['site'])
                    
            progress_text = (
                f"⏳ <b>Checking Shopify Sites Pool</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔄 <b>Progress:</b> <code>{min(i + batch_size, len(sites))}/{len(sites)}</code>\n"
                f"🟢 <b>Alive:</b> <code>{len(alive_sites)}</code>\n"
                f"🔴 <b>Dead:</b> <code>{len(dead_sites)}</code>\n"
                f"⚠️ <b>API Error:</b> <code>{len(unknown_sites)}</code>"
            )
            try: await status_msg.edit_text(progress_text, parse_mode=ParseMode.HTML)
            except: pass
            
        summary = (
            f"{EMOJI_DONE} <b>Site Check Completed</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Alive:</b> <code>{len(alive_sites)}</code>\n"
            f"🔴 <b>Dead:</b> <code>{len(dead_sites)}</code>\n"
            f"⚠️ <b>API Error:</b> <code>{len(unknown_sites)}</code>\n\n"
            f"<i>Sites list was not modified.</i>"
        )
        kb = [[btn("Back to Sites", callback_data="adm_shopify_sites", icon_id=ID_BC)]]
        await status_msg.edit_text(summary, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)


    elif data == "adm_errors":
        if not is_admin_user(uid): return
        recent = state.errors[-10:] if state.errors else []
        body = "\n".join([f"• <code>{html.escape(str(e))}</code>" for e in recent]) or "No recent errors logged."
        text = (
            f"{EMOJI_DEAD} <b>System Error Console</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"{body}\n\n"
            f"<b>Health Status:</b>\n"
            f"• Stats: {'✅' if os.path.exists(STATS_FILE) else '❌'}\n"
            f"• Settings: {'✅' if os.path.exists(SETTINGS_FILE) else '❌'}\n"
            f"• Accounts: {'✅' if os.path.exists(ACCOUNTS_FILE) else '❌'}"
        )
        kb = [[btn("Clear Logs", callback_data="adm_clear_errors", icon_id=ID_DEAD)], [btn("Back", callback_data="admin_menu", icon_id=ID_BC)]]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_clear_errors":
        if not is_admin_user(uid): return
        state.errors.clear()
        await query.answer("Logs cleared.", show_alert=True)
        await button_handler(update, context, override_data="adm_errors")

    elif data == "adm_clear_prem":
        if not is_admin_user(uid): return
        from bot.utils.usage import get_all_premium_dict, remove_premium
        users = get_all_premium_dict()
        count = 0
        for u in list(users.keys()):
            remove_premium(u)
            count += 1
        await query.answer(f"Cleared premium from {count} users.", show_alert=True)
        await button_handler(update, context, override_data="admin_menu")

    elif data.startswith("fb_appr_") or data.startswith("fb_rej_"):
        if not is_admin_user(uid): return
        action = "Approved" if data.startswith("fb_appr_") else "Rejected"
        parts = data.split("_")
        target_uid = parts[2]
        group_id = parts[3] if len(parts) > 3 else None
        
        try:
            original_text = query.message.caption_html or query.message.text_html or ""
            import re
            # Strip everything from the start up to the end of the "Feedback" header line
            clean_text = re.sub(r'^.*?<b>\s*𝗙𝗲𝗲𝗱𝗯𝗮𝗰𝗸\s*</b>\n*┣\s*', '', original_text, flags=re.DOTALL | re.IGNORECASE).strip()
            
            # Remove the "Thanks for using" footer
            clean_text = re.sub(r'\n*┣?\s*<[^>]+>[^<]+</[^>]+>\s*<b>\s*𝗧𝗵𝗮𝗻𝗸𝘀 𝗳𝗼𝗿 𝘂𝘀𝗶𝗻𝗴.*$', '', clean_text, flags=re.DOTALL | re.IGNORECASE).strip()
            
            # Convert PTB's span tags for custom emojis back to Telegram's native tg-emoji tags
            clean_text = re.sub(r'<span[^>]*data-(?:custom-)?emoji-id="([^"]+)"[^>]*>(.*?)</span>', r'<tg-emoji emoji-id="\1">\2</tg-emoji>', clean_text)
            
            await query.edit_message_reply_markup(reply_markup=None)
        except: pass

        if action == "Approved":
            import bot.core.config as config
            MAIN_CHANNEL_ID = getattr(config, 'MAIN_CHANNEL_ID', getattr(config, 'MAIN_GROUP_ID', None))
            
            
            try:
                original_text = query.message.caption_html or query.message.text_html or ""
                
                fb_data = None
                if group_id:
                    fb_data = getattr(state, 'pending_fb_media', {}).get(group_id)
                else:
                    fb_data = getattr(state, 'pending_fb_media', {}).get(int(target_uid))

                # Post the clean feedback to the channel without the admin header
                final_post_text = fb_data.get('caption', clean_text) if fb_data else clean_text

                if fb_data and len(fb_data['media']) > 1:
                    from telegram import InputMediaPhoto, InputMediaDocument
                    media_list = []
                    for idx, (fid, mtype) in enumerate(fb_data['media']):
                        cap = final_post_text if idx == 0 else ""
                        if mtype == 'photo':
                            media_list.append(InputMediaPhoto(media=fid, caption=cap, parse_mode=ParseMode.HTML))
                        else:
                            media_list.append(InputMediaDocument(media=fid, caption=cap, parse_mode=ParseMode.HTML))
                    
                    sent_msgs = await context.bot.send_media_group(chat_id=MAIN_CHANNEL_ID, media=media_list)
                    copied_msg = sent_msgs[0]
                elif fb_data and len(fb_data['media']) == 1:
                    fid, mtype = fb_data['media'][0]
                    if mtype == 'photo':
                        copied_msg = await context.bot.send_photo(chat_id=MAIN_CHANNEL_ID, photo=fid, caption=final_post_text, parse_mode=ParseMode.HTML)
                    else:
                        copied_msg = await context.bot.send_document(chat_id=MAIN_CHANNEL_ID, document=fid, caption=final_post_text, parse_mode=ParseMode.HTML)
                else:
                    if query.message.photo or query.message.document:
                        copied_msg = await context.bot.copy_message(
                            chat_id=MAIN_CHANNEL_ID,
                            from_chat_id=query.message.chat.id,
                            message_id=query.message.message_id,
                            caption=final_post_text,
                            parse_mode=ParseMode.HTML
                        )
                    else:
                        copied_msg = await context.bot.send_message(
                            chat_id=MAIN_CHANNEL_ID,
                            text=final_post_text,
                            parse_mode=ParseMode.HTML
                        )

                # Clean up memory
                if hasattr(state, 'pending_fb_media'):
                    if group_id and group_id in state.pending_fb_media:
                        del state.pending_fb_media[group_id]
                    elif int(target_uid) in state.pending_fb_media:
                        del state.pending_fb_media[int(target_uid)]

                await query.message.reply_text(f"{EMOJI_DONE} <b>Feedback approved and sent to channel.</b>", parse_mode=ParseMode.HTML)
                await context.bot.send_message(chat_id=int(target_uid), text=f"{EMOJI_DONE} <b>Your feedback has been approved and posted!</b>", parse_mode=ParseMode.HTML)
            except Exception as e:
                await query.message.reply_text(f"{EMOJI_WRONG} <b>Failed to post feedback:</b> {e}", parse_mode=ParseMode.HTML)
        else:
            # Clean up memory if rejected
            
            if hasattr(state, 'pending_fb_media'):
                if group_id and group_id in state.pending_fb_media:
                    del state.pending_fb_media[group_id]
                elif int(target_uid) in state.pending_fb_media:
                    del state.pending_fb_media[int(target_uid)]

            await query.message.reply_text(f"{EMOJI_DEAD} <b>Feedback rejected.</b>", parse_mode=ParseMode.HTML)
            try:
                await context.bot.send_message(chat_id=int(target_uid), text=f"{EMOJI_DEAD} <b>Your feedback was rejected by the admin.</b>", parse_mode=ParseMode.HTML)
            except: pass

    elif data == "adm_settings_menu":
        if not is_admin_user(uid): return
        text = (
            f"{EMOJI_TOOLS} <b>Bot Settings:</b>\n\n"
            f"Free Mass Daily: <code>{bot_settings.get('mass_daily_free', 100)}</code>\n"
            f"Premium Mass Daily: <code>{bot_settings.get('mass_daily_prem', 1000)}</code>\n"
            f"Premium Max: <code>{bot_settings.get('prem_max', 1000)}</code>"
        )
        kb = [
            [btn("Shopify Settings", callback_data="adm_shopify_settings", icon_id=ID_SHOPIFY), btn("Remove Premium", callback_data="adm_remove_premium_menu", icon_id=ID_DEAD)],
            [btn("Group Settings", callback_data="adm_group_menu", style="primary", icon_id=ID_PROFILE)],
            [btn("Reload All Data", callback_data="adm_reload_all", style="primary", icon_id=ID_TOOLS)],
            [btn("Back to Admin", callback_data="admin_menu", icon_id=ID_BC)]
        ]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))


    elif data == "adm_remove_premium_menu":
        if not is_admin_user(uid): return
        from bot.utils.usage import get_all_premium_dict
        users = get_all_premium_dict()
        premium_users = [(user_id, expiry) for user_id, expiry in users.items() if expiry]

        text = f"{EMOJI_DEAD} <b>Remove Premium</b>\n\n"
        kb = []
        if premium_users:
            text += "Tap a user below to remove premium, or use <code>/rmprem USER_ID</code>."
            for user_id, expiry in premium_users[:20]:
                label = "lifetime" if expiry == "lifetime" else str(expiry)
                kb.append([btn(f"Remove {user_id} ({label})", callback_data=f"adm_rmprem:{user_id}", icon_id=ID_DEAD)])
        else:
            text += "No premium users found."
        kb.append([btn("Back", callback_data="adm_settings_menu", icon_id=ID_BC)])
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("adm_rmprem:"):
        if not is_admin_user(uid): return
        target = data.split(":", 1)[1]
        if remove_premium(target):
            await query.answer(f"Premium removed from {target}.", show_alert=True)
        else:
            await query.answer("User is not premium.", show_alert=True)
        await button_handler(update, context, override_data="adm_remove_premium_menu")

    elif data in ["adm_group_menu", "adm_group_settings"]:
        if not is_admin_user(uid): return
        from bot.utils.db import db_get_all_groups
        groups_raw = db_get_all_groups()
        if isinstance(groups_raw, dict):
            group_ids = list(groups_raw.keys())
        elif isinstance(groups_raw, list):
            group_ids = groups_raw
        else:
            group_ids = []
        body = "\n".join([f"• <code>{html.escape(str(g))}</code>" for g in group_ids[:20]]) or "No authorized groups."
        text = (
            f"{EMOJI_PROFILE} <b>Authorized Groups</b>\n\n"
            f"{body}\n\n"
            f"Manage with commands:\n"
            f"• <code>/addgroup GROUP_ID</code>\n"
            f"• <code>/delgroup GROUP_ID</code>"
        )
        is_blocked = bot_settings.get("group_block_free_sh", False)
        kb = [
            [btn(f"Block Free Shopify: {'ON' if is_blocked else 'OFF'}", callback_data="adm_toggle_group_block_sh", icon_id=ID_DEAD if is_blocked else ID_LIVE)],
            [btn("Refresh", callback_data="adm_group_menu", icon_id=ID_TOOLS)],
            [btn("Back", callback_data="adm_settings_menu", icon_id=ID_BC)]
        ]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_toggle_group_block_sh":
        if not is_admin_user(uid): return
        bot_settings["group_block_free_sh"] = not bot_settings.get("group_block_free_sh", False)
        save_json(SETTINGS_FILE, bot_settings)
        await query.answer(f"Block Free Shopify: {'ON' if bot_settings['group_block_free_sh'] else 'OFF'}", show_alert=True)
        await button_handler(update, context, override_data="adm_group_menu")

    elif data == "adm_reload_all":
        if not is_admin_user(uid): return
        try:
            from bot.utils.helpers import load_json_dict
            new_settings = load_json_dict(SETTINGS_FILE)
            if new_settings:
                bot_settings.clear()
                bot_settings.update(new_settings)
            await query.answer("Bot settings successfully reloaded from disk.", show_alert=True)
        except Exception as e:
            await query.answer(f"Failed to reload settings: {e}", show_alert=True)
        await button_handler(update, context, override_data="adm_settings_menu")

    elif data == "adm_bc":
        if not is_admin_user(uid): return
        kb = [[btn("Back", callback_data="admin_menu", icon_id=ID_BC)]]
        await nav_reply(f"{EMOJI_BC} <b>Broadcast Prompt:</b>\n\nUse <code>/broadcast Your message</code>.", reply_markup=InlineKeyboardMarkup(kb))

    elif data == "redeem_help":
        text = (
            f"{EMOJI_RANK} <b>Redeem Code:</b>\n"
            f"Use the command <code>/redeem YOUR_CODE</code> to add credits or premium time to your account."
        )
        kb = [[btn("Back", callback_data="start_menu", icon_id=ID_BC)]]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data in ["adm_users_menu", "adm_active_users"]:
        if not is_admin_user(uid): return
        from bot.utils.db import db_get_all_banned
        banned = db_get_all_banned()
        from bot.utils.usage import get_all_credits_dict, get_all_premium_dict
        credits = get_all_credits_dict()
        users = get_all_premium_dict()

        text = (
            f"{EMOJI_PROFILE} <b>User Management</b>\n\n"
            f"Total credit users: <code>{len(credits)}</code>\n"
            f"Premium users: <code>{len(users)}</code>\n"
            f"Banned users: <code>{len(banned)}</code>\n\n"
            f"Commands:\n"
            f"• <code>/ban USER_ID</code>\n"
            f"• <code>/unban USER_ID</code>\n"
            f"• <code>/rmprem USER_ID</code>"
        )
        kb = [
            [btn("View Banned", callback_data="adm_banned_users", icon_id=ID_DEAD), btn("View Premium", callback_data="adm_remove_premium_menu", icon_id=ID_RANK)],
            [btn("Back", callback_data="admin_menu", icon_id=ID_BC)]
        ]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data == "adm_banned_users":
        if not is_admin_user(uid): return
        from bot.utils.db import db_get_all_banned
        banned = db_get_all_banned()
        text = f"{EMOJI_DEAD} <b>Banned Users</b>\n\n"
        kb = []
        if banned:
            text += "Tap a user below to unban, or use <code>/unban USER_ID</code>."
            for user_id in list(banned.keys())[:20]:
                kb.append([btn(f"Unban {user_id}", callback_data=f"adm_unban:{user_id}", icon_id=ID_LIVE)])
        else:
            text += "No banned users found."
        kb.append([btn("Back", callback_data="adm_users_menu", icon_id=ID_BC)])
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("adm_unban:"):
        if not is_admin_user(uid): return
        target = data.split(":", 1)[1]
        from bot.utils.db import db_is_banned, db_unban_user
        if db_is_banned(target):
            db_unban_user(target)
            await query.answer(f"User {target} unbanned.", show_alert=True)
        else:
            await query.answer("User is not banned.", show_alert=True)
        await button_handler(update, context, override_data="adm_banned_users")

    elif data == "fsub_check_joined":
        fsub_channel = bot_settings.get("fsub_channel")
        fsub_channel_link = bot_settings.get("fsub_channel_link")
        fsub_group = bot_settings.get("fsub_group")
        fsub_group_link = bot_settings.get("fsub_group_link")

        not_joined = []
        user_id = uid

        def clean_chat_id(val):
            if not val:
                return ""
            s = str(val).strip().lower()
            if "t.me/" in s:
                s = s.split("t.me/")[-1].lstrip("+")
                if "/" in s:
                    s = s.split("/")[0]
            s = s.lstrip('@')
            s = s.replace("-100", "").replace("-", "")
            return s

        async def _check_membership(chat_id_or_username, is_group=False):
            if not chat_id_or_username:
                return True
            if is_group and query.message.chat.type in ['group', 'supergroup']:
                return True
            eff_chat_clean = clean_chat_id(query.message.chat.id)
            target_chat_clean = clean_chat_id(chat_id_or_username)
            if eff_chat_clean and target_chat_clean and eff_chat_clean == target_chat_clean:
                return True
            if query.message.chat.username:
                eff_user_clean = clean_chat_id(query.message.chat.username)
                if eff_user_clean and target_chat_clean and eff_user_clean == target_chat_clean:
                    return True

            target_id = chat_id_or_username
            if isinstance(target_id, str):
                clean_str = target_id.strip()
                if "t.me/" in clean_str:
                    part = clean_str.split("t.me/")[-1].strip()
                    if part.startswith("+") or part.startswith("joinchat/"):
                        return True
                    else:
                        target_id = "@" + part.split("/")[0]
                elif clean_str.startswith("-") or clean_str.isdigit():
                    try:
                        target_id = int(clean_str)
                    except ValueError:
                        pass

            try:
                member = await context.bot.get_chat_member(chat_id=target_id, user_id=user_id)
                if member.status in ['left', 'kicked']:
                    return False
                return True
            except Exception as e:
                logger.error(f"FSub Done: Error checking membership for {target_id}: {e}")
                return True

        is_admin_or_bypassed = False
        if query.message.chat.type in ['group', 'supergroup']:
            if uid in [108790513, 136817688]:
                is_admin_or_bypassed = True
            else:
                try:
                    chat_member = await context.bot.get_chat_member(chat_id=query.message.chat.id, user_id=uid)
                    if chat_member.status in ['creator', 'administrator']:
                        is_admin_or_bypassed = True
                except Exception:
                    pass

        if is_admin_or_bypassed or is_admin_user(uid):
            pass
        else:
            if fsub_channel and fsub_channel_link:
                if not await _check_membership(fsub_channel, is_group=False):
                    not_joined.append(("Channel", fsub_channel_link))
                    
            if fsub_group and fsub_group_link:
                if not await _check_membership(fsub_group, is_group=True):
                    not_joined.append(("Group", fsub_group_link))

        if not not_joined:
            try:
                await query.message.delete()
            except:
                pass
            await query.answer("✅ Verification successful! You can now use the bot.", show_alert=True)
        else:
            missing_names = " And ".join([name for name, link in not_joined])
            await query.answer(f"❌ You still need to join: {missing_names}", show_alert=True)
            
            from bot.utils.ui import btn as ui_btn
            msg = (
                '<tg-emoji emoji-id="5039665997506675838">⛔</tg-emoji> <b>Access Denied</b> <tg-emoji emoji-id="6260506384060647928">👮</tg-emoji>\n\n'
                f'<tg-emoji emoji-id="6219886357196574645">📣</tg-emoji> You Must Join Our Official {missing_names} To Use This Bot.\n\n'
                '<tg-emoji emoji-id="6230941830649743676">👇</tg-emoji> Please Join Using The Buttons Below And Try Again!'
            )
            buttons = []
            for name, link in not_joined:
                buttons.append([ui_btn(f"Join {name}", url=link, icon_id="5039834781131474002")])
            buttons.append([ui_btn("DONE", callback_data="fsub_check_joined", icon_id="5039793437776282663")])
            
            try:
                await query.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            except Exception:
                pass

    elif data == "stop_current" or data.startswith("stop_current_"):
        if data.startswith("stop_current_"):
            owner_uid = data.split("stop_current_")[1]
            if str(uid) != owner_uid:
                await query.answer("You didn't start this check!", show_alert=True)
                return
        uid_str = str(uid)
        if state.active_checks.get(uid_str, False):
            state.active_checks[uid_str] = False
            await query.answer("Checking process stopped.", show_alert=True)
            try: await query.edit_message_reply_markup(reply_markup=None)
            except: pass
        else:
            await query.answer("No active check to stop.", show_alert=True)

    elif data.startswith("inl_chk_"):
        try:
            card = data.split("inl_chk_")[1]
            
            # 1. Double check admin privilege on button click
            if not is_admin_user(uid):
                await query.answer("This bot is configured in Admin-Only Inline Mode.", show_alert=True)
                return

            # 2. Start check
            await query.edit_message_text(
                f"💳 <b>Braintree Auth Check</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"🃏 <b>Card:</b> <code>{card}</code>\n"
                f"⏳ <b>Status:</b> Checking in progress... Please wait.",
                parse_mode=ParseMode.HTML
            )
            
            # Call the Braintree engine directly!
            
            # Run in thread pool to prevent blocking
            proxy = get_random_proxy()
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda: braintree_engine.process(card, proxy=proxy))
            
            status = result.get("status", "error")
            msg = result.get("msg", "Unknown error")
            bin_info = result.get("bin_info", {})
            if not bin_info:
                bin_info = braintree_engine.get_bin_info(card)
                
            status_label = "APPROVED (LIVE) ✅" if status == "live" else ("DECLINED ❌" if status == "dead" else "ERROR ⚠️")
            
            brand = (bin_info.get("brand") or "UNKNOWN").upper()
            card_type = (bin_info.get("type") or "UNKNOWN").upper()
            bank = (bin_info.get("bank") or "UNKNOWN").upper()
            country = (bin_info.get("country") or "UNKNOWN").upper()
            
            res_text = (
                f"💳 <b>Braintree Auth Check Result</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"🃏 <b>Card:</b> <code>{card}</code>\n"
                f"<b>Status:</b> {status_label}\n"
                f"<b>Response:</b> <code>{html.escape(msg)}</code>\n"
                f"━━━━━━━━━━━━━━\n"
                f"ℹ️ <b>BIN Info:</b>\n"
                f"• <b>Brand:</b> <code>{brand}</code>\n"
                f"• <b>Type:</b> <code>{card_type}</code>\n"
                f"• <b>Bank:</b> <code>{bank}</code>\n"
                f"• <b>Country:</b> <code>{country}</code>\n"
                f"━━━━━━━━━━━━━━\n"
                f"👤 <b>Checked by:</b> @{query.from_user.username or 'Admin'}\n"
                f"⏰ <b>Completed in:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>"
            )
            
            # Edit the inline message with final result
            await query.edit_message_text(res_text, parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
        except Exception as e:
            logger.exception("Error executing inline check")
            state.errors.append(f"Inline Check Exec Err: {e}\n{traceback.format_exc()}")
            try:
                await query.edit_message_text(
                    f"⚠️ <b>Check Execution Error</b>\n\nFailed to check card. Check bot logs or error console.",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass

    elif data == "toggle_proxy_pool_on":
        from bot.utils.db import db_set_use_pool
        db_set_use_pool(uid, 1)
        await button_handler(update, context, override_data="shopify_proxy_menu")
        
    elif data == "toggle_proxy_pool_off":
        from bot.utils.db import db_set_use_pool
        db_set_use_pool(uid, 0)
        await button_handler(update, context, override_data="shopify_proxy_menu")

    elif data == "adm_proxy_pool_menu":
        from bot.utils.helpers import get_global_proxies
        proxies = get_global_proxies()
        p_lines = [p.strip() for p in proxies.split("\n") if p.strip()]
        total = len(p_lines)
        
        text = (
            f"<tg-emoji emoji-id='6181682949516173646'>⚙️</tg-emoji> <b>Global Proxy Pool Manager</b>\n\n"
            f"<b>Total Proxies Loaded:</b> <code>{total}</code>\n\n"
            f"Use commands in chat to manage:\n"
            f"<code>/addpool ip:port</code> - Add proxies (supports replies to .txt)\n"
            f"<code>/rmpool</code> - Clear proxy pool\n"
            f"<code>/pool</code> - View current pool"
        )
        kb = [
            [btn("Check Proxies", callback_data="adm_proxy_pool_check", style="success", icon_id=ID_LIVE), btn("Delete All", callback_data="adm_proxy_pool_delete", style="danger", icon_id=ID_DEAD)],
            [btn("Refresh", callback_data="adm_proxy_pool_menu", icon_id=ID_LIVE)],
            _admin_back_kb().inline_keyboard[0]
        ]
        await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))
        
    elif data == "adm_proxy_pool_delete":
        from bot.utils.helpers import clear_global_proxies
        try:
            clear_global_proxies()
            await query.answer("Global Proxy Pool deleted!", show_alert=True)
        except Exception as e:
            await query.answer(f"Error: {e}", show_alert=True)
            
        await query.message.edit_reply_markup(InlineKeyboardMarkup([
            [btn("Refresh", callback_data="adm_proxy_pool_menu", icon_id=ID_LIVE)],
            _admin_back_kb().inline_keyboard[0]
        ]))
        
    elif data == "adm_proxy_pool_check":
        from bot.utils.helpers import get_global_proxies, test_proxy_connection, set_global_proxies
        
        proxies = get_global_proxies()
        p_lines = [p.strip() for p in proxies.split("\n") if p.strip()]
        
        if not p_lines:
            await query.answer("Proxy pool is empty!", show_alert=True)
            return
            
        await query.answer()
        sent_msg = None
        try:
            from bot.core.config import ID_LOAD
            sent_msg = await query.message.reply_animation(animation=ID_LOAD, caption=f"{EMOJI_TIME} <b>Testing {len(p_lines)} global proxies...</b> Please wait.", parse_mode=ParseMode.HTML)
        except Exception:
            sent_msg = await nav_reply(f"{EMOJI_TIME} <b>Testing {len(p_lines)} global proxies...</b> Please wait.")
        
        async def _check_global_proxies():
            sem = asyncio.Semaphore(150)
            async def _check(p):
                async with sem:
                    return await test_proxy_connection(p)
            
            tasks = [_check(p) for p in p_lines]
            results = await asyncio.gather(*tasks)
            
            live_proxies = [r[3] for r in results if r[0]]
            
            set_global_proxies("\n".join(live_proxies))
            
            text = (
                f"{EMOJI_DONE} <b>Global Proxy Check Complete</b>\n\n"
                f"{EMOJI_PROXY} Tested: <code>{len(p_lines)}</code>\n"
                f"{EMOJI_LIVE} Alive: <code>{len(live_proxies)}</code>\n"
                f"{EMOJI_DEAD} Dead/Timeout: <code>{len(p_lines) - len(live_proxies)}</code>"
            )
            kb = [
                [btn("Refresh", callback_data="adm_proxy_pool_menu", icon_id=ID_LIVE)],
                _admin_back_kb().inline_keyboard[0]
            ]
            try:
                if sent_msg and sent_msg.animation:
                    await sent_msg.delete()
                    await nav_reply(text, reply_markup=InlineKeyboardMarkup(kb))
                elif sent_msg:
                    await sent_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
                else:
                    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
            except:
                pass

        asyncio.create_task(_check_global_proxies())

    else:
        logger.info("Unknown callback action uid=%s data=%s", uid, data)
        await query.answer("Unknown button action.", show_alert=True)

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin_user(uid): return
    
    text, kb = admin_menu_logic()
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import uuid
    try:
        query = update.inline_query.query.strip()
        uid = update.inline_query.from_user.id
        
        # 1. Answer immediately if not admin to prevent loading spinner
        if not is_admin_user(uid):
            results = [
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="❌ Unauthorized Access",
                    description="This bot's inline mode is strictly restricted to Admins.",
                    input_message_content=InputTextMessageContent(
                        "❌ <b>Access Denied</b>\n\nOnly bot administrators can use inline queries.",
                        parse_mode=ParseMode.HTML
                    )
                )
            ]
            await update.inline_query.answer(results, cache_time=3600, is_personal=True)
            return
            
        if not query:
            # Show hint
            results = [
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="🔍 Admin Inline Mode",
                    description="Type card details: card|mm|yy|cvv",
                    input_message_content=InputTextMessageContent(
                        "<b>Admin Inline Mode</b>\n\nFormat: <code>card|mm|yy|cvv</code>",
                        parse_mode=ParseMode.HTML
                    )
                )
            ]
            await update.inline_query.answer(results, cache_time=1)
            return

        # Parse card
        card_match = re.search(r'(\d{15,16})[|:,\s]+(\d{1,2})[|:,\s]+(\d{2,4})[|:,\s]+(\d{3,4})', query)
        if not card_match:
            results = [
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="❌ Invalid Card Format",
                    description="Please use: card|mm|yy|cvv",
                    input_message_content=InputTextMessageContent(
                        f"❌ <b>Invalid format:</b> <code>{html.escape(query)}</code>\nUse <code>card|mm|yy|cvv</code>",
                        parse_mode=ParseMode.HTML
                    )
                )
            ]
            await update.inline_query.answer(results, cache_time=1)
            return

        cc, mm, yy, cvv = card_match.groups()
        card_line = f"{cc}|{mm}|{yy}|{cvv}"
        
        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"⚡ Run Braintree Auth: {cc[:6]}xxxx|{mm}|{yy}",
                description=f"Click to prepare auth check for {card_line}",
                input_message_content=InputTextMessageContent(
                    f"💳 <b>Braintree Auth Check</b>\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"🃏 <b>Card:</b> <code>{cc[:6]}xxxxxxxxxxxx|{mm}|{yy}|***</code>\n"
                    f"👤 <b>Prepared by:</b> @{update.inline_query.from_user.username or 'Admin'}\n\n"
                    f"<i>Click the button below to initiate the check.</i>",
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=InlineKeyboardMarkup([
                    [btn("⚡ Execute Check", callback_data=f"inl_chk_{card_line}", icon_id=ID_LIVE)]
                ])
            )
        ]
        await update.inline_query.answer(results, cache_time=1)
    except Exception as exc:
        logger.exception("Error in inline_query_handler")
        state.errors.append(f"Inline Query Err: {exc}\n{traceback.format_exc()}")
