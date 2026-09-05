import asyncio
import os
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.abspath("bot_user_data")

async def test_fastpeoplesearch():
    async with async_playwright() as p:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--start-maximized"
        ]

        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False,
                channel="chrome",
                ignore_default_args=["--enable-automation"],
                args=launch_args
            )
        except Exception as e:
            print("Launch channel='chrome' failed:", e)
            return

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = window.chrome || { runtime: {} };
        """)

        page = context.pages[0] if context.pages else await context.new_page()
        
        url = "https://www.fastpeoplesearch.com/"
        print(f"Navigating to {url}...")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            title = await page.title()
            content = await page.content()
            
            print("Page Title:", title)
            print("Contains Cloudflare/Security:", any(k in content for k in ["cloudflare", "Just a moment...", "Verify you are human", "Attention Required"]))
            
            # Save HTML snapshot to inspect inputs/tabs
            os.makedirs("scratch", exist_ok=True)
            with open("scratch/fps_home.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("Saved scratch/fps_home.html")
            
        except Exception as e:
            print("Error navigating:", e)

        await context.close()

if __name__ == "__main__":
    asyncio.run(test_fastpeoplesearch())
