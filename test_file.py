import asyncio
import telegram
from bot.core.config import TOKEN

async def test():
    bot = telegram.Bot(TOKEN)
    # We just want to inspect the File class methods
    print(dir(telegram.File))

asyncio.run(test())
