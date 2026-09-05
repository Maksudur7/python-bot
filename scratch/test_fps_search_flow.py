import asyncio
import os
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.abspath("bot_user_data")

async def test_fps_form_submission(phone_raw="3188854611"):
    phone_clean = re.sub(r"\D", "", phone_raw)[-10:]
    
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

        # Step 1: Go to FastPeopleSearch homepage
        print("1. Navigating to FastPeopleSearch Homepage: https://www.fastpeoplesearch.com/")
        await page.goto("https://www.fastpeoplesearch.com/", wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(2)

        # Cloudflare Turnstile wait loop for homepage
        max_attempts = 20
        warned = False
        for cf_attempt in range(max_attempts):
            content_check = await page.content()
            if any(k in content_check for k in ["challenges.cloudflare.com", "Just a moment...", "Verify you are human"]):
                if not warned:
                    print("CLOUDFLARE TURNSTILE DETECTED on FastPeopleSearch Homepage!")
                    print("Please click Turnstile checkbox in Chrome if needed.")
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
                print("Cloudflare Turnstile CLEARED on Homepage!")
                break

        await asyncio.sleep(1)

        # Step 2: Click PHONE option tab
        print("2. Clicking PHONE tab (#search-nav-link-phone)...")
        phone_tab = page.locator("#search-nav-link-phone")
        if await phone_tab.is_visible():
            await phone_tab.click()
            await asyncio.sleep(0.5)
        else:
            print("PHONE tab element not visible!")

        # Step 3: Fill phone number
        print(f"3. Filling phone input (#search-phone-phone) with {phone_clean}...")
        phone_inp = page.locator("#search-phone-phone")
        await phone_inp.fill(phone_clean)
        await asyncio.sleep(0.5)

        # Step 4: Click Submit Search
        print("4. Submitting form (#form-search-phone button[type='submit'])...")
        submit_btn = page.locator("#form-search-phone button[type='submit']")
        await submit_btn.click()

        # Step 5: Wait for search result page navigation & Cloudflare check
        print("5. Waiting for results page...")
        await asyncio.sleep(5)

        # Result page Cloudflare loop
        for cf_attempt in range(max_attempts):
            content_check = await page.content()
            if any(k in content_check for k in ["challenges.cloudflare.com", "Just a moment...", "Verify you are human"]):
                if not warned:
                    print("CLOUDFLARE TURNSTILE DETECTED on Results Page!")
                    warned = True
                print(f"Waiting for Result Turnstile clearance... [{cf_attempt+1}/{max_attempts}]")
                await asyncio.sleep(3)
            else:
                print("Cloudflare Turnstile CLEARED on Results Page!")
                break

        await asyncio.sleep(2)

        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        
        print("Current URL:", page.url)

        with open("scratch/fps_form_results.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("Saved scratch/fps_form_results.html")

        # Inspect parsed details
        title = soup.find("title").get_text() if soup.find("title") else ""
        print("Page Title:", title)

        # FastPeopleSearch result cards
        cards = soup.select(".card, .search-item, .people-card, [class*='card']")
        print("Card count:", len(cards))

        headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3", "h4", "a"]) if len(h.get_text(strip=True)) > 2][:20]
        print("Headings sample:", headings)

        await context.close()

if __name__ == "__main__":
    asyncio.run(test_fps_form_submission("3188854611"))
