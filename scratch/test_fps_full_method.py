import asyncio
import os
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.abspath("bot_user_data")

async def search_fastpeoplesearch(page, phone_10):
    phone_clean = re.sub(r"\D", "", phone_10)[-10:]
    phone_formatted = f"{phone_clean[:3]}-{phone_clean[3:6]}-{phone_clean[6:]}" if len(phone_clean) == 10 else phone_clean
    
    url = "https://www.fastpeoplesearch.com/"
    try:
        print(f"Navigating to FastPeopleSearch homepage: {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(1.5)

        # Step 1: Turnstile check on homepage
        max_captcha_attempts = 20
        warned_user = False
        for cf_attempt in range(max_captcha_attempts):
            content_check = await page.content()
            if any(k in content_check for k in ["challenges.cloudflare.com", "Just a moment...", "Verify you are human"]):
                if not warned_user:
                    print("⚠️ CLOUDFLARE TURNSTILE DETECTED on FastPeopleSearch!")
                    print("👉 Please click the Turnstile checkbox 1 TIME manually in Chrome if needed.")
                    warned_user = True
                
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
                    pass
                await asyncio.sleep(2.5)
            else:
                print("✅ Cloudflare Turnstile cleared on FastPeopleSearch homepage!")
                break

        # Step 2: Select PHONE option tab
        print("Selecting PHONE tab option...")
        phone_tab = page.locator("#search-nav-link-phone, a[data-target='#search-type-container-phone'], text='PHONE'")
        if await phone_tab.first.is_visible():
            await phone_tab.first.click()
            await asyncio.sleep(0.5)

        # Step 3: Enter phone number
        print(f"Filling phone input field with number: {phone_formatted}...")
        phone_inp = page.locator("#search-phone-phone, input[name='phone']").first
        if await phone_inp.is_visible():
            await phone_inp.fill(phone_formatted)
            await asyncio.sleep(0.5)
            
            # Click search button
            submit_btn = page.locator("#form-search-phone button[type='submit'], #form-search-phone .search-form-button-submit").first
            if await submit_btn.is_visible():
                await submit_btn.click()
                await asyncio.sleep(3)
        else:
            # Direct fallback navigation
            print(f"Direct phone URL fallback: https://www.fastpeoplesearch.com/phone/{phone_formatted}")
            await page.goto(f"https://www.fastpeoplesearch.com/phone/{phone_formatted}", wait_until="domcontentloaded")

        # Step 4: Turnstile check on results page
        for cf_attempt in range(max_captcha_attempts):
            content_check = await page.content()
            if any(k in content_check for k in ["challenges.cloudflare.com", "Just a moment...", "Verify you are human"]):
                if not warned_user:
                    print("⚠️ CLOUDFLARE TURNSTILE DETECTED on FastPeopleSearch Results Page!")
                    warned_user = True
                
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
                    pass
                await asyncio.sleep(2.5)
            else:
                break

        await asyncio.sleep(2)

        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        page_text = soup.get_text()

        if "0 People Records" in page_text or "No records found" in page_text or "404" in page_text or "0 Records" in page_text:
            print(f"FastPeopleSearch result: No matching record for {phone_10}.")
            return {"found": False}

        # Extract details
        name_el = soup.select_one(".card-title, .record-name, a[href*='name'], h2.card-title, .people-card h2, a.link-to-details, h2, h3")
        name = name_el.get_text(strip=True) if name_el else ""

        age_el = soup.select_one(".age, span[class*='age']")
        age = age_el.get_text(strip=True) if age_el else ""

        loc_el = soup.select_one(".location, .address, span[class*='location'], a[href*='address']")
        location = loc_el.get_text(strip=True) if loc_el else ""

        relatives_els = soup.select("a[href*='name'], .relatives a, a[href*='relative']")
        relatives = ", ".join([r.get_text(strip=True) for r in relatives_els[:5]]) if relatives_els else ""

        if name or "Full Name" in page_text or "Current Address" in page_text:
            result = {
                "found": True,
                "name": name if name else "Person Record Found",
                "age": age,
                "location": location,
                "relatives": relatives
            }
            print("Extracted Result:", result)
            return result

    except Exception as e:
        print(f"FastPeopleSearch lookup warning: {e}")

    return {"found": False}

async def run_test():
    async with async_playwright() as p:
        launch_args = ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"]
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            channel="chrome",
            ignore_default_args=["--enable-automation"],
            args=launch_args
        )
        page = context.pages[0] if context.pages else await context.new_page()
        res = await search_fastpeoplesearch(page, "3188854611")
        print("Final Test Result:", res)
        await context.close()

if __name__ == "__main__":
    asyncio.run(run_test())
