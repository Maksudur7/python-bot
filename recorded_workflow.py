import asyncio
import re
from playwright.async_api import Playwright, async_playwright, expect


async def run(playwright: Playwright) -> None:
    browser = await playwright.chromium.launch(channel="chrome", headless=False)
    context = await browser.new_context()
    await page.goto("https://smsbower.app/cabinet/client/phonehistory")
    await page.locator("div:nth-child(9) > .img-radius-1").click()
    await page.get_by_text("Gold", exact=True).click()
    await page.get_by_role("textbox", name="Find country").click()
    await page.get_by_role("textbox", name="Find country").fill("usa")
    await page.locator("div:nth-child(2) > .phone-country-item-body > .phone-country-item-show-hide-btn").click()
    await page.get_by_text("0.75 $", exact=True).click()
    await page.locator(".--copy > img").click()
    await page.close()

    # ---------------------
    await context.close()
    await browser.close()


async def main() -> None:
    async with async_playwright() as playwright:
        await run(playwright)


asyncio.run(main())
