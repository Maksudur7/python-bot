import asyncio
import os
import re
import time
import logging
import threading
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class SMSBowerBot:
    def __init__(self):
        self.is_running = False
        self.headless = False
        self.thread = None
        self.loop = None
        self.logs = []
        self.max_logs = 100
        self.current_context = None
        
        # Metrics
        self.numbers_checked = 0
        self.records_saved = 0
        self.cancelled_cost = 0
        self.target_numbers = 10
        self.current_status = "IDLE"
        self.user_data_dir = os.path.join(os.path.dirname(__file__), "bot_user_data")
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        logging.info(message)
        self.logs.append(entry)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

    def start(self, headless=False):
        if self.is_running:
            return False
        del self.logs[:]
        self.is_running = True
        self.headless = headless
        self.current_status = "STARTING"
        self.records_saved = database.get_record_count()
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        if not self.is_running:
            return False
        self.is_running = False
        self.current_status = "STOPPING"
        self.log("Stop requested. Closing browser session immediately...")
        
        # Force close browser context if loop is running
        if self.loop and self.current_context:
            asyncio.run_coroutine_threadsafe(self._force_close_context(), self.loop)
        return True

    async def _force_close_context(self):
        try:
            if self.current_context:
                await self.current_context.close()
                self.current_context = None
        except Exception:
            pass

    async def _sleep_check(self, seconds):
        steps = int(seconds / 0.2)
        for _ in range(max(1, steps)):
            if not self.is_running:
                break
            await asyncio.sleep(0.2)

    def _run_async_loop(self):
        self.logs.clear()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.main_workflow())
        except Exception as e:
            self.log(f"Bot loop exception: {e}")
        finally:
            self.is_running = False
            self.current_status = "IDLE"
            self.current_context = None
            self.log("Bot stopped successfully.")

    async def main_workflow(self):
        self.log(f"Initializing Playwright Engine (Headless: {self.headless})...")
        os.makedirs(self.user_data_dir, exist_ok=True)

        # Remove stale lock files if previous process crashed or was terminated
        for lock_name in ["SingletonLock", "lockfile", "SingletonCookie", "SingletonSocket"]:
            lock_path = os.path.join(self.user_data_dir, lock_name)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                except Exception:
                    pass

        while self.is_running:
            try:
                async with async_playwright() as p:
                    self.log("Launching persistent Chromium browser session...")
                    try:
                        context = await p.chromium.launch_persistent_context(
                            user_data_dir=self.user_data_dir,
                            headless=self.headless,
                            channel="chrome",
                            viewport={"width": 1366, "height": 768},
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                            args=[
                                "--disable-blink-features=AutomationControlled",
                                "--no-sandbox",
                                "--disable-setuid-sandbox",
                                "--disable-dev-shm-usage",
                                "--disable-gpu",
                                "--js-flags=--max-old-space-size=256"
                            ]
                        )
                    except Exception as launch_err:
                        self.log(f"Browser launch warning: {launch_err}. Retrying clean profile launch...")
                        # Remove lock again and retry once
                        for lock_name in ["SingletonLock", "lockfile"]:
                            lp = os.path.join(self.user_data_dir, lock_name)
                            if os.path.exists(lp):
                                try: os.remove(lp)
                                except Exception: pass
                        context = await p.chromium.launch_persistent_context(
                            user_data_dir=self.user_data_dir,
                            headless=self.headless,
                            channel="chrome",
                            viewport={"width": 1366, "height": 768},
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                            args=[
                                "--disable-blink-features=AutomationControlled",
                                "--disable-dev-shm-usage",
                                "--disable-gpu",
                                "--js-flags=--max-old-space-size=256"
                            ]
                        )

                    self.current_context = context
                    
                    page = context.pages[0] if context.pages else await context.new_page()
                    await page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    """)

                    self.current_status = "RUNNING"
                    self.log("Navigating to SMSBower Web Cabinet...")
                    
                    try:
                        await page.goto("https://smsbower.app/cabinet/client/phonehistory", wait_until="domcontentloaded", timeout=40000)
                    except Exception as e:
                        self.log(f"Navigation note: {e}")

                    while self.is_running:
                        try:
                            self.log("Step 1: Checking SMSBower cabinet page status...")
                            current_url = page.url.lower()
                            if "login" in current_url or "auth" in current_url or "signin" in current_url:
                                self.log(f"⚠️ LOGIN REQUIRED: SMSBower redirected to login page ({page.url}).")
                                self.log("👉 Please check '👁️ Watch Live Browser Window' on dashboard and log into your SMSBower account.")
                                await self._sleep_check(5)
                                continue

                            if "phonehistory" not in current_url:
                                try:
                                    await page.goto("https://smsbower.app/cabinet/client/phonehistory", wait_until="domcontentloaded", timeout=40000)
                                except Exception as e:
                                    self.log(f"Redirect note: {e}")
                            
                            await self._sleep_check(0.1)
                            if not self.is_running: break
                            
                            # Step 2: Clear Stale Active Cards
                            self.log("Step 2: Clearing any pre-existing active order cards...")
                            await self._clear_active_cards(page)
                            if not self.is_running: break

                            # Step 3: Select Service (Google / Gmail - go)
                            self.log("Step 3: Selecting Service -> Google / Gmail (go)...")
                            service_selected = await self._select_service(page)
                            if not service_selected:
                                self.log("Warning: Service selector not clicked directly, attempting fallback...")
                            if not self.is_running: break

                            # Step 4: Select Position Rank (Gold)
                            self.log("Step 4: Selecting Position Rank -> Gold...")
                            await self._select_rank(page, "Gold")
                            if not self.is_running: break

                            # Step 5: Select Country (2nd USA Option - USA Physical)
                            self.log("Step 5: Searching country 'usa' & selecting USA Physical...")
                            await self._select_country(page)
                            if not self.is_running: break

                            # Step 6: Locate & Click Rank #3170 ($0.75)
                            self.log("Step 6: Locating & clicking offer Gold #3170 ($0.75)...")
                            purchased = await self._buy_target_offer(page)
                            if purchased:
                                self.log("Successfully clicked offer buy button!")
                            else:
                                self.log("Target offer #3170 ($0.75) not immediately available or clicked fallback offer.")
                            if not self.is_running: break

                            await self._sleep_check(0.3)
                            if not self.is_running: break

                            # Step 7: Extract Acquired Phone Number
                            self.log("Step 7: Extracting acquired phone number from active order card...")
                            phone_number, order_id = await self._extract_active_phone(page)

                            if not phone_number:
                                self.log("No active phone number found on cabinet. Retrying iteration...")
                                await self._sleep_check(0.5)
                                continue

                            self.numbers_checked += 1
                            self.log(f"-> Acquired Phone Number: {phone_number} (Order ID: {order_id})")

                            # Clean phone number for 10-digit search
                            phone_clean = re.sub(r"\D", "", phone_number)
                            if phone_clean.startswith("1") and len(phone_clean) == 11:
                                phone_10 = phone_clean[1:]
                            else:
                                phone_10 = phone_clean[-10:] if len(phone_clean) >= 10 else phone_clean

                            if not self.is_running: break

                            # Step 8: FamilyTreeNow Search
                            self.log(f"Step 8: Searching FamilyTreeNow for number: {phone_10}...")
                            ftn_page = await context.new_page()
                            ftn_data = await self._search_familytreenow(ftn_page, phone_10)
                            await ftn_page.close()

                            if not self.is_running: break

                            google_status = "Not Tested"
                            if ftn_data.get("found"):
                                self.log(f"-> Match Found on FamilyTreeNow! Name: {ftn_data.get('name')}, Age: {ftn_data.get('age')}, Location: {ftn_data.get('location')}")
                                
                                # Step 9: Test Google Sign-In verification
                                self.log("Step 9: Verifying Google Sign-In with acquired number...")
                                google_page = await context.new_page()
                                google_status = await self._verify_google_signin(google_page, phone_number)
                                await google_page.close()
                                self.log(f"-> Google Sign-In Status: {google_status}")

                                # Save complete record
                                record = database.save_record(
                                    phone=phone_number,
                                    order_id=order_id,
                                    name=ftn_data.get("name", ""),
                                    age=ftn_data.get("age", ""),
                                    location=ftn_data.get("location", ""),
                                    relatives=ftn_data.get("relatives", ""),
                                    google_status=google_status
                                )
                                self.records_saved += 1
                                self.log(f"-> Record saved to database & CSV! Total saved: {self.records_saved}")
                            else:
                                self.log("-> No matching personal record found on FamilyTreeNow.")

                            if not self.is_running: break

                            # Step 10: SMSBower Cabinet Order Cancellation ($0 Cost Refund)
                            self.log("Step 10: Cancelling active order on SMSBower cabinet ($0 net charge refund)...")
                            cancelled = await self._cancel_order(page, order_id)
                            if cancelled:
                                self.cancelled_cost += 1
                                self.log(f"-> Order successfully cancelled! Total $0 refund cancellations: {self.cancelled_cost}")

                            self.log("Iteration complete. Fast cycle delay 0.3s...")
                            await self._sleep_check(0.3)

                            if self.target_numbers and self.numbers_checked >= self.target_numbers:
                                self.log(f"Target count of {self.target_numbers} numbers checked. Batch workflow finished successfully!")
                                self.is_running = False
                                break

                        except Exception as iter_err:
                            err_msg = str(iter_err)
                            if not self.is_running:
                                break
                            self.log(f"Error during bot iteration: {err_msg}")
                            if "closed" in err_msg.lower() or "target closed" in err_msg.lower():
                                self.log("Browser context connection lost. Re-initializing browser...")
                                break
                            await self._sleep_check(2)

                    try:
                        await context.close()
                    except Exception:
                        pass
                    self.current_context = None

            except Exception as context_err:
                if not self.is_running:
                    break
                self.log(f"Browser session error: {context_err}")
                await self._sleep_check(2)

    async def _clear_active_cards(self, page):
        try:
            cancel_buttons = await page.query_selector_all("button:has-text('Cancel'), button:has-text('Отмена'), .cancel-btn, [data-action='cancel']")
            for btn in cancel_buttons:
                try:
                    if await btn.is_visible():
                        await btn.click(timeout=3000)
                        await asyncio.sleep(0.5)
                except Exception:
                    pass
        except Exception as e:
            self.log(f"Note on clearing cards: {e}")

    async def _select_service(self, page):
        try:
            service_selectors = [
                "[data-service='go']",
                "[data-code='go']",
                ".service-item[data-code='go']",
                "div:has-text('Google')",
                "span:has-text('Google')",
                "img[alt*='Google']"
            ]
            for sel in service_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    await el.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    return True
            return False
        except Exception as e:
            self.log(f"Service select note: {e}")
            return False

    async def _select_rank(self, page, rank_name="Gold"):
        try:
            rank_selectors = [
                f"button:has-text('{rank_name}')",
                f"span:has-text('{rank_name}')",
                f".rank-filter:has-text('{rank_name}')",
                "[data-rank='gold']",
                "div:has-text('Gold')"
            ]
            for sel in rank_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    await el.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    return True
            return False
        except Exception as e:
            self.log(f"Rank select note: {e}")
            return False

    async def _select_country(self, page):
        try:
            search_inputs = [
                "input[placeholder*='Select country']",
                "input[placeholder*='Country']",
                "input[placeholder*='Search']",
                "input[type='search']",
                "input[type='text']"
            ]
            for inp_sel in search_inputs:
                inp = await page.query_selector(inp_sel)
                if inp and await inp.is_visible():
                    await inp.fill("usa")
                    await asyncio.sleep(0.5)
                    break
            
            select_btns = await page.query_selector_all("button:has-text('Select'), div:has-text('Select'), span:has-text('Select')")
            for btn in select_btns:
                try:
                    if await btn.is_visible():
                        await btn.click(timeout=3000)
                        await asyncio.sleep(0.5)
                except Exception:
                    pass
        except Exception as e:
            self.log(f"Country select note: {e}")

    async def _buy_target_offer(self, page):
        try:
            offer_selectors = [
                "button:has-text('0.75')",
                "button:has-text('0.75 $')",
                "button:has-text('$0.75')",
                "tr:has-text('3170') button",
                "div:has-text('3170') button",
                ".country-item:has-text('USA') button:has-text('Buy')",
                "button:has-text('Buy')"
            ]
            for sel in offer_selectors:
                btns = await page.query_selector_all(sel)
                for btn in btns:
                    if await btn.is_visible():
                        await btn.click(timeout=3000)
                        await asyncio.sleep(1)
                        return True
            return False
        except Exception as e:
            self.log(f"Buy offer note: {e}")
            return False

    async def _extract_active_phone(self, page):
        for attempt in range(6):
            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            
            raw_matches = re.findall(r"\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", soup.get_text())
            for raw in raw_matches:
                digits = re.sub(r"\D", "", raw)
                if len(digits) in (10, 11):
                    clean_phone = "+1" + digits[-10:]
                    order_ids = re.findall(r"ID:?\s*(\d+)", soup.get_text())
                    order_id = order_ids[0] if order_ids else f"ORD-{int(time.time())}"
                    return clean_phone, order_id

            await asyncio.sleep(0.8)

        return "", ""

    async def _search_familytreenow(self, page, phone_10):
        url = f"https://www.familytreenow.com/search/genealogy/results?searchtype=phone&phone={phone_10}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(2)
            
            # Auto-click Cloudflare Turnstile if encountered
            try:
                turnstile_frame = page.frame(url=re.compile(r"challenges\.cloudflare\.com"))
                if turnstile_frame:
                    cb = await turnstile_frame.query_selector("input[type='checkbox'], .recaptcha-checkbox")
                    if cb:
                        await cb.click()
                        await asyncio.sleep(2)
            except Exception:
                pass

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            page_text = soup.get_text()
            
            # Fallback if form input field is present
            if "Not enough criteria entered" in page_text or "Search Criteria" in page_text and "0 People Records" not in page_text:
                try:
                    inp = await page.query_selector("input[name='phone'], input[placeholder*='phone'], #phone")
                    if inp:
                        await inp.fill(phone_10)
                        btn = await page.query_selector("button:has-text('Search'), input[type='submit']")
                        if btn:
                            await btn.click()
                            await asyncio.sleep(3)
                            content = await page.content()
                            soup = BeautifulSoup(content, "html.parser")
                            page_text = soup.get_text()
                except Exception:
                    pass

            if "0 People Records" in page_text or "No records found" in page_text:
                return {"found": False}

            # Extract details
            name_el = soup.select_one(".detail-link, .record-name, a[href*='search/person']")
            name = name_el.get_text(strip=True) if name_el else ""

            age_el = soup.select_one(".age, span:contains('Age')")
            age = age_el.get_text(strip=True) if age_el else ""

            loc_el = soup.select_one(".location, .address, span:contains('Lives in')")
            location = loc_el.get_text(strip=True) if loc_el else ""

            relatives_els = soup.select(".relatives a, .relative-name")
            relatives = ", ".join([r.get_text(strip=True) for r in relatives_els[:5]]) if relatives_els else ""

            if name and "No records" not in name and "Search" not in name:
                return {
                    "found": True,
                    "name": name,
                    "age": age,
                    "location": location,
                    "relatives": relatives
                }
        except Exception as e:
            self.log(f"FamilyTreeNow lookup warning: {e}")

        return {"found": False}

    async def _verify_google_signin(self, page, phone_number):
        try:
            await page.goto("https://accounts.google.com/v3/signin/identifier", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            inp = await page.query_selector("input[type='email'], input[name='identifier']")
            if inp:
                await inp.fill(phone_number)
                await page.keyboard.press("Enter")
                await asyncio.sleep(3)

                content = await page.content()
                if "Could not find your Google Account" in content or "Couldn't find your Google Account" in content:
                    return "No Account Linked"
                elif "Enter your password" in content or "challenge" in content:
                    return "Active Google Account Found"
                else:
                    return "Identifier Submitted"
        except Exception as e:
            self.log(f"Google Sign-In test note: {e}")
            return "Test Error / Shielded"
        return "Unknown"

    async def _cancel_order(self, page, order_id):
        try:
            cancel_btns = await page.query_selector_all("button:has-text('Cancel'), button:has-text('Отмена'), .cancel-btn")
            for btn in cancel_btns:
                if await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(2)
                    return True
        except Exception as e:
            self.log(f"Cancel order note: {e}")
        return False
