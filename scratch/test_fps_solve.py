import asyncio
import os
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.abspath("bot_user_data")

async def test_search_fastpeoplesearch(phone_10="8184443214"):
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
        
        # Navigate to homepage
        print("1. Navigating to https://www.fastpeoplesearch.com/...")
        await page.goto("https://www.fastpeoplesearch.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # Select PHONE tab
        print("2. Selecting PHONE option/tab...")
        phone_tab = page.locator("#search-nav-link-phone")
        if await phone_tab.is_visible():
            await phone_tab.click()
            await asyncio.sleep(0.5)

        # Fill phone number
        print(f"3. Filling phone number {phone_10}...")
        phone_inp = page.locator("#search-phone-phone")
        if await phone_inp.is_visible():
            await phone_inp.fill(phone_10)
            await asyncio.sleep(0.5)
            submit_btn = page.locator("#form-search-phone button[type='submit']")
            await submit_btn.click()
        else:
            # Direct URL fallback
            print("Direct navigation fallback...")
            await page.goto(f"https://www.fastpeoplesearch.com/{phone_10}", wait_until="domcontentloaded")

        # Persistent Hybrid Wait Loop: Wait for Turnstile pass (auto-click + manual fallback)
        max_attempts = 15
        warned = False
        for cf_attempt in range(max_attempts):
            content_check = await page.content()
            if any(k in content_check for k in ["challenges.cloudflare.com", "Just a moment...", "Verify you are human"]):
                if not warned:
                    print("CLOUDFLARE TURNSTILE DETECTED on FastPeopleSearch!")
                    print("Click Turnstile checkbox if present.")
                    warned = True
                else:
                    print(f"Waiting for Turnstile clearance... [{cf_attempt+1}/{max_attempts}]")

                try:
                    turnstile_frame = page.frame(url=re.compile(r"challenges\.cloudflare\.com"))
                    if turnstile_frame:
                        cb = await turnstile_frame.query_selector("input[type='checkbox'], .ctp-checkbox_label, body")
                        if cb:
                            box = await cb.bounding_box()
                            if box:
                                await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=6)
                                await asyncio.sleep(0.2)
                                await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                            else:
                                await cb.click()
                except Exception as cf_err:
                    print(f"Turnstile note: {cf_err}")

                await asyncio.sleep(3)
            else:
                print("Cloudflare Turnstile CLEARED SUCCESSFULLY!")
                break

        await asyncio.sleep(2)
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        
        # Save snapshot
        with open("scratch/fps_cleared_result.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("Saved scratch/fps_cleared_result.html")

        # Inspect cards / person details
        people = soup.select(".card, .search-item, .people-card, .record-item, [class*='card-title']")
        print("Found element count:", len(people))
        
        # Look for text like name, age, address
        for el in soup.select("h2, h3, .card-title, a[href*='person'], a[href*='name']"):
            txt = el.get_text(strip=True)
            if txt:
                print("Extracted item title:", txt)

        await context.close()

if __name__ == "__main__":
    asyncio.run(test_search_fastpeoplesearch("8184443214"))
