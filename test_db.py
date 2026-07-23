import sys
import os

sys.path.append(os.path.abspath('.'))

try:
    from bot.utils.db import DB_FILE, init_db
    print("DB_FILE IS:", DB_FILE)
    if not os.path.exists(os.path.dirname(DB_FILE)):
        print("Creating DIR:", os.path.dirname(DB_FILE))
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    init_db()
    print("DB Init Successful!")
except Exception as e:
    import traceback
    traceback.print_exc()
