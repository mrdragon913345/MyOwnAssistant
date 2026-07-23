import time
import os
import threading
from bot.core.config import bot_settings
from bot.utils.helpers import load_json_dict
from bot.utils.db import (
    db_set_credits, db_set_premium, db_remove_premium,
    db_load_all_credits, db_load_all_premium,
    db_increment_daily_usage, db_load_all_daily_usage
)

_usage_lock = threading.Lock()

# In-memory caches for extreme speed, initialized from DB
_credits_cache = db_load_all_credits()
_users_cache = db_load_all_premium()
_today_date = time.strftime("%Y-%m-%d")
_daily_mass_cache = db_load_all_daily_usage(_today_date)

def get_all_credits_dict():
    with _usage_lock:
        return dict(_credits_cache)

def get_all_premium_dict():
    with _usage_lock:
        return dict(_users_cache)

def _get_daily_mass_limit(uid):
    from bot.utils.helpers import is_admin_user
    if is_admin_user(uid):
        return int(bot_settings.get("mass_daily_prem", 5000))
    if is_premium(uid):
        return int(bot_settings.get("mass_daily_prem", 2000))
    return int(bot_settings.get("mass_daily_free", 200))

def get_daily_quota_limit(uid, gateway_key):
    from bot.utils.helpers import is_admin_user
    if is_admin_user(uid): return 999999999
    
    custom = bot_settings.get(f"custom_limit_{uid}")
    if custom is not None:
        return int(custom)
        
    if is_premium(uid):
        return int(bot_settings.get(f"{gateway_key}_prem", bot_settings.get("mass_daily_prem", 5000)))
        
    return int(bot_settings.get(f"{gateway_key}_free", bot_settings.get("mass_daily_free", 100)))

def get_daily_quota_used(uid, gateway_key):
    global _today_date, _daily_mass_cache
    with _usage_lock:
        date = time.strftime("%Y-%m-%d")
        if date != _today_date:
            _today_date = date
            _daily_mass_cache = db_load_all_daily_usage(date)
            
        day_data = _daily_mass_cache.get(str(uid), {})
        return day_data.get(gateway_key, 0)

def consume_daily_quota(uid, count, gateway_key, price_amount: float = 0.0):
    global _today_date, _daily_mass_cache
    with _usage_lock:
        date = time.strftime("%Y-%m-%d")
        if date != _today_date:
            _today_date = date
            _daily_mass_cache = db_load_all_daily_usage(date)
            
        uid_str = str(uid)
        if uid_str not in _daily_mass_cache:
            _daily_mass_cache[uid_str] = {}
            
        _daily_mass_cache[uid_str][gateway_key] = _daily_mass_cache[uid_str].get(gateway_key, 0) + count
        db_increment_daily_usage(date, uid_str, gateway_key, count, price_amount)
        return True

def do_deduct_credits(uid, amount):
    from bot.utils.helpers import is_admin_user
    if is_admin_user(uid): return True
    if is_premium(uid): return True
    if amount <= 0:
        return False
    
    with _usage_lock:
        uid_str = str(uid)
        if uid_str not in _credits_cache:
            _credits_cache[uid_str] = 200
            
        current = _credits_cache.get(uid_str, 0)
        if current < amount: return False
        
        new_val = current - amount
        _credits_cache[uid_str] = new_val
        db_set_credits(uid_str, new_val)
        return True


def refund_credits(uid, amount):
    """Explicit refund path; does not allow negative accounting tricks."""
    if amount <= 0:
        return False

    from bot.utils.helpers import is_admin_user
    if is_admin_user(uid):
        return True
    if is_premium(uid):
        return True

    with _usage_lock:
        uid_str = str(uid)
        current = _credits_cache.get(uid_str, 0)
        new_val = current + amount
        _credits_cache[uid_str] = new_val
        db_set_credits(uid_str, new_val)
        return True

def check_auth(uid):
    from bot.utils.helpers import is_admin_user
    if is_admin_user(uid): return True
    if is_premium(uid): return True
    
    with _usage_lock:
        uid_str = str(uid)
        if uid_str not in _credits_cache:
            _credits_cache[uid_str] = 200
            db_set_credits(uid_str, 200)
            return True
        return _credits_cache.get(uid_str, 0) > 0

def is_premium(uid):
    with _usage_lock:
        val = _users_cache.get(str(uid))
        if not val: return False
        if val == "lifetime": return True
        try: return float(val) > time.time()
        except: return False

def get_premium_time_left(uid):
    import time
    with _usage_lock:
        val = _users_cache.get(str(uid))
        if not val: return None
        if val == "lifetime": return "Lifetime"
        try:
            left = float(val) - time.time()
            if left <= 0: return None
            hours = int(left / 3600)
            if hours > 24:
                days = hours // 24
                rem_hours = hours % 24
                return f"{days} Days {rem_hours} Hours" if rem_hours > 0 else f"{days} Days"
            return f"{hours} Hours"
        except:
            return None

def reload_usage_data():
    """Force reload from DB if needed"""
    global _daily_mass_cache, _credits_cache, _users_cache, _today_date
    with _usage_lock:
        _today_date = time.strftime("%Y-%m-%d")
        _daily_mass_cache = db_load_all_daily_usage(_today_date)
        _credits_cache = db_load_all_credits()
        _users_cache = db_load_all_premium()


def add_credits(uid, amount):
    with _usage_lock:
        uid_str = str(uid)
        new_val = _credits_cache.get(uid_str, 0) + amount
        _credits_cache[uid_str] = new_val
        db_set_credits(uid_str, new_val)
        
def distribute_all_credits(amount):
    with _usage_lock:
        count = 0
        for uid_str in _credits_cache:
            new_val = _credits_cache[uid_str] + amount
            _credits_cache[uid_str] = new_val
            db_set_credits(uid_str, new_val)
            count += 1
        return count

def set_premium(uid, days):
    with _usage_lock:
        uid_str = str(uid)
        if days == "lifetime":
            _users_cache[uid_str] = "lifetime"
            db_set_premium(uid_str, "lifetime")
        else:
            try:
                days_val = float(days)
            except:
                days_val = 0.0
            current = _users_cache.get(uid_str)
            now = time.time()
            if current == "lifetime":
                pass # Don't overwrite lifetime with a shorter duration
            else:
                try:
                    current_exp = float(current)
                except:
                    current_exp = now
                if current_exp < now:
                    current_exp = now
                new_val = current_exp + (days_val * 86400)
                _users_cache[uid_str] = new_val
                db_set_premium(uid_str, str(new_val))

def override_premium(uid, days):
    with _usage_lock:
        uid_str = str(uid)
        if days == "lifetime":
            _users_cache[uid_str] = "lifetime"
            db_set_premium(uid_str, "lifetime")
        else:
            try:
                days_val = float(days)
            except:
                days_val = 0.0
            
            current_val = _users_cache.get(uid_str)
            if current_val and current_val != "lifetime":
                try:
                    current_end = float(current_val)
                    if current_end > time.time():
                        new_val = current_end + (days_val * 86400)
                    else:
                        new_val = time.time() + (days_val * 86400)
                except:
                    new_val = time.time() + (days_val * 86400)
            else:
                new_val = time.time() + (days_val * 86400)
                
            _users_cache[uid_str] = new_val
            db_set_premium(uid_str, str(new_val))

def remove_premium(uid):
    with _usage_lock:
        uid_str = str(uid)
        if uid_str in _users_cache:
            del _users_cache[uid_str]
            db_remove_premium(uid_str)
            return True
        return False

