import requests
import json
import os
import time
from datetime import datetime
from bot.core.config import STATS_FILE

# Configuration for hits channel
# Configuration for hits channels (Environment Variables)
# Will be lazily loaded in send_hit

BOT_TOKEN = os.getenv("BOT_TOKEN")

import threading

_stats_lock = threading.Lock()

def send_hit(text, gw="bt", user_info=None, reply_markup=None):
    """
    Spawns a background thread to send the hit message to prevent blocking the async event loop.
    """
    thread = threading.Thread(target=_send_hit_thread, args=(text, gw, user_info, reply_markup), daemon=True)
    thread.start()

def _send_hit_thread(text, gw, user_info, reply_markup):
    bot_token = os.getenv("BOT_TOKEN") or BOT_TOKEN
    if not bot_token: return
    
    hits_channel_id = os.getenv("HITS_GROUP") or "-1003872526156"
    bt_auth_hits = os.getenv("BT_AUTH_HITS") or hits_channel_id
    st_auth_hits = os.getenv("ST_AUTH_HITS") or hits_channel_id
    shopify_hits = os.getenv("SHOPIFY_HITS") or "-1003872526156"
    shopify_approved_hits = os.getenv("SHOPIFY_APPROVED_HITS") or shopify_hits
    shopify_charged_hits = os.getenv("SHOPIFY_CHARGED_HITS") or shopify_hits

    # Select target channel based on gateway
    target = hits_channel_id
    if gw == "bt": target = bt_auth_hits
    elif gw == "st": target = st_auth_hits
    elif gw == "shopify": target = shopify_hits
    elif gw == "shopify_approved": target = shopify_approved_hits
    elif gw == "shopify_charged": target = shopify_charged_hits

    if user_info:
        text += f"\n\n👤 <b>Found by:</b> {user_info}"

    if "Charged" in text or "charged" in text.lower():
        url = f"https://api.telegram.org/bot{bot_token}/sendAnimation"
        payload = {
            "chat_id": target,
            "animation": "https://i.giphy.com/media/xdv8L6vywYnFRLFZKC/giphy.mp4",
            "caption": text,
            "parse_mode": "HTML"
        }
    else:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": target,
            "text": text,
            "parse_mode": "HTML"
        }

    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        if not r.ok:
            print(f"Failed to send hit: {r.text}")
            # Fallback to sendMessage if animation failed
            if "animation" in payload:
                url_fallback = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload_fallback = {
                    "chat_id": target,
                    "text": payload.get("caption", text),
                    "parse_mode": "HTML"
                }
                if reply_markup:
                    payload_fallback["reply_markup"] = reply_markup
                requests.post(url_fallback, json=payload_fallback, timeout=10)
        _update_stats()
    except Exception as e:
        print(f"Error sending hit: {e}")

def _update_stats():
    """Increment hit counters."""
    with _stats_lock:
        stats = {"total_hits": 0, "today_hits": 0, "last_update": ""}
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, 'r') as f: stats = json.load(f)
            except: pass
            
        today = datetime.now().strftime("%Y-%m-%d")
        if stats.get("last_update") != today:
            stats["today_hits"] = 0
            stats["last_update"] = today
            
        stats["total_hits"] = stats.get("total_hits", 0) + 1
        stats["today_hits"] = stats.get("today_hits", 0) + 1
        
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=4)

def get_today_count():
    if not os.path.exists(STATS_FILE): return 0
    with _stats_lock:
        try:
            with open(STATS_FILE, 'r') as f:
                stats = json.load(f)
                if stats.get("last_update") == datetime.now().strftime("%Y-%m-%d"):
                    return stats.get("today_hits", 0)
        except: pass
    return 0

def get_total_count():
    if not os.path.exists(STATS_FILE): return 0
    with _stats_lock:
        try:
            with open(STATS_FILE, 'r') as f:
                stats = json.load(f)
                return stats.get("total_hits", 0)
        except: pass
    return 0
