import asyncio
import os
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.abspath("bot_user_data")

async def test_exact():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        print("Navigating to SMSBower...")
        await page.goto("https://smsbower.app/cabinet/client/phonehistory", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        print("Testing exact recorded steps:")
        
        # Step 1: Select Service -> Google
        try:
            print("Step 1: Clicking Select service combobox...")
            box = page.get_by_role("combobox").get_by_text("Select service")
            await box.click()
            await asyncio.sleep(0.5)
            
            print("Filling 'google'...")
            s_input = page.get_by_role("textbox", name="Select service")
            await s_input.fill("google")
            await asyncio.sleep(0.8)
            
            print("Clicking option 'Google, Gmail, Youtube go'...")
            opt = page.get_by_role("option", name="Google, Gmail, Youtube go")
            await opt.click()
            print("-> Service Google selected successfully!")
        except Exception as e:
            print(f"-> Step 1 Error: {e}")

        await asyncio.sleep(1)

        # Step 2: Click Rank Gold
        try:
            print("Step 2: Clicking 'Gold' rank filter...")
            gold = page.get_by_text("Gold", exact=True)
            await gold.click()
            print("-> Rank Gold selected successfully!")
        except Exception as e:
            print(f"-> Step 2 Error: {e}")

        await asyncio.sleep(1)

        # Step 3: Search country usa
        try:
            print("Step 3: Searching country 'usa'...")
            c_box = page.get_by_role("textbox", name="Find country")
            await c_box.click()
            await c_box.fill("usa")
            print("-> Country 'usa' filled successfully!")
        except Exception as e:
            print(f"-> Step 3 Error: {e}")

        await asyncio.sleep(1.5)

        # Step 4: Click 2nd USA card select dropdown
        try:
            print("Step 4: Clicking 2nd USA card Select dropdown...")
            dropdown2 = page.locator("div:nth-child(2) > .phone-country-item-body > .phone-country-select > .app-select > .app-select__control > .app-select__value-container")
            if not await dropdown2.is_visible():
                print("Exact recorded dropdown locator not visible, trying fallback inside 2nd card...")
                items = page.locator(".phone-country-item, .phone-country-item-body")
                if await items.count() >= 2:
                    dropdown2 = items.nth(1).locator(".phone-country-item-show-hide-btn, .phone-country-select, [class*='select']").first
            
            await dropdown2.click()
            print("-> 2nd USA card Select dropdown clicked successfully!")
        except Exception as e:
            print(f"-> Step 4 Error: {e}")

        await asyncio.sleep(1.5)

        # Step 5: Click 0.75 $
        try:
            print("Step 5: Clicking '0.75 $' offer button...")
            offer_btn = page.get_by_text("0.75 $", exact=True)
            if not await offer_btn.is_visible():
                print("Exact 0.75 $ text not visible, checking visible text containing 0.75...")
                offer_btn = page.locator("text=0.75").first
            await offer_btn.click()
            print("-> Offer 0.75 $ clicked successfully!")
        except Exception as e:
            print(f"-> Step 5 Error: {e}")

        await context.close()

if __name__ == "__main__":
    asyncio.run(test_exact())
