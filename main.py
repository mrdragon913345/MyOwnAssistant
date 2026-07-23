import os
import sys
import asyncio
import logging
import socket
import time

try:
    import uvloop
    uvloop.install()
except ImportError:
    pass

try:
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if hard > soft:
        resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
except Exception:
    pass

_dns_cache = {}
_original_getaddrinfo = socket.getaddrinfo

def _cached_getaddrinfo(*args, **kwargs):
    host = kwargs.get('host')
    if len(args) > 0:
        host = args[0]
        
    # Skip caching for localhost, raw IP addresses (no letters), or empty hosts
    if not host or not isinstance(host, str) or not any(c.isalpha() for c in host) or host in ('localhost', '127.0.0.1', '0.0.0.0'):
        return _original_getaddrinfo(*args, **kwargs)
        
    cache_key = (args, tuple(sorted(kwargs.items())))
    now = time.time()
    
    if cache_key in _dns_cache:
        cached_res, timestamp = _dns_cache[cache_key]
        if now - timestamp < 600:
            return cached_res
            
    try:
        res = _original_getaddrinfo(*args, **kwargs)
        _dns_cache[cache_key] = (res, now)
        return res
    except Exception as e:
        if cache_key in _dns_cache:
            return _dns_cache[cache_key][0]
        raise e

socket.getaddrinfo = _cached_getaddrinfo

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, InlineQueryHandler
from telegram import Update
from telegram.constants import ParseMode
from bot.core.config import TOKEN

from bot.handlers.shopify_cmds import shopify_handler, shopify_doc_handler, checkout_handler, dm_card_parser_handler, test_fire_cmd
from bot.handlers.user import parse_cmd, split_cmd, gen_cc_cmd, start, redeem_cmd, set_proxy_cmd, rm_proxy_cmd, help_cmd, bin_cmd, feedback_cmd, info_cmd, lb_cmd
from bot.handlers.admin import stats_cmd, inclimit_cmd, deauth_cmd, op_cmd, deop_cmd, broadcast_cmd, status_cmd, ban_cmd, unban_cmd, remove_premium_cmd, keysdays_cmd, addcredits_cmd, gen_cmd, distribute_credits_cmd, set_delay_cmd, set_limit_cmd, set_masslimit_cmd, addproxy_cmd, proxies_cmd, delproxy_cmd, addpool_cmd, rmpool_cmd, pool_cmd, addsite_cmd, delsite_cmd, sites_cmd, site_check_cmd, clearsites_cmd, preusers_cmd, delcache_cmd, setchannel_cmd, setgroup_cmd, auth_cmd, vps_cmd, setapi_cmd
from bot.handlers.router import button_handler, admin_cmd, inline_query_handler
from bot.handlers.fsub import fsub_middleware
from bot.handlers.maintenance import maintenance_middleware

from telegram.error import NetworkError, TimedOut

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, (NetworkError, TimedOut)):
        logger.warning(f"Telegram network/timeout error: {context.error}")
    else:
        logger.exception("Unhandled Telegram handler exception", exc_info=context.error)

async def post_init(application: Application):
    from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
    from bot.core.config import ADMIN_IDS
    
    public_commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "View all user commands"),
        BotCommand("redeem", "Redeem Premium/Credit code"),
        BotCommand("sh", "Shopify Auth Single Check"),
        BotCommand("setproxy", "Set your custom proxy"),
        BotCommand("rmproxy", "Remove your proxy")
    ]
    
    admin_commands = public_commands + [
        BotCommand("admin", "Open admin panel"),
        BotCommand("broadcast", "Message all users"),
        BotCommand("status", "System health"),
        BotCommand("stats", "Advanced Statistics"),
        BotCommand("ban", "Ban a user"),
        BotCommand("gen", "Generate code"),
        BotCommand("setdelay", "Set delay per check"),
        BotCommand("addsite", "Add Shopify site")
    ]
    
    try:
        await application.bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())
        for admin_id in ADMIN_IDS:
            try:
                await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception as e:
                logger.debug(f"Could not set admin commands for {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Error setting bot commands: {e}")

def main():
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.set_default_executor(ThreadPoolExecutor(max_workers=1000))


    if not TOKEN:
        logger.error("No BOT_TOKEN found in environment variables!")
        return

    try:
        from bot.utils.db import init_db
        init_db()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    import time
    from telegram.error import NetworkError

    while True:
        try:
            application = Application.builder().token(TOKEN).concurrent_updates(True).post_init(post_init).build()
            application.add_error_handler(global_error_handler)
            
            from bot.handlers.user import close_menu_callback
            
            from telegram.ext.filters import MessageFilter
            import bot.core.state as state
            class ActiveAlbumFilter(MessageFilter):
                def filter(self, message):
                    group_id = message.media_group_id
                    if group_id and hasattr(state, 'feedback_albums') and group_id in state.feedback_albums:
                        return True
                    return False

            active_album_filter = ActiveAlbumFilter()
            f_filter = filters.Regex(r'(?i)(?:^|\s)/f\b') | filters.CaptionRegex(r'(?i)(?:^|\s)/f\b') | active_album_filter
            
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("info", info_cmd))
            application.add_handler(CommandHandler("lb", lb_cmd))
            application.add_handler(CommandHandler("help", help_cmd))
            application.add_handler(CommandHandler("setproxy", set_proxy_cmd))
            application.add_handler(CommandHandler("rmproxy", rm_proxy_cmd))
            application.add_handler(CommandHandler("redeem", redeem_cmd))
            application.add_handler(CommandHandler("bin", bin_cmd))
            application.add_handler(CommandHandler("split", split_cmd))
            application.add_handler(CommandHandler("parse", parse_cmd))
            application.add_handler(MessageHandler(f_filter, feedback_cmd))
            application.add_handler(CommandHandler("testfire", test_fire_cmd))
            application.add_handler(CallbackQueryHandler(close_menu_callback, pattern="^close_menu$"))
            
            # Shopify Core Handlers
            application.add_handler(CommandHandler("sh", shopify_handler))
            application.add_handler(CommandHandler("msh", shopify_doc_handler))
            application.add_handler(CommandHandler("mshtxt", shopify_doc_handler))
            application.add_handler(CommandHandler("checkout", checkout_handler))
            
            # DM Card Auto-Parser
            application.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.Document.ALL) & ~filters.COMMAND, dm_card_parser_handler))
            
            # Global FSub Middleware
            from telegram.ext import TypeHandler
            application.add_handler(TypeHandler(Update, maintenance_middleware), group=-2)
            application.add_handler(TypeHandler(Update, fsub_middleware), group=-1)

            # Admin & UI Handlers
            application.add_handler(CommandHandler("setchannel", setchannel_cmd))
            application.add_handler(CommandHandler("setgroup", setgroup_cmd))
            application.add_handler(CommandHandler("broadcast", broadcast_cmd))
            application.add_handler(CommandHandler("status", status_cmd))
            application.add_handler(CommandHandler("stats", stats_cmd))
            application.add_handler(CommandHandler("ban", ban_cmd))
            application.add_handler(CommandHandler("unban", unban_cmd))
            application.add_handler(CommandHandler("auth", auth_cmd))
            application.add_handler(CommandHandler("rmprem", remove_premium_cmd))
            application.add_handler(CommandHandler("keysdays", keysdays_cmd))
            application.add_handler(CommandHandler("preusers", preusers_cmd))
            application.add_handler(CommandHandler("addcredits", addcredits_cmd))
            application.add_handler(CommandHandler("gen", gen_cmd))
            application.add_handler(CommandHandler("op", op_cmd))
            application.add_handler(CommandHandler("deop", deop_cmd))
            application.add_handler(CommandHandler("inclimit", inclimit_cmd))
            application.add_handler(CommandHandler("deauth", deauth_cmd))
            application.add_handler(CommandHandler("gencc", gen_cc_cmd))
            application.add_handler(CommandHandler("distribute", distribute_credits_cmd))
            application.add_handler(CommandHandler("setdelay", set_delay_cmd))
            application.add_handler(CommandHandler("setlimit", set_limit_cmd))
            application.add_handler(CommandHandler("setmasslimit", set_masslimit_cmd))
            # Free limit command removed
            application.add_handler(CommandHandler("addproxy", addproxy_cmd))
            application.add_handler(CommandHandler("addpool", addpool_cmd))
            application.add_handler(CommandHandler("rmpool", rmpool_cmd))
            application.add_handler(CommandHandler("pool", pool_cmd))
            application.add_handler(CommandHandler("proxies", proxies_cmd))
            application.add_handler(CommandHandler("delproxy", delproxy_cmd))
            application.add_handler(CommandHandler("rmproxy", delproxy_cmd))
            application.add_handler(CommandHandler("addsite", addsite_cmd))
            application.add_handler(CommandHandler("delsite", delsite_cmd))
            application.add_handler(CommandHandler("rmsite", delsite_cmd))
            application.add_handler(CommandHandler("clearsites", clearsites_cmd))
            application.add_handler(CommandHandler("sites", sites_cmd))
            application.add_handler(CommandHandler("sitecheck", site_check_cmd))
            application.add_handler(CommandHandler("checksite", site_check_cmd))
            application.add_handler(CommandHandler("delcache", delcache_cmd))
            application.add_handler(CommandHandler("admin", admin_cmd))
            application.add_handler(CommandHandler("vps", vps_cmd))
            application.add_handler(CommandHandler("setapi", setapi_cmd))
            # Panel command removed
            
            # Router
            application.add_handler(CallbackQueryHandler(button_handler))
            application.add_handler(InlineQueryHandler(inline_query_handler))

            logger.info("Bot starting polling...")
            application.run_polling(drop_pending_updates=True)
            break  # Clean exit (e.g. stopped by SIGINT/SIGTERM)
        except (NetworkError, Exception) as e:
            logger.error(f"Critical error in bot polling: {e}. Reconnecting in 10 seconds...")
            time.sleep(10)

if __name__ == "__main__":
    main()
