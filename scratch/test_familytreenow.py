import asyncio
import os
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.abspath("bot_user_data")

async def test_familytreenow():
    async with async_playwright() as p:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--start-maximized"
        ]

        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
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

        page = context.pages[0] if context.pages else await context.new_page()
        
        url = "https://www.familytreenow.com/search/genealogy/results?searchtype=phone&phone=3188854611"
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(5)

        title = await page.title()
        content = await page.content()
        cookies = await context.cookies()
        
        print("Page Title:", title)
        print("Cookies:", [c["name"] for c in cookies])
        print("Contains Cloudflare challenge:", "challenges.cloudflare.com" in content or "Just a moment..." in content)

        # Check if Turnstile iframe exists
        frames = page.frames
        print("Total frames:", len(frames))
        for f in frames:
            print("Frame URL:", f.url)

        await asyncio.sleep(10)
        await context.close()

if __name__ == "__main__":
    asyncio.run(test_familytreenow())
