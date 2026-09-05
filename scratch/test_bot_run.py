import os
import sys
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from automation_bot import SMSBowerBot
from playwright.async_api import async_playwright

async def test_bot():
    bot = SMSBowerBot()
    bot.headless = False
    bot.target_numbers = 1
    
    print("============================================================")
    print("Testing 1 Cycle of FamilyTreeNow Stealth Search...")
    print("============================================================")
    
    user_data_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "bot_user_data"))
    async with async_playwright() as p:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--start-maximized"
        ]
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            channel="chrome",
            ignore_default_args=["--enable-automation"],
            args=launch_args
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = window.chrome || { runtime: {} };
        """)

        ftn_page = await context.new_page()
        test_phone = "3188854611"
        print(f"Executing FamilyTreeNow stealth search for phone: {test_phone}...")
        res = await bot._search_familytreenow(ftn_page, test_phone)
        print("FamilyTreeNow Search Result:", res)

        await asyncio.sleep(5)
        await context.close()

if __name__ == "__main__":
    asyncio.run(test_bot())
