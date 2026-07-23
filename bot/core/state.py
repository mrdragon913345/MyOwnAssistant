import threading
import asyncio
from bot.core.config import STATS_FILE, SETTINGS_FILE
import json
import os

# --- Global Locks ---
_io_lock = threading.RLock()
stats_lock = threading.RLock()

def load_json(path):
    if os.path.exists(path):
        with _io_lock:
            try:
                with open(path, 'r', encoding='utf-8') as f: return json.load(f)
            except: return {}
    return {}

_saved_state = load_json(SETTINGS_FILE)

# --- Global State ---
bot_operational = _saved_state.get('bot_operational', True)
global_stop_signal = _saved_state.get('global_stop_signal', False)
global_mass_stop_signal = _saved_state.get('global_mass_stop_signal', False)
bt_auth_stop_signal = _saved_state.get('bt_auth_stop_signal', False)
stripe_auth_stop_signal = _saved_state.get('stripe_auth_stop_signal', False)
pp_auth_stop_signal = _saved_state.get('pp_auth_stop_signal', False)
stripe_ccn_stop_signal = _saved_state.get('stripe_ccn_stop_signal', False)
stripe1_stop_signal = _saved_state.get('stripe1_stop_signal', False)
shopify_stop_signal = _saved_state.get('shopify_stop_signal', False)
frbt_stop_signal = _saved_state.get('frbt_stop_signal', False)
selected_account = None
selected_frbt_account = None
active_checks = {} # uid: bool
worker_threads = {}
errors = [] # List of recent error strings

def save_toggles():
    with _io_lock:
        state_dict = load_json(SETTINGS_FILE)
        state_dict['bot_operational'] = bot_operational
        state_dict['global_stop_signal'] = global_stop_signal
        state_dict['global_mass_stop_signal'] = global_mass_stop_signal
        state_dict['bt_auth_stop_signal'] = bt_auth_stop_signal
        state_dict['stripe_auth_stop_signal'] = stripe_auth_stop_signal
        state_dict['stripe_ccn_stop_signal'] = stripe_ccn_stop_signal
        state_dict['pp_auth_stop_signal'] = pp_auth_stop_signal
        state_dict['stripe1_stop_signal'] = stripe1_stop_signal
        state_dict['shopify_stop_signal'] = shopify_stop_signal
        state_dict['frbt_stop_signal'] = frbt_stop_signal
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(state_dict, f, indent=4)
        except: pass

bot_stats = load_json(STATS_FILE)
if not bot_stats: bot_stats = {"total_live": 0, "total_dead": 0, "total_checks": 0}

user_pending_cards = {}


