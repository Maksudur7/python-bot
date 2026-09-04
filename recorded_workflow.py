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
    page1 = await context.new_page()
    await page1.goto("chrome://new-tab-page/")
    await page1.goto("https://www.familytreenow.com/search/genealogy/results?searchtype=phone&phone=3188854611")
    await page1.locator("iframe[src=\"https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile/f/av0/rch/bfgbs/0x4AAAAAAADnPIDROrmt1Wwj/light/fbE/new/normal?lang=auto\"]").content_frame.locator("body").click()
    await page1.goto("https://www.familytreenow.com/search/genealogy/results?searchtype=phone&phone=3188854611")
    await page1.locator("iframe[src=\"https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile/f/av0/rch/80hl8/0x4AAAAAAADnPIDROrmt1Wwj/light/fbE/new/normal?lang=auto\"]").content_frame.locator("body").click()
    await page1.goto("https://www.familytreenow.com/search/genealogy/results?searchtype=phone&phone=3188854611")
    await page1.locator("iframe[src=\"https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile/f/av0/rch/9espj/0x4AAAAAAADnPIDROrmt1Wwj/light/fbE/new/normal?lang=auto\"]").content_frame.locator("body").click()
    await page1.goto("https://www.familytreenow.com/search/genealogy/results?searchtype=phone&phone=3188854611")
    page2 = await context.new_page()
    await page2.goto("chrome://new-tab-page/")
    await page1.close()
    await page2.goto("https://www.google.com/search?q=familytreenow&oq=f&gs_lcrp=EgZjaHJvbWUqBggCECMYJzIGCAAQRRg8MgYIARBFGDkyBggCECMYJzIGCAMQIxgnMgYIBBBFGDwyBggFEEUYPDIGCAYQRRg9MgYIBxBFGD3SAQgzNDI3ajBqN6gCALACAA&sourceid=chrome&source=chrome.ob&ie=UTF-8")
    await page2.get_by_role("link", name="FamilyTreeNow.com: Free").click()
    await page2.locator("iframe[src=\"https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile/f/av0/rch/tmfwh/0x4AAAAAAADnPIDROrmt1Wwj/light/fbE/new/normal?lang=auto\"]").content_frame.locator("body").click()
    await page2.goto("https://www.familytreenow.com/")
    await page2.locator("iframe[src=\"https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile/f/av0/rch/5k4rr/0x4AAAAAAADnPIDROrmt1Wwj/light/fbE/new/normal?lang=auto\"]").content_frame.locator("body").click()
    await page2.goto("https://www.familytreenow.com/")

    # ---------------------
    await context.close()
    await browser.close()


async def main() -> None:
    async with async_playwright() as playwright:
        await run(playwright)


asyncio.run(main())
