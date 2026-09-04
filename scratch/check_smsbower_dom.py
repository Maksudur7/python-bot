import asyncio
import os
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.abspath("bot_user_data")

async def test_full_sequence():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        print("1. Navigating to SMSBower...")
        await page.goto("https://smsbower.app/cabinet/client/phonehistory", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        # Step 1: Select Service -> Google
        print("2. Selecting service Google...")
        box = page.get_by_role("combobox").get_by_text("Select service")
        if await box.is_visible():
            await box.click()
            await asyncio.sleep(0.5)
            await page.get_by_role("textbox", name="Select service").fill("google")
            await asyncio.sleep(0.8)
            opt = page.get_by_role("option", name="Google, Gmail, Youtube go")
            if await opt.is_visible():
                await opt.click()
                print("Selected Google service!")
            else:
                await page.keyboard.press("Enter")
        else:
            s_inp = await page.query_selector("input[placeholder*='Select service'], .multiselect")
            if s_inp:
                await s_inp.click()
                await s_inp.fill("google")
                await asyncio.sleep(0.8)
                await page.keyboard.press("Enter")

        await asyncio.sleep(1)

        # Step 2: Select Rank -> Gold
        print("3. Selecting Rank Gold...")
        gold_btn = page.get_by_text("Gold", exact=True)
        if await gold_btn.is_visible():
            await gold_btn.click()
            print("Selected Gold rank!")

        await asyncio.sleep(1)

        # Step 3: Search country -> usa
        print("4. Searching country usa...")
        c_inp = page.get_by_role("textbox", name="Find country")
        if await c_inp.is_visible():
            await c_inp.click()
            await c_inp.fill("usa")
            print("Filled usa in country search.")
        else:
            c_inp2 = await page.query_selector("input[placeholder*='Find country']")
            if c_inp2:
                await c_inp2.fill("usa")

        await asyncio.sleep(1.5)

        # Step 4: Click Select dropdown on 2nd USA card (USA Physical)
        items = page.locator(".phone-country-item")
        count = await items.count()
        print(f"5. Country cards found: {count}")
        for i in range(count):
            print(f"   Card {i+1}: {await items.nth(i).inner_text()}")

        if count >= 2:
            card2 = items.nth(1)
            select_btn = card2.locator(".phone-country-item-show-hide-btn, text='Select', button:has-text('Select')").first
            if await select_btn.is_visible():
                print("6. Clicking Select button on 2nd USA card (USA Physical)...")
                await select_btn.click()
                await asyncio.sleep(2)
                
                # Check for 0.75 $ button/text
                offer_075 = page.get_by_text("0.75 $", exact=True)
                print("7. Is '0.75 $' offer visible?", await offer_075.is_visible())
                if not await offer_075.is_visible():
                    print("Checking all elements containing '0.75':")
                    all_075 = page.locator("text=0.75")
                    for k in range(await all_075.count()):
                        el = all_075.nth(k)
                        print(f"   [{k}] tag={await el.evaluate('e=>e.tagName')}, text='{await el.inner_text()}'")
            else:
                print("Select button on 2nd card not visible!")

        await context.close()

if __name__ == "__main__":
    asyncio.run(test_full_sequence())
