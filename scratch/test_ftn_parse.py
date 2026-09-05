import os
import sys
import asyncio
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from automation_bot import SMSBowerBot
from playwright.async_api import async_playwright

async def inspect_ftn_results():
    bot = SMSBowerBot()
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

        page = await context.new_page()
        # Search a known phone number
        url = "https://www.familytreenow.com/search/genealogy/results?searchtype=phone&phone=3188854611"
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(4)

        # Handle turnstile if needed
        for _ in range(3):
            tf = page.frame(url=r"challenges.cloudflare.com")
            if tf:
                cb = await tf.query_selector("input[type='checkbox'], .ctp-checkbox_label, body")
                if cb:
                    box = await cb.bounding_box()
                    if box:
                        await page.mouse.move(box["x"] + box["width"]/2, box["y"] + box["height"]/2, steps=5)
                        await page.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                    await asyncio.sleep(3)
            content = await page.content()
            if "challenges.cloudflare.com" not in content and "Just a moment..." not in content:
                break

        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        
        print("Page Title:", await page.title())
        # Print headings or result cards
        cards = soup.select(".record, .card, table tr, .record-container, .panel")
        print(f"Total potential result containers found: {len(cards)}")
        for idx, card in enumerate(cards[:5]):
            print(f"--- Card {idx+1} ---")
            print(card.get_text(strip=True)[:200])

        await context.close()

if __name__ == "__main__":
    asyncio.run(inspect_ftn_results())
