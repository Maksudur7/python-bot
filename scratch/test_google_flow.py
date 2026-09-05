import asyncio
import os
import re
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.abspath("bot_user_data")

async def test_google_signin(phone_number="+18184443214", sample_name="John Doe"):
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
        
        print("1. Navigating to Google Sign-In...")
        await page.goto("https://accounts.google.com/v3/signin/identifier", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # Identifier input
        inp = page.locator("input[type='email'], input[name='identifier'], #identifierId").first
        if await inp.is_visible():
            print(f"2. Filling phone number {phone_number}...")
            await inp.fill(phone_number)
            await asyncio.sleep(0.5)

            # Click Next
            next_btn = page.locator("#identifierNext, button:has-text('Next'), button:has-text('Далее')").first
            if await next_btn.is_visible():
                print("3. Clicking Next button...")
                await next_btn.click()
            else:
                print("Pressing Enter...")
                await page.keyboard.press("Enter")
            
            await asyncio.sleep(3)

            content = await page.content()
            title = await page.title()
            print("4. Current Title:", title)
            print("5. Current URL:", page.url)

            # Check if Error (No account)
            no_acc = any(err in content for err in ["Could not find your Google Account", "Couldn't find your Google Account", "Enter a valid email"])
            print("No Google Account Error:", no_acc)

            # Check if Direct Password requested
            pwd_field = page.locator("input[type='password'], input[name='Passwd'], #password")
            pwd_visible = await pwd_field.is_visible() if await pwd_field.count() > 0 else False
            print("Direct Password requested:", pwd_visible)

            # Check if Name requested (first name / last name)
            fname_field = page.locator("input[name='firstName'], #firstName")
            fname_visible = await fname_field.is_visible() if await fname_field.count() > 0 else False
            print("First Name requested:", fname_visible)

            os.makedirs("scratch", exist_ok=True)
            with open("scratch/google_login_page.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("Saved scratch/google_login_page.html")
        else:
            print("Identifier input field not visible!")

        await context.close()

if __name__ == "__main__":
    asyncio.run(test_google_signin())
