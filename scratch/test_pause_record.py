import asyncio
from playwright.async_api import async_playwright
import os

async def test_record():
    user_data_dir = os.path.join(os.path.dirname(__file__), "bot_user_data")
    os.makedirs(user_data_dir, exist_ok=True)
    
    # Remove stale locks
    for lock in ["SingletonLock", "lockfile"]:
        lp = os.path.join(user_data_dir, lock)
        if os.path.exists(lp):
            try: os.remove(lp)
            except: pass

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            channel="chrome",
            no_viewport=True,
            ignore_default_args=["--enable-automation"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://smsbower.app/cabinet/client/phonehistory")
        print("Browser launched! Opening inspector pause...")
        await page.pause()
        await context.close()

if __name__ == "__main__":
    asyncio.run(test_record())
