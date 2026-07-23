import sqlite3
import os
import logging
import threading
from bot.core.config import USERS_FILE, CREDITS_FILE, USER_PROXIES_FILE, DATA_DIR

logger = logging.getLogger(__name__)
DB_FILE = os.path.join(DATA_DIR, 'bot.db')
_db_lock = threading.Lock()

def get_db_connection():
    # Enable WAL mode for concurrent read/write and specify timeout
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _db_lock:
        conn = get_db_connection()
        try:
            with conn:
                # Enable WAL mode for better concurrency
                conn.execute("PRAGMA journal_mode=WAL")
                
                # Users table with premium, credits, proxy, banned
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        premium TEXT,
                        credits INTEGER DEFAULT 200,
                        proxy TEXT,
                        banned INTEGER DEFAULT 0
                    )
                """)
                
                # Ensure banned column exists
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(users)")
                columns = [row[1] for row in cursor.fetchall()]
                if "banned" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0")
                if "use_pool" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN use_pool INTEGER DEFAULT 0")
                
                # Referral Program Columns
                if "invited_by" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN invited_by TEXT DEFAULT NULL")
                if "total_invited" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN total_invited INTEGER DEFAULT 0")
                if "earned_days" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN earned_days INTEGER DEFAULT 0")
                if "created_at" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT '2000-01-01 00:00:00'")
                if "daily_ref_count" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN daily_ref_count INTEGER DEFAULT 0")
                if "last_ref_date" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN last_ref_date TEXT DEFAULT ''")
                if "charged_count" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN charged_count INTEGER DEFAULT 0")
                
                # Authorized groups table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS authorized_groups (
                        group_id TEXT PRIMARY KEY,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Redeemable codes table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS redeem_codes (
                        code TEXT PRIMARY KEY,
                        type TEXT,
                        value REAL
                    )
                """)
                
                # Daily usage table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS daily_usage (
                        date TEXT,
                        user_id TEXT,
                        gateway TEXT,
                        count INTEGER,
                        charge_amount REAL DEFAULT 0.0,
                        PRIMARY KEY (date, user_id, gateway)
                    )
                """)
                
                # Ensure charge_amount column exists for older daily_usage tables
                cursor.execute("PRAGMA table_info(daily_usage)")
                du_columns = [row[1] for row in cursor.fetchall()]
                if "charge_amount" not in du_columns:
                    conn.execute("ALTER TABLE daily_usage ADD COLUMN charge_amount REAL DEFAULT 0.0")
                
                # Bin cache table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS bin_cache (
                        bin_prefix TEXT PRIMARY KEY,
                        brand TEXT,
                        type TEXT,
                        level TEXT,
                        bank TEXT,
                        country_name TEXT,
                        country_code TEXT
                    )
                """)
            logger.info("Database initialized successfully in WAL mode.")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            return

        # Run migration from JSON files to SQLite
        try:
            from bot.utils.helpers import load_json_dict
            from bot.core.config import BANNED_FILE, GROUPS_FILE, CODES_FILE, DAILY_MASS_FILE
            
            # Users, credits, proxies migration (if table is empty)
            users_json = load_json_dict(USERS_FILE)
            credits_json = load_json_dict(CREDITS_FILE)
            proxies_json = load_json_dict(USER_PROXIES_FILE)
            
            all_uids = set(users_json.keys()) | set(credits_json.keys()) | set(proxies_json.keys())
            if all_uids:
                with conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM users")
                    count = cursor.fetchone()[0]
                    if count == 0:
                        logger.info(f"Migrating {len(all_uids)} users from JSON to database...")
                        for uid in all_uids:
                            premium = users_json.get(uid)
                            credits = credits_json.get(uid, 200)
                            proxy = proxies_json.get(uid)
                            cursor.execute("""
                                INSERT OR REPLACE INTO users (user_id, premium, credits, proxy, banned)
                                VALUES (?, ?, ?, ?, 0)
                            """, (uid, premium, credits, proxy))
                        logger.info("Users migration completed.")
            
            # Banned users migration
            if os.path.exists(BANNED_FILE):
                banned_json = load_json_dict(BANNED_FILE)
                if banned_json:
                    logger.info("Migrating banned users from JSON...")
                    with conn:
                        for uid in banned_json:
                            conn.execute("""
                                UPDATE users SET banned = 1 WHERE user_id = ?
                            """, (str(uid),))
                            conn.execute("""
                                INSERT OR IGNORE INTO users (user_id, premium, credits, proxy, banned)
                                VALUES (?, NULL, 200, NULL, 1)
                            """, (str(uid),))
                    try:
                        os.rename(BANNED_FILE, BANNED_FILE + ".migrated")
                    except:
                        pass
            
            # Groups migration
            if os.path.exists(GROUPS_FILE):
                groups_json = load_json_dict(GROUPS_FILE)
                if groups_json:
                    logger.info("Migrating authorized groups from JSON...")
                    if isinstance(groups_json, list):
                        groups_dict = {str(g): True for g in groups_json}
                    else:
                        groups_dict = groups_json
                    with conn:
                        for gid in groups_dict:
                            conn.execute("""
                                INSERT OR IGNORE INTO authorized_groups (group_id)
                                VALUES (?)
                            """, (str(gid),))
                    try:
                        os.rename(GROUPS_FILE, GROUPS_FILE + ".migrated")
                    except:
                        pass
            
            # Codes migration
            if os.path.exists(CODES_FILE):
                codes_json = load_json_dict(CODES_FILE)
                if codes_json:
                    logger.info("Migrating redeemable codes from JSON...")
                    with conn:
                        for code, info in codes_json.items():
                            ctype = info.get('type', 'credits')
                            val = info.get('value', 0)
                            conn.execute("""
                                INSERT OR REPLACE INTO redeem_codes (code, type, value)
                                VALUES (?, ?, ?)
                            """, (code, ctype, val))
                    try:
                        os.rename(CODES_FILE, CODES_FILE + ".migrated")
                    except:
                        pass
                        
            # Daily mass limit cache migration
            if os.path.exists(DAILY_MASS_FILE):
                daily_json = load_json_dict(DAILY_MASS_FILE)
                if daily_json:
                    logger.info("Migrating daily usage from JSON...")
                    with conn:
                        for date_str, day_data in daily_json.items():
                            for uid, user_data in day_data.items():
                                if isinstance(user_data, int):
                                    conn.execute("""
                                        INSERT OR REPLACE INTO daily_usage (date, user_id, gateway, count)
                                        VALUES (?, ?, ?, ?)
                                    """, (date_str, str(uid), "bt_auth_daily_limit", user_data))
                                elif isinstance(user_data, dict):
                                    for gateway, count in user_data.items():
                                        conn.execute("""
                                            INSERT OR REPLACE INTO daily_usage (date, user_id, gateway, count)
                                            VALUES (?, ?, ?, ?)
                                        """, (date_str, str(uid), gateway, count))
                    try:
                        os.rename(DAILY_MASS_FILE, DAILY_MASS_FILE + ".migrated")
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Error during database migration: {e}")
        finally:
            conn.close()

def db_get_user(user_id):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT premium, credits, proxy, banned FROM users WHERE user_id = ?", (uid_str,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        else:
            # Create user with default values in DB
            with _db_lock:
                with conn:
                    conn.execute("INSERT OR IGNORE INTO users (user_id, premium, credits, proxy, banned, created_at) VALUES (?, NULL, 200, NULL, 0, CURRENT_TIMESTAMP)", (uid_str,))
            return {"premium": None, "credits": 200, "proxy": None, "banned": 0}
    except Exception as e:
        logger.error(f"Error fetching user {uid_str}: {e}")
        return {"premium": None, "credits": 200, "proxy": None, "banned": 0}
    finally:
        conn.close()

def db_set_proxy(user_id, proxy_line):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("""
                    INSERT INTO users (user_id, proxy) VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET proxy = excluded.proxy
                """, (uid_str, proxy_line))
        return True
    except Exception as e:
        logger.error(f"Error setting proxy for {uid_str}: {e}")
        return False
    finally:
        conn.close()

def db_get_proxy(user_id):
    user = db_get_user(user_id)
    return user.get("proxy")

def db_delete_user_proxy(user_id):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("""
                    INSERT INTO users (user_id, proxy) VALUES (?, NULL)
                    ON CONFLICT(user_id) DO UPDATE SET proxy = NULL
                """, (uid_str,))
        return True
    except Exception as e:
        logger.error(f"Error deleting proxy for {uid_str}: {e}")
        return False
    finally:
        conn.close()

def db_set_credits(user_id, credits_val):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("""
                    INSERT INTO users (user_id, credits) VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET credits = excluded.credits
                """, (uid_str, credits_val))
        return True
    except Exception as e:
        logger.error(f"Error setting credits for {uid_str}: {e}")
        return False
    finally:
        conn.close()

def db_add_credits(user_id, amount):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("""
                    INSERT INTO users (user_id, credits) VALUES (?, 200 + ?)
                    ON CONFLICT(user_id) DO UPDATE SET credits = credits + excluded.credits
                """, (uid_str, amount))
        return True
    except Exception as e:
        logger.error(f"Error adding credits for {uid_str}: {e}")
        return False
    finally:
        conn.close()

def db_set_premium(user_id, premium_val):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("""
                    INSERT INTO users (user_id, premium) VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET premium = excluded.premium
                """, (uid_str, premium_val))
        return True
    except Exception as e:
        logger.error(f"Error setting premium for {uid_str}: {e}")
        return False
    finally:
        conn.close()

def db_remove_premium(user_id):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("""
                    INSERT INTO users (user_id, premium) VALUES (?, NULL)
                    ON CONFLICT(user_id) DO UPDATE SET premium = NULL
                """, (uid_str,))
        return True
    except Exception as e:
        logger.error(f"Error removing premium for {uid_str}: {e}")
        return False
    finally:
        conn.close()

def db_load_all_credits():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, credits FROM users")
        rows = cursor.fetchall()
        return {row['user_id']: row['credits'] for row in rows}
    except Exception as e:
        logger.error(f"Error loading all credits from DB: {e}")
        return {}
    finally:
        conn.close()

def db_load_all_premium():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, premium FROM users WHERE premium IS NOT NULL")
        rows = cursor.fetchall()
        return {row['user_id']: row['premium'] for row in rows}
    except Exception as e:
        logger.error(f"Error loading all premium from DB: {e}")
        return {}
    finally:
        conn.close()

# Banned users DB helpers
def db_is_banned(user_id):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT banned FROM users WHERE user_id = ?", (uid_str,))
        row = cursor.fetchone()
        if row:
            return bool(row['banned'])
        return False
    except Exception as e:
        logger.error(f"Error checking banned for {uid_str}: {e}")
        return False
    finally:
        conn.close()

def db_ban_user(user_id):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("""
                    INSERT INTO users (user_id, banned) VALUES (?, 1)
                    ON CONFLICT(user_id) DO UPDATE SET banned = 1
                """, (uid_str,))
        return True
    except Exception as e:
        logger.error(f"Error banning {uid_str}: {e}")
        return False
    finally:
        conn.close()

def db_unban_user(user_id):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("""
                    INSERT INTO users (user_id, banned) VALUES (?, 0)
                    ON CONFLICT(user_id) DO UPDATE SET banned = 0
                """, (uid_str,))
        return True
    except Exception as e:
        logger.error(f"Error unbanning {uid_str}: {e}")
        return False
    finally:
        conn.close()

def db_get_all_banned():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE banned = 1")
        rows = cursor.fetchall()
        return {row['user_id']: True for row in rows}
    except Exception as e:
        logger.error(f"Error getting all banned from DB: {e}")
        return {}
    finally:
        conn.close()

# Group DB helpers
def db_is_group_authorized(group_id):
    gid_str = str(group_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM authorized_groups WHERE group_id = ?", (gid_str,))
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking group auth for {gid_str}: {e}")
        return False
    finally:
        conn.close()

def db_authorize_group(group_id):
    gid_str = str(group_id)
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("INSERT OR IGNORE INTO authorized_groups (group_id) VALUES (?)", (gid_str,))
        return True
    except Exception as e:
        logger.error(f"Error authorizing group {gid_str}: {e}")
        return False
    finally:
        conn.close()

def db_unauthorize_group(group_id):
    gid_str = str(group_id)
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("DELETE FROM authorized_groups WHERE group_id = ?", (gid_str,))
        return True
    except Exception as e:
        logger.error(f"Error unauthorizing group {gid_str}: {e}")
        return False
    finally:
        conn.close()

def db_get_all_groups():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT group_id FROM authorized_groups")
        rows = cursor.fetchall()
        return {row['group_id']: True for row in rows}
    except Exception as e:
        logger.error(f"Error getting all groups from DB: {e}")
        return {}
    finally:
        conn.close()

# Codes DB helpers
def db_add_code(code, type_val, value):
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO redeem_codes (code, type, value)
                    VALUES (?, ?, ?)
                """, (code, type_val, value))
        return True
    except Exception as e:
        logger.error(f"Error adding code {code}: {e}")
        return False
    finally:
        conn.close()

def db_get_code(code):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT type, value FROM redeem_codes WHERE code = ?", (code,))
        row = cursor.fetchone()
        if row:
            return {"type": row['type'], "value": row['value']}
        return None
    except Exception as e:
        logger.error(f"Error getting code {code}: {e}")
        return None
    finally:
        conn.close()

def db_delete_code(code):
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("DELETE FROM redeem_codes WHERE code = ?", (code,))
        return True
    except Exception as e:
        logger.error(f"Error deleting code {code}: {e}")
        return False
    finally:
        conn.close()

def db_delete_code_atomic(code):
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM redeem_codes WHERE code = ?", (code,))
                if cursor.fetchone():
                    conn.execute("DELETE FROM redeem_codes WHERE code = ?", (code,))
                    return True
                return False
    except Exception as e:
        logger.error(f"Error atomically deleting code {code}: {e}")
        return False
    finally:
        conn.close()

def db_get_all_codes():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT code, type, value FROM redeem_codes")
        rows = cursor.fetchall()
        return {row['code']: {"type": row['type'], "value": row['value']} for row in rows}
    except Exception as e:
        logger.error(f"Error loading all codes: {e}")
        return {}
    finally:
        conn.close()

# Daily usage DB helpers
def db_get_daily_usage(date_str, user_id, gateway):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT count FROM daily_usage 
            WHERE date = ? AND user_id = ? AND gateway = ?
        """, (date_str, uid_str, gateway))
        row = cursor.fetchone()
        if row:
            return row['count']
        return 0
    except Exception as e:
        logger.error(f"Error getting daily usage: {e}")
        return 0
    finally:
        conn.close()

def db_increment_daily_usage(date_str, user_id, gateway, amount, price_amount: float = 0.0):
    uid_str = str(user_id)
    conn = get_db_connection()
    try:
        with _db_lock:
            with conn:
                conn.execute("""
                    INSERT INTO daily_usage (date, user_id, gateway, count, charge_amount)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(date, user_id, gateway) DO UPDATE SET 
                        count = count + excluded.count,
                        charge_amount = charge_amount + excluded.charge_amount
                """, (date_str, uid_str, gateway, amount, price_amount))
        return True
    except Exception as e:
        logger.error(f"Error incrementing daily usage: {e}")
        return False
    finally:
        conn.close()

def db_load_all_daily_usage(date_str):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, gateway, count FROM daily_usage WHERE date = ?", (date_str,))
        rows = cursor.fetchall()
        res = {}
        for row in rows:
            uid = row['user_id']
            gateway = row['gateway']
            count = row['count']
            if uid not in res:
                res[uid] = {}
            res[uid][gateway] = count
        return res
    except Exception as e:
        logger.error(f"Error loading daily usage: {e}")
        return {}
    finally:
        conn.close()

# Auto-initialize database on load
init_db()


def db_set_use_pool(user_id, status: int):
    uid_str = str(user_id)
    with _db_lock:
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("UPDATE users SET use_pool = ? WHERE user_id = ?", (status, uid_str))
        except Exception as e:
            logger.error(f"Error setting use_pool for {uid_str}: {e}")
        finally:
            conn.close()

def db_get_use_pool(user_id) -> bool:
    uid_str = str(user_id)
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT use_pool FROM users WHERE user_id = ?", (uid_str,))
            row = cursor.fetchone()
            if row and row['use_pool'] == 1:
                return True
            return False
        except Exception as e:
            logger.error(f"Error getting use_pool for {uid_str}: {e}")
            return False
        finally:
            conn.close()

def db_get_total_charged(user_id):
    uid_str = str(user_id)
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(count) FROM daily_usage WHERE user_id = ? AND (gateway LIKE '%charged%' OR gateway LIKE '%approved%')", (uid_str,))
            row = cursor.fetchone()
            return row[0] if row and row[0] else 0
        except Exception as e:
            logger.error(f"Error getting total charged for {uid_str}: {e}")
            return 0
        finally:
            conn.close()

# ─── Referral Program ─────────────────────────────────────────────────────────

def db_get_referral_stats(user_id):
    uid_str = str(user_id)
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT total_invited, earned_days FROM users WHERE user_id = ?", (uid_str,))
            row = cursor.fetchone()
            if row:
                return {"total_invited": row['total_invited'], "earned_days": row['earned_days']}
            return {"total_invited": 0, "earned_days": 0}
        except Exception as e:
            logger.error(f"Error getting referral stats for {uid_str}: {e}")
            return {"total_invited": 0, "earned_days": 0}
        finally:
            conn.close()

def db_update_daily_usage(user_id, gateway, amount: float = 0.0):
    from datetime import datetime
    uid_str = str(user_id)
    today = datetime.utcnow().strftime('%Y-%m-%d')
    with _db_lock:
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO daily_usage (date, user_id, gateway, count, charge_amount)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(date, user_id, gateway) DO UPDATE SET 
                        count = count + 1,
                        charge_amount = charge_amount + excluded.charge_amount
                """, (today, uid_str, gateway, amount))
        except Exception as e:
            logger.error(f"Error updating daily usage for {uid_str}: {e}")
        finally:
            conn.close()

def db_set_invited_by(new_user_id, inviter_id):
    """Sets invited_by for a new user if they don't already have one."""
    uid_str = str(new_user_id)
    inv_str = str(inviter_id)
    with _db_lock:
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT invited_by, created_at FROM users WHERE user_id = ?", (uid_str,))
                row = cursor.fetchone()
                if row:
                    if row['invited_by']:
                        return False # Already invited
                    # Prevent already registered users from giving a reward
                    created_at = row['created_at'] if 'created_at' in row.keys() else None
                    if created_at == '2000-01-01 00:00:00':
                        return False # Legacy existing user
                    if created_at:
                        from datetime import datetime, timedelta
                        try:
                            # CURRENT_TIMESTAMP in SQLite is UTC
                            c_time = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                            if datetime.utcnow() - c_time > timedelta(minutes=10):
                                return False # Already registered user (older than 10 mins)
                        except:
                            pass
                conn.execute("UPDATE users SET invited_by = ? WHERE user_id = ?", (inv_str, uid_str))
                return True
        except Exception as e:
            logger.error(f"Error setting invited_by for {uid_str}: {e}")
            return False
        finally:
            conn.close()

def db_add_referral_reward(inviter_id, max_days=14):
    """Adds 1 day to inviter's premium, up to max_days limit."""
    inv_str = str(inviter_id)
    from datetime import datetime, timedelta
    
    with _db_lock:
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT premium, earned_days, total_invited, daily_ref_count, last_ref_date FROM users WHERE user_id = ?", (inv_str,))
                row = cursor.fetchone()
                if not row:
                    return False
                
                earned_days = row['earned_days'] or 0
                total_invited = row['total_invited'] or 0
                daily_ref_count = row['daily_ref_count'] if 'daily_ref_count' in row.keys() and row['daily_ref_count'] else 0
                last_ref_date = row['last_ref_date'] if 'last_ref_date' in row.keys() and row['last_ref_date'] else ''
                
                today_str = datetime.now().strftime("%Y-%m-%d")
                if last_ref_date != today_str:
                    daily_ref_count = 0
                    last_ref_date = today_str
                
                # Increment invite count
                total_invited += 1
                
                if daily_ref_count >= max_days:
                    # They maxed out their DAILY rewards, but we still count the invite
                    conn.execute("UPDATE users SET total_invited = ?, daily_ref_count = ?, last_ref_date = ? WHERE user_id = ?", (total_invited, daily_ref_count, last_ref_date, inv_str))
                    return False
                
                daily_ref_count += 1
                earned_days += 1
                
                # Update the database
                conn.execute("""
                    UPDATE users 
                    SET earned_days = ?, total_invited = ?, daily_ref_count = ?, last_ref_date = ?
                    WHERE user_id = ?
                """, (earned_days, total_invited, daily_ref_count, last_ref_date, inv_str))
                return True
        except Exception as e:
            logger.error(f"Error adding referral reward for {inv_str}: {e}")
            return False
        finally:
            conn.close()



def db_get_leaderboard(limit=10):
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, SUM(count) as total_hits 
                FROM daily_usage 
                WHERE gateway LIKE '%charged%' OR gateway LIKE '%approved%' 
                GROUP BY user_id 
                ORDER BY total_hits DESC 
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            return "Error retrieving leaderboard."

def db_get_charge_stats():
    from datetime import datetime
    today = datetime.utcnow().strftime('%Y-%m-%d')
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 1. Total All-Time
            cursor.execute("SELECT SUM(charge_amount) FROM daily_usage WHERE gateway LIKE '%charged%'")
            all_time = cursor.fetchone()[0] or 0.0
            
            # 2. Total Today
            cursor.execute("SELECT SUM(charge_amount) FROM daily_usage WHERE date = ? AND gateway LIKE '%charged%'", (today,))
            today_total = cursor.fetchone()[0] or 0.0
            
            # 3. Top 5 Users
            cursor.execute("""
                SELECT user_id, SUM(charge_amount) as total_charged 
                FROM daily_usage 
                WHERE gateway LIKE '%charged%' 
                GROUP BY user_id 
                ORDER BY total_charged DESC 
                LIMIT 5
            """)
            top_users = cursor.fetchall()
            
            return {
                "all_time": all_time,
                "today": today_total,
                "top": top_users
            }
        except Exception as e:
            logger.error(f"Error getting charge stats: {e}")
            return None
        finally:
            conn.close()

def save_cached_bin(bin_prefix: str, data: dict):
    with _db_lock:
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO bin_cache (bin_prefix, brand, type, level, bank, country_name, country_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    bin_prefix,
                    data.get('brand', 'UNKNOWN'),
                    data.get('type', 'UNKNOWN'),
                    data.get('level', 'UNKNOWN'),
                    data.get('bank', 'UNKNOWN'),
                    data.get('country_name', 'UNKNOWN'),
                    data.get('country_code', 'UNKNOWN')
                ))
        except Exception as e:
            logger.error(f"Error saving bin cache: {e}")
        finally:
            conn.close()

def get_cached_bin(bin_prefix: str) -> dict:
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bin_cache WHERE bin_prefix = ?", (bin_prefix,))
            row = cursor.fetchone()
            if row:
                return {
                    'brand': row['brand'],
                    'type': row['type'],
                    'level': row['level'],
                    'bank': row['bank'],
                    'country_name': row['country_name'],
                    'country': row['country_name'],
                    'country_code': row['country_code']
                }
        except Exception as e:
            logger.error(f"Error reading bin cache: {e}")
        finally:
            conn.close()
    return {}

def get_bot_stats() -> dict:
    with _db_lock:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Total users
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Total banned
            cursor.execute("SELECT COUNT(*) FROM users WHERE banned = 1")
            total_banned = cursor.fetchone()[0]
            
            # Total cards checked
            cursor.execute("SELECT SUM(count) FROM daily_usage")
            res = cursor.fetchone()[0]
            total_checks = res if res else 0
            
            return {
                "total_users": total_users,
                "total_banned": total_banned,
                "total_checks": total_checks
            }
        except Exception as e:
            logger.error(f"Error getting bot stats: {e}")
            return {"total_users": 0, "total_banned": 0, "total_checks": 0}
        finally:
            conn.close()


def db_add_charge_reward(user_id):
    uid_str = str(user_id)
    from datetime import datetime, timedelta
    with _db_lock:
        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute('SELECT premium, charged_count FROM users WHERE user_id = ?', (uid_str,))
                row = cursor.fetchone()
                if not row:
                    return False
                count = row['charged_count'] or 0
                count += 1
                if count >= 10:
                    cursor.execute('UPDATE users SET charged_count = 0 WHERE user_id = ?', (uid_str,))
                    return True
                else:
                    cursor.execute('UPDATE users SET charged_count = ? WHERE user_id = ?', (count, uid_str))
                    return False
        except Exception as e:
            logger.error(f'Error tracking charge reward for {uid_str}: {e}')
            return False
