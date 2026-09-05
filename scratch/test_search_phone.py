import asyncio
import os
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.abspath("bot_user_data")

async def test_search_phone(phone="8184443214"):
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
        
        url = "https://www.fastpeoplesearch.com/"
        print(f"1. Navigating to {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        print("2. Clicking PHONE tab (#search-nav-link-phone)...")
        phone_tab = page.locator("#search-nav-link-phone")
        if await phone_tab.is_visible():
            await phone_tab.click()
            await asyncio.sleep(1)
        else:
            print("PHONE tab not visible!")

        print(f"3. Filling phone input (#search-phone-phone) with {phone}...")
        phone_inp = page.locator("#search-phone-phone")
        await phone_inp.fill(phone)
        await asyncio.sleep(0.5)

        print("4. Submitting search...")
        submit_btn = page.locator("#form-search-phone button[type='submit']")
        await submit_btn.click()
        
        await asyncio.sleep(5)

        print("Current URL:", page.url)
        content = await page.content()
        
        # Save results HTML
        os.makedirs("scratch", exist_ok=True)
        with open("scratch/fps_result.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("Saved scratch/fps_result.html")

        soup = BeautifulSoup(content, "html.parser")
        
        # Check Cloudflare
        cf = any(k in content for k in ["challenges.cloudflare.com", "Just a moment...", "Verify you are human", "Attention Required"])
        print("Cloudflare / Security block:", cf)

        # Print extracted text snippets
        records = soup.select(".card, .search-item, .people-card, .record-item, [class*='card'], [class*='result']")
        print(f"Total candidate result elements: {len(records)}")

        # Check titles / headings / names
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3", "h4", "a"]) if "view" in h.get_text(strip=True).lower() or "person" in h.get_text(strip=True).lower() or "detail" in h.get_text(strip=True).lower() or "phone" in h.get_text(strip=True).lower()]
        print("Headings/Links preview:", headings[:10])

        await context.close()

if __name__ == "__main__":
    asyncio.run(test_search_phone("8184443214"))
