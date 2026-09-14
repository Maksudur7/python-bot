import asyncio
import os
import re
import time
import json
import urllib.request
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
        self.capsolver_api_key = "CAP-C839F176A1BB8AE555FFB6755BC28791F6B4095403B4C8B74CB68667B5B7F611"
        
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
                    
                    launch_args = [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--start-maximized",
                        "--js-flags=--max-old-space-size=256"
                    ]
                    
                    viewport_opts = None if not self.headless else {"width": 1366, "height": 768}
                    no_vp = True if not self.headless else False

                    # Try launching with channel='chrome' first, fallback to default Playwright Chromium if Google Chrome is not installed
                    try:
                        try:
                            context = await p.chromium.launch_persistent_context(
                                user_data_dir=self.user_data_dir,
                                headless=self.headless,
                                channel="chrome",
                                viewport=viewport_opts,
                                no_viewport=no_vp,
                                ignore_default_args=["--enable-automation"],
                                args=launch_args
                            )
                        except Exception as chrome_err:
                            if "chrome" in str(chrome_err).lower() or "not found" in str(chrome_err).lower():
                                self.log("System Google Chrome not found, switching to Playwright default Chromium...")
                                context = await p.chromium.launch_persistent_context(
                                    user_data_dir=self.user_data_dir,
                                    headless=self.headless,
                                    viewport=viewport_opts,
                                    no_viewport=no_vp,
                                    ignore_default_args=["--enable-automation"],
                                    args=launch_args
                                )
                            else:
                                raise chrome_err
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
                            viewport=viewport_opts,
                            no_viewport=no_vp,
                            ignore_default_args=["--enable-automation"],
                            args=launch_args
                        )

                    self.current_context = context
                    
                    # Apply stealth anti-detection JS init script to CONTEXT so ALL pages, tabs, and frames inherit it!
                    await context.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                        window.chrome = window.chrome || { runtime: {}, loadTimes: function() {}, csi: function() {}, app: {} };
                        const originalQuery = window.navigator.permissions ? window.navigator.permissions.query : null;
                        if (originalQuery) {
                            window.navigator.permissions.query = (parameters) => (
                                parameters.name === 'notifications' ?
                                    Promise.resolve({ state: Notification.permission }) :
                                    originalQuery(parameters)
                            );
                        }
                    """)

                    page = context.pages[0] if context.pages else await context.new_page()
                    if not self.headless:
                        try:
                            await page.bring_to_front()
                        except Exception:
                            pass

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
                            
                            # Step 2: Check if an active phone number is ALREADY present on cabinet
                            phone_number, order_id = await self._extract_active_phone(page)
                            
                            if not phone_number:
                                # First try executing dynamically recorded workflow if recorded_workflow.py has actions
                                recorded_executed = await self._execute_recorded_workflow(page, context)
                                
                                if not recorded_executed:
                                    # Built-in Step 3: Select Service (Google / Gmail - go)
                                    self.log("Step 3: Selecting Service -> Google / Gmail (go)...")
                                    service_selected = await self._select_service(page)
                                    if not service_selected:
                                        await self._dismiss_overlays(page)
                                        service_selected = await self._select_service(page)
                                    if not self.is_running: break

                                    # Built-in Step 4: Select Position Rank (Gold)
                                    self.log("Step 4: Selecting Position Rank -> Gold...")
                                    await self._select_rank(page, "Gold")
                                    if not self.is_running: break

                                    # Built-in Step 5: Select Country (2nd USA Option - USA Physical)
                                    self.log("Step 5: Searching country 'usa' & selecting USA Physical...")
                                    await self._select_country(page)
                                    if not self.is_running: break

                                    # Built-in Step 6: Locate & Click Offer Gold #3170 ($0.75)
                                    self.log("Step 6: Locating & clicking offer Gold #3170 ($0.75)...")
                                    purchased = await self._buy_target_offer(page)
                                    if purchased:
                                        self.log("Successfully clicked Google offer buy button!")
                                    else:
                                        self.log("Target Google offer #3170 ($0.75) not clicked yet. Retrying iteration...")
                                        await self._sleep_check(1)
                                        continue
                                    if not self.is_running: break

                                await self._sleep_check(0.5)
                                if not self.is_running: break

                                # Step 7: Extract Acquired Phone Number
                                self.log("Step 7: Extracting acquired phone number from active order card...")
                                phone_number, order_id = await self._extract_active_phone(page)

                            if not phone_number:
                                self.log("No active phone number found on cabinet. Retrying iteration...")
                                await self._sleep_check(1)
                                continue

                            self.numbers_checked += 1
                            self.log(f"============================================================")
                            self.log(f"📱 COPIED PHONE NUMBER: {phone_number} (Order ID: {order_id})")
                            self.log(f"============================================================")

                            # Clean phone number for 10-digit search
                            phone_clean = re.sub(r"\D", "", phone_number)
                            if phone_clean.startswith("1") and len(phone_clean) == 11:
                                phone_10 = phone_clean[1:]
                            else:
                                phone_10 = phone_clean[-10:] if len(phone_clean) >= 10 else phone_clean

                            if not self.is_running: break

                            # Step 8: Search FastPeopleSearch & FamilyTreeNow
                            self.log(f"Step 8: Searching FastPeopleSearch for number: {phone_10}...")
                            fps_page = await context.new_page()
                            fps_data = await self._search_fastpeoplesearch(fps_page, phone_10)
                            await fps_page.close()

                            # If FastPeopleSearch does not return a record, search FamilyTreeNow as Fallback 1
                            if not fps_data.get("found") or not fps_data.get("name"):
                                self.log(f"⚠️ FastPeopleSearch had no match/blocked. Fallback 1: Searching FamilyTreeNow for {phone_10}...")
                                ftn_page = await context.new_page()
                                ftn_data = await self._search_familytreenow(ftn_page, phone_10)
                                await ftn_page.close()
                                if ftn_data.get("found") and ftn_data.get("name"):
                                    fps_data = ftn_data
                                    self.log(f"✅ Match found on FamilyTreeNow fallback! Name: '{fps_data.get('name')}'")

                            # If still no record, search That's Them as Fallback 2
                            if not fps_data.get("found") or not fps_data.get("name"):
                                self.log(f"⚠️ FamilyTreeNow had no match/blocked. Fallback 2: Searching That's Them for {phone_10}...")
                                tt_page = await context.new_page()
                                tt_data = await self._search_thatsthem(tt_page, phone_10)
                                await tt_page.close()
                                if tt_data.get("found") and tt_data.get("name"):
                                    fps_data = tt_data
                                    self.log(f"✅ Match found on That's Them fallback! Name: '{fps_data.get('name')}'")

                            if not self.is_running: break

                            # If NO name/record found on FastPeopleSearch, FamilyTreeNow, OR That's Them -> Cancel order on SMSBower & Get Next Number!
                            if not fps_data.get("found") or not fps_data.get("name"):
                                self.log(f"❌ No matching record found across FastPeopleSearch, FamilyTreeNow, or That's Them for {phone_10}.")
                                self.log("👉 Cancelling active order on SMSBower cabinet ($0 cost refund) and fetching new number...")
                                cancelled = await self._cancel_order(page, order_id)
                                if cancelled:
                                    self.cancelled_cost += 1
                                    self.log(f"-> Order successfully cancelled! Total $0 refund cancellations: {self.cancelled_cost}")
                                await self._sleep_check(1)
                                continue  # REPEAT LOOP FOR NEW NUMBER!

                            # MATCH FOUND ON FASTPEOPLESEARCH!
                            extracted_name = fps_data.get("name", "")
                            self.log(f"-> 🎯 MATCH FOUND ON FASTPEOPLESEARCH! Name: '{extracted_name}', Age: {fps_data.get('age')}, Location: {fps_data.get('location')}")

                            if not self.is_running: break

                            # Step 9: Verify Google Sign-In with acquired number & name
                            self.log("Step 9: Testing Google Sign-In with acquired number & FastPeopleSearch name...")
                            google_page = await context.new_page()
                            google_res = await self._verify_google_signin_flow(google_page, phone_number, extracted_name)

                            google_status = google_res.get("message", "FAILED")

                            if google_res.get("status") in ["HOLD_DIRECT_PASSWORD", "HOLD_NAME_VERIFIED"]:
                                # BINGO! Save Record & HOLD/PAUSE!
                                record = database.save_record(
                                    phone=phone_number,
                                    order_id=order_id,
                                    name=extracted_name,
                                    age=fps_data.get("age", ""),
                                    location=fps_data.get("location", ""),
                                    relatives=fps_data.get("relatives", ""),
                                    google_status=google_status
                                )
                                self.records_saved += 1
                                self.log(f"-> 💾 Record saved to database & CSV! Total saved: {self.records_saved}")
                                self.log(f"⏸️ HOLDING BROWSER SESSION FOR USER ACTION ({google_status})...")
                                self.current_status = "HOLD / ACTION REQUIRED"

                                # Wait in Hold loop until user stops or closes
                                while self.is_running and "HOLD" in self.current_status:
                                    await self._sleep_check(1)

                                try:
                                    await google_page.close()
                                except Exception:
                                    pass
                            else:
                                # POINT 3: Google Sign-In Next failed -> Cancel order on SMSBower & Get Next Number!
                                self.log(f"❌ Google Sign-In could not proceed for {phone_number}.")
                                try:
                                    await google_page.close()
                                except Exception:
                                    pass
                                self.log("👉 Cancelling active order on SMSBower cabinet ($0 cost refund) and fetching new number...")
                                cancelled = await self._cancel_order(page, order_id)
                                if cancelled:
                                    self.cancelled_cost += 1
                                    self.log(f"-> Order successfully cancelled! Total $0 refund cancellations: {self.cancelled_cost}")
                                await self._sleep_check(1)
                                continue

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

    async def _dismiss_overlays(self, page):
        """Dismiss popups, modal overlays, cookie banners, or backdrop elements that intercept clicks."""
        try:
            close_selectors = [
                ".popup-overlay .close-btn",
                ".popup-overlay button:has-text('Close')",
                ".popup-overlay button:has-text('OK')",
                ".modal-close",
                "button.close",
                "[aria-label='Close']"
            ]
            for sel in close_selectors:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    try:
                        await btn.click(timeout=1000, force=True)
                    except Exception:
                        pass
            
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            
            await page.evaluate("""
                () => {
                    const overlays = document.querySelectorAll('.popup-overlay, .modal-backdrop, .v-overlay');
                    overlays.forEach(el => {
                        if (el && el.parentElement && el.style) {
                            el.style.display = 'none';
                            el.style.pointerEvents = 'none';
                        }
                    });
                }
            """)
        except Exception:
            pass

    async def _safe_click(self, page, element):
        """Attempt to click an element, falling back to force click or JS click if blocked by overlays."""
        if not element:
            return False
        try:
            await element.click(timeout=2000)
            return True
        except Exception:
            try:
                await element.click(timeout=2000, force=True)
                return True
            except Exception:
                try:
                    await page.evaluate("(el) => el.click()", element)
                    return True
                except Exception:
                    return False

    def _check_connection_error(self, e):
        err_str = str(e).lower()
        if "closed" in err_str or "driver" in err_str or "target" in err_str:
            raise e

    async def _clear_active_cards(self, page):
        await self._dismiss_overlays(page)
        try:
            cancel_buttons = await page.query_selector_all("button:has-text('Cancel'), button:has-text('Отмена'), .cancel-btn, [data-action='cancel']")
            for btn in cancel_buttons:
                try:
                    if await btn.is_visible():
                        await self._safe_click(page, btn)
                        await asyncio.sleep(0.5)
                except Exception as inner_e:
                    self._check_connection_error(inner_e)
        except Exception as e:
            self._check_connection_error(e)
            self.log(f"Note on clearing cards: {e}")

    async def _execute_recorded_workflow(self, page, context=None):
        """Execute exact Playwright codegen statements saved dynamically in recorded_workflow.py (Supports Multi-Tab)"""
        file_path = os.path.join(os.path.dirname(__file__), "recorded_workflow.py")
        if not os.path.exists(file_path):
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            action_lines = []
            for line in content.splitlines():
                line_str = line.strip()
                if not line_str or line_str.startswith("#") or line_str.startswith("import ") or line_str.startswith("from "):
                    continue
                if any(skip_kw in line_str for skip_kw in ["async def ", "async with async_playwright", "browser =", "context.close()", "browser.close()", "page.close()"]):
                    continue

                if any(kw in line_str for kw in ["page", "click", "fill", "press", "locator", "get_by_", "new_page", "expect_popup"]):
                    if not line_str.startswith("await ") and "=" not in line_str and not line_str.startswith("async with "):
                        line_str = "await " + line_str
                    action_lines.append(line_str)

            if not action_lines:
                return False

            self.log(f"🎬 Executing {len(action_lines)} dynamically recorded workflow steps (Multi-Tab Supported)...")
            
            local_scope = {
                "page": page,
                "page1": page,
                "page2": page,
                "context": context,
                "asyncio": asyncio,
                "re": re
            }
            executed_count = 0

            for idx, stmt in enumerate(action_lines, 1):
                if not self.is_running: break
                self.log(f"-> Recorded Action {idx}/{len(action_lines)}: {stmt}")
                try:
                    exec_code = f"async def _step():\n    {stmt}\n"
                    exec(exec_code, local_scope)
                    await local_scope["_step"]()
                    executed_count += 1
                    await asyncio.sleep(0.5)
                except Exception as step_err:
                    self.log(f"-> Recorded Step {idx} note: {step_err}")

            return executed_count > 0
        except Exception as e:
            self.log(f"Recorded workflow execution note: {e}")
            return False

    async def _select_service(self, page):
        await self._dismiss_overlays(page)
        try:
            self.log("Step 3: Selecting Service -> Google / Gmail (go)...")
            
            # Primary Recorded Playwright Method
            try:
                box = page.get_by_role("combobox").get_by_text("Select service")
                if await box.is_visible():
                    await box.click()
                    await asyncio.sleep(0.3)
                    s_input = page.get_by_role("textbox", name="Select service")
                    if await s_input.is_visible():
                        await s_input.fill("google")
                        await asyncio.sleep(0.5)
                    opt = page.get_by_role("option", name="Google, Gmail, Youtube go")
                    if await opt.is_visible():
                        await opt.click()
                        await asyncio.sleep(0.5)
                        self.log("Successfully selected 'Google' service via recorded role selector.")
                        return True
            except Exception as rec_err:
                self.log(f"Recorded service select note: {rec_err}")

            # Fallback search box query selector
            search_box = await page.query_selector("input[placeholder*='Select service'], [name='Select service'], .multiselect, .multiselect__tags, .multiselect__placeholder, input[name='service-name']")
            if search_box:
                await self._safe_click(page, search_box)
                await asyncio.sleep(0.2)
                await page.keyboard.type("google")
                await asyncio.sleep(0.8)
                await page.keyboard.press("Enter")
                await asyncio.sleep(0.5)

            service_selectors = [
                "text='Google, Gmail, Youtube'",
                ".multiselect__option:has-text('Google')",
                "[data-service='go']",
                "[data-service='google']"
            ]
            for sel in service_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    if await self._safe_click(page, el):
                        await asyncio.sleep(0.5)
                        return True
            return True
        except Exception as e:
            self._check_connection_error(e)
            self.log(f"Service select note: {e}")
            return False

    async def _select_rank(self, page, rank_name="Gold"):
        await self._dismiss_overlays(page)
        try:
            self.log(f"Step 4: Selecting Position Rank -> {rank_name}...")
            
            # Primary recorded method: page.get_by_text("Gold", exact=True).click()
            gold_loc = page.get_by_text(rank_name, exact=True)
            if await gold_loc.is_visible():
                await gold_loc.click()
                await asyncio.sleep(0.5)
                self.log(f"Successfully selected '{rank_name}' rank filter via get_by_text.")
                return True

            rank_selectors = [
                "text='Gold'",
                ".rank-item.gold",
                ".rank-item:has-text('Gold')",
                "div.rank-item:has-text('Gold')",
                "[data-rank='gold']",
                "button:has-text('Gold')"
            ]
            for sel in rank_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    if await self._safe_click(page, el):
                        await asyncio.sleep(0.5)
                        self.log("Successfully selected 'Gold' rank filter.")
                        return True
            return False
        except Exception as e:
            self._check_connection_error(e)
            self.log(f"Rank select note: {e}")
            return False

    async def _select_country(self, page):
        await self._dismiss_overlays(page)
        try:
            self.log("Step 5: Searching country 'usa' & expanding 2nd USA card (USA Physical)...")
            
            # Step 1: Search 'usa' in country search input (as recorded)
            c_box = page.get_by_role("textbox", name="Find country")
            if await c_box.is_visible():
                await c_box.click()
                await c_box.fill("usa")
            else:
                c_inp = await page.query_selector("input[placeholder*='Find country'], input[placeholder*='Country']")
                if c_inp and await c_inp.is_visible():
                    await c_inp.click()
                    await c_inp.fill("usa")

            await asyncio.sleep(1.2)

            # Step 2: Click 'Select' dropdown on the 2nd country card (USA Physical)
            country_items = page.locator(".phone-country-item, .phone-country-item-body")
            item_count = await country_items.count()

            if item_count >= 2:
                card2 = country_items.nth(1)
                select_btn = card2.locator(".phone-country-item-show-hide-btn, .phone-country-select, .app-select__value-container, text='Select', button:has-text('Select')").first
                if await select_btn.is_visible():
                    await self._safe_click(page, select_btn)
                    await asyncio.sleep(1.5)
                    self.log("Successfully clicked 'Select' dropdown on 2nd USA card (USA Physical).")
                    return True

            # Fallback 1: try exact recorded selector
            rec_sel = page.locator("div:nth-child(2) > .phone-country-item-body > .phone-country-select > .app-select > .app-select__control > .app-select__value-container")
            if await rec_sel.is_visible():
                await self._safe_click(page, rec_sel)
                await asyncio.sleep(1.5)
                self.log("Successfully clicked 2nd USA card dropdown via recorded selector.")
                return True

            # Fallback 2: locate all 'Select' / show-hide buttons
            select_btns = page.locator(".phone-country-item-show-hide-btn, button:has-text('Select'), div:has-text('Select')")
            if await select_btns.count() >= 2:
                await self._safe_click(page, select_btns.nth(1))
                await asyncio.sleep(1.5)
                self.log("Expanded 2nd USA card dropdown table via fallback.")
            elif await select_btns.count() > 0:
                await self._safe_click(page, select_btns.nth(0))
                await asyncio.sleep(1.5)
                self.log("Expanded USA card dropdown table via fallback.")
            return True
        except Exception as e:
            self._check_connection_error(e)
            self.log(f"Country select note: {e}")
            return False

    async def _buy_target_offer(self, page):
        await self._dismiss_overlays(page)
        try:
            self.log("Step 6: Locating & clicking offer $0.75 / 0.75 $ buy button...")
            for attempt in range(5):
                # 1. Recorded locator: get_by_text("0.75 $", exact=True)
                btn1 = page.get_by_text("0.75 $", exact=True)
                if await btn1.is_visible():
                    await btn1.click()
                    await asyncio.sleep(1.5)
                    self.log("Successfully clicked '0.75 $' offer buy button!")
                    return True

                # 2. Text locator variations
                btn2 = page.locator("text='0.75 $'").first
                if await btn2.is_visible():
                    await self._safe_click(page, btn2)
                    await asyncio.sleep(1.5)
                    self.log("Successfully clicked '0.75 $' offer buy button!")
                    return True

                btn3 = page.locator("text='$0.75'").first
                if await btn3.is_visible():
                    await self._safe_click(page, btn3)
                    await asyncio.sleep(1.5)
                    self.log("Successfully clicked '$0.75' offer buy button!")
                    return True

                # 3. Table row containing 3170 or 0.75
                rows = page.locator("tr:has-text('3170'), tr:has-text('0.75'), div:has-text('3170'), div:has-text('0.75')")
                for r_idx in range(await rows.count()):
                    row = rows.nth(r_idx)
                    buy_btn = row.query_selector("button, .btn, a, div")
                    if buy_btn and await buy_btn.is_visible():
                        if await self._safe_click(page, buy_btn):
                            await asyncio.sleep(1.5)
                            self.log("Successfully clicked offer buy button in table row!")
                            return True

                await asyncio.sleep(0.5)
            return False
        except Exception as e:
            self._check_connection_error(e)
            self.log(f"Buy offer note: {e}")
            return False

    async def _extract_active_phone(self, page):
        # Scroll up to top of cabinet page to see active order card
        try:
            await page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass

        self.log("Step 7: Waiting for active phone number order card & copying number...")

        for attempt in range(12):
            # 1. Click copy button if present (as recorded: page.locator(".--copy > img"))
            try:
                copy_img = page.locator(".--copy > img, .--copy, [class*='copy']").first
                if await copy_img.is_visible():
                    await copy_img.click()
                    self.log("Clicked active phone copy button (.--copy > img).")
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            # 2. Check for phone number text in active order element or locator regex
            try:
                phone_loc = page.locator("text=/\\+?1[0-9]{10}/").first
                if await phone_loc.is_visible():
                    txt = await phone_loc.text_content()
                    digits = re.sub(r"\D", "", txt)
                    if len(digits) in (10, 11):
                        clean_phone = "+1" + digits[-10:]
                        self.log(f"Extracted active phone number: {clean_phone}")
                        return clean_phone, f"ORD-{int(time.time())}"
            except Exception:
                pass

            # 3. Full page text parsing via BeautifulSoup
            try:
                content = await page.content()
                soup = BeautifulSoup(content, "html.parser")
                page_text = soup.get_text()
                
                raw_matches = re.findall(r"\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", page_text)
                for raw in raw_matches:
                    digits = re.sub(r"\D", "", raw)
                    if len(digits) in (10, 11):
                        clean_phone = "+1" + digits[-10:]
                        order_ids = re.findall(r"ID:?\s*(\d+)", page_text)
                        order_id = order_ids[0] if order_ids else f"ORD-{int(time.time())}"
                        return clean_phone, order_id
            except Exception:
                pass

            # Refresh cabinet page if order card delayed
            if attempt == 5:
                self.log("Refreshing cabinet page to load newly assigned phone number...")
                try:
                    await page.goto("https://smsbower.app/cabinet/client/phonehistory", wait_until="domcontentloaded", timeout=15000)
                    await page.evaluate("window.scrollTo(0, 0)")
                except Exception:
                    pass

            await asyncio.sleep(0.8)

        return "", ""

    async def _solve_turnstile_capsolver(self, page, page_url):
        if not self.capsolver_api_key:
            return False
        try:
            sitekey = await page.evaluate("""
                () => {
                    const el = document.querySelector('[data-sitekey]');
                    if (el) return el.getAttribute('data-sitekey');
                    const iframe = document.querySelector('iframe[src*="challenges.cloudflare.com"]');
                    if (iframe) {
                        const src = iframe.getAttribute('src') || '';
                        const match = src.match(/k=([^&]+)/) || src.match(/sitekey=([^&]+)/);
                        if (match) return match[1];
                    }
                    return null;
                }
            """)
            
            if not sitekey:
                html = await page.content()
                match = re.search(r"sitekey[\"']?\s*:\s*[\"']([^\"']+)[\"']", html) or re.search(r"data-sitekey=[\"']([^\"']+)[\"']", html)
                if match:
                    sitekey = match.group(1)

            if not sitekey:
                self.log("CapSolver note: Turnstile sitekey not found on page DOM.")
                return False

            self.log(f"🔑 Found Cloudflare Sitekey ({sitekey[:10]}...). Sending to CapSolver API...")

            task_payload = {
                "clientKey": self.capsolver_api_key,
                "task": {
                    "type": "AntiTurnstileTaskProxyLess",
                    "websiteURL": page_url,
                    "websiteKey": sitekey
                }
            }

            req = urllib.request.Request(
                "https://api.capsolver.com/createTask",
                data=json.dumps(task_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            
            loop = asyncio.get_event_loop()
            resp_raw = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req).read().decode("utf-8"))
            data = json.loads(resp_raw)

            if data.get("errorId", 0) != 0:
                self.log(f"CapSolver API note: {data.get('errorDescription', '')} ({data.get('errorCode', '')})")
                return False

            task_id = data.get("taskId")
            if not task_id:
                return False

            self.log(f"CapSolver Task ID: {task_id}. Polling solution token...")

            for attempt in range(12):
                await asyncio.sleep(2)
                poll_payload = {"clientKey": self.capsolver_api_key, "taskId": task_id}
                poll_req = urllib.request.Request(
                    "https://api.capsolver.com/getTaskResult",
                    data=json.dumps(poll_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                poll_raw = await loop.run_in_executor(None, lambda: urllib.request.urlopen(poll_req).read().decode("utf-8"))
                poll_data = json.loads(poll_raw)

                if poll_data.get("status") == "ready":
                    solution = poll_data.get("solution", {})
                    token = solution.get("token")
                    if token:
                        self.log("✅ CapSolver Turnstile token solved successfully!")
                        await page.evaluate("""
                            (token) => {
                                const els = document.querySelectorAll('input[name="cf-turnstile-response"], [name="g-recaptcha-response"]');
                                els.forEach(el => {
                                    el.value = token;
                                    el.dispatchEvent(new Event('input', { bubbles: true }));
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                });
                                if (window.tsCallback) window.tsCallback(token);
                                if (window.turnstile && window.turnstile.callback) window.turnstile.callback(token);
                                const form = document.querySelector('form');
                                if (form) form.submit();
                            }
                        """, token)
                        await asyncio.sleep(2)
                        return True
                elif poll_data.get("status") == "failed":
                    self.log(f"CapSolver polling note: {poll_data.get('errorDescription')}")
                    return False

        except Exception as e:
            self.log(f"CapSolver solver note: {e}")

        return False

    async def _search_fastpeoplesearch(self, page, phone_10):
        phone_clean = re.sub(r"\D", "", phone_10)[-10:]
        phone_formatted = f"{phone_clean[:3]}-{phone_clean[3:6]}-{phone_clean[6:]}" if len(phone_clean) == 10 else phone_clean
        
        url = "https://www.fastpeoplesearch.com/"
        try:
            self.log(f"Navigating to FastPeopleSearch homepage ({url}) for number: {phone_10}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(1.5)

            if not self.headless:
                try:
                    await page.bring_to_front()
                except Exception:
                    pass

            # Persistent Hybrid Wait Loop: Wait for Turnstile pass (auto-click + manual fallback)
            max_captcha_attempts = 25  # Wait up to ~75 seconds
            warned_user = False
            for cf_attempt in range(max_captcha_attempts):
                if not self.is_running:
                    return {"found": False}

                content_check = await page.content()
                
                # Check if Cloudflare Turnstile / Just a moment page is active
                if "challenges.cloudflare.com" in content_check or "Just a moment..." in content_check or "Verify you are human" in content_check:
                    if not warned_user:
                        self.log("⚠️ CLOUDFLARE TURNSTILE DETECTED on FastPeopleSearch!")
                        self.log("🚀 Attempting automatic solving via CapSolver API...")
                        solved = await self._solve_turnstile_capsolver(page, page.url)
                        if solved:
                            self.log("✅ CapSolver API successfully cleared Turnstile on FastPeopleSearch!")
                            break
                        else:
                            self.log("👉 CapSolver fallback: Please click Turnstile 1 time manually if auto-pass takes time.")
                        warned_user = True
                    else:
                        self.log(f"⏳ Waiting for Turnstile clearance... [{cf_attempt+1}/{max_captcha_attempts}]")
                    
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
                        self.log(f"Turnstile auto-click note: {cf_err}")
                    
                    await asyncio.sleep(3)
                else:
                    self.log("✅ Cloudflare Turnstile CLEARED SUCCESSFULLY on FastPeopleSearch!")
                    break

            await asyncio.sleep(1)

            # Step 2: Select PHONE option/tab on FastPeopleSearch
            self.log("Selecting 'PHONE' reverse lookup option tab on FastPeopleSearch...")
            phone_tab = page.locator("#search-nav-link-phone, a[data-target='#search-type-container-phone'], text='PHONE'")
            if await phone_tab.first.is_visible():
                await phone_tab.first.click()
                await asyncio.sleep(0.5)

            # Step 3: Fill phone number input field & submit form
            self.log(f"Filling phone number {phone_formatted} into FastPeopleSearch input field...")
            phone_inp = page.locator("#search-phone-phone, input[name='phone']").first
            if await phone_inp.is_visible():
                await phone_inp.fill(phone_formatted)
                await asyncio.sleep(0.5)
                
                submit_btn = page.locator("#form-search-phone button[type='submit'], #form-search-phone .search-form-button-submit").first
                if await submit_btn.is_visible():
                    self.log("Clicking FastPeopleSearch Free Search button...")
                    await submit_btn.click()
                    await asyncio.sleep(3)
            else:
                self.log(f"Direct phone URL fallback: https://www.fastpeoplesearch.com/phone/{phone_formatted}")
                await page.goto(f"https://www.fastpeoplesearch.com/phone/{phone_formatted}", wait_until="domcontentloaded", timeout=40000)

            # Step 4: Secondary Turnstile check on results page if triggered
            for cf_attempt in range(max_captcha_attempts):
                if not self.is_running:
                    return {"found": False}

                content_check = await page.content()
                if "challenges.cloudflare.com" in content_check or "Just a moment..." in content_check or "Verify you are human" in content_check:
                    if not warned_user:
                        self.log("⚠️ CLOUDFLARE TURNSTILE DETECTED on FastPeopleSearch Results!")
                        self.log("👉 Please click Turnstile checkbox manually in Chrome window if needed.")
                        warned_user = True
                    await asyncio.sleep(3)
                else:
                    break

            await asyncio.sleep(2.5)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            page_text = soup.get_text()

            if "0 People Records" in page_text or "No records found" in page_text or "404" in page_text or "0 Records" in page_text:
                self.log(f"FastPeopleSearch result: No matching record for {phone_10}.")
                return {"found": False}

            # Extract details from FastPeopleSearch results DOM
            name_el = soup.select_one(".card-title, .record-name, a[href*='name'], h2.card-title, .people-card h2, a.link-to-details, h2, h3")
            name = name_el.get_text(strip=True) if name_el else ""

            age_el = soup.select_one(".age, span[class*='age']")
            age = age_el.get_text(strip=True) if age_el else ""

            loc_el = soup.select_one(".location, .address, span[class*='location'], a[href*='address']")
            location = loc_el.get_text(strip=True) if loc_el else ""

            relatives_els = soup.select("a[href*='name'], .relatives a, a[href*='relative']")
            relatives = ", ".join([r.get_text(strip=True) for r in relatives_els[:5]]) if relatives_els else ""

            if name or "Full Name" in page_text or "Current Address" in page_text:
                return {
                    "found": True,
                    "name": name if name else "Person Record Found",
                    "age": age,
                    "location": location,
                    "relatives": relatives,
                    "source": "FastPeopleSearch"
                }
        except Exception as e:
            self.log(f"FastPeopleSearch lookup warning: {e}")

        return {"found": False}

    async def _search_familytreenow(self, page, phone_10):
        url = f"https://www.familytreenow.com/search/genealogy/results?searchtype=phone&phone={phone_10}"
        try:
            self.log(f"Navigating to FamilyTreeNow search URL for {phone_10}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(2)
            
            if not self.headless:
                try:
                    await page.bring_to_front()
                except Exception:
                    pass

            # Persistent Hybrid Wait Loop: Wait for Turnstile pass (auto-click + manual fallback)
            max_captcha_attempts = 25  # Wait up to ~75 seconds
            warned_user = False
            for cf_attempt in range(max_captcha_attempts):
                if not self.is_running:
                    return {"found": False}

                content_check = await page.content()
                
                # Check if Cloudflare Turnstile / Just a moment page is active
                if "challenges.cloudflare.com" in content_check or "Just a moment..." in content_check or "Verify you are human" in content_check:
                    if not warned_user:
                        self.log("⚠️ CLOUDFLARE TURNSTILE DETECTED on FamilyTreeNow!")
                        self.log("🚀 Attempting automatic solving via CapSolver API...")
                        solved = await self._solve_turnstile_capsolver(page, page.url)
                        if solved:
                            self.log("✅ CapSolver API successfully cleared Turnstile!")
                            break
                        else:
                            self.log("👉 CapSolver fallback: Please click Turnstile 1 time manually if auto-pass takes time.")
                        warned_user = True
                    else:
                        self.log(f"⏳ Waiting for Turnstile clearance... [{cf_attempt+1}/{max_captcha_attempts}]")
                    
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
                        self.log(f"Turnstile auto-click note: {cf_err}")
                    
                    await asyncio.sleep(3)
                else:
                    self.log("✅ Cloudflare Turnstile CLEARED SUCCESSFULLY!")
                    break

            # Extra wait for search results page DOM render
            await asyncio.sleep(2.5)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            page_text = soup.get_text()

            # Ensure phone number search is submitted if form is presented
            try:
                inp = await page.query_selector("input[name='phone'], input[placeholder*='phone'], #phone")
                if inp:
                    val = await inp.input_value()
                    if not val or phone_10 not in val:
                        self.log(f"Filling phone number {phone_10} into FamilyTreeNow input field...")
                        await inp.fill(phone_10)
                        await asyncio.sleep(0.5)
                        btn = await page.query_selector("button:has-text('Search'), input[type='submit'], .btn-primary")
                        if btn:
                            self.log("Clicking FamilyTreeNow Search button...")
                            await btn.click()
                            await asyncio.sleep(4)
                            content = await page.content()
                            soup = BeautifulSoup(content, "html.parser")
                            page_text = soup.get_text()
            except Exception as form_err:
                self.log(f"Form interaction note: {form_err}")

            if "0 People Records" in page_text or "No records found" in page_text or "0 Records" in page_text:
                self.log(f"FamilyTreeNow result: No matching record for {phone_10}.")
                return {"found": False}

            # Extract details
            name_el = soup.select_one(".detail-link, .record-name, a[href*='search/person'], h3, .name")
            name = name_el.get_text(strip=True) if name_el else ""

            age_el = soup.select_one(".age, span[class*='age']")
            age = age_el.get_text(strip=True) if age_el else ""

            loc_el = soup.select_one(".location, .address, span[class*='location']")
            location = loc_el.get_text(strip=True) if loc_el else ""

            relatives_els = soup.select(".relatives a, .relative-name, a[href*='relative']")
            relatives = ", ".join([r.get_text(strip=True) for r in relatives_els[:5]]) if relatives_els else ""

            if name or "Person Record" in page_text or "Living" in page_text:
                return {
                    "found": True,
                    "name": name if name else "Person Record Found",
                    "age": age,
                    "location": location,
                    "relatives": relatives,
                    "source": "FamilyTreeNow"
                }
        except Exception as e:
            self.log(f"FamilyTreeNow lookup warning: {e}")

        return {"found": False}

    async def _search_thatsthem(self, page, phone_10):
        phone_clean = re.sub(r"\D", "", phone_10)[-10:]
        phone_formatted = f"{phone_clean[:3]}-{phone_clean[3:6]}-{phone_clean[6:]}" if len(phone_clean) == 10 else phone_clean
        url = f"https://thatsthem.com/phone/{phone_formatted}"
        try:
            self.log(f"Navigating to That's Them reverse lookup URL for {phone_formatted}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            content = await page.content()
            soup = BeautifulSoup(content, "html.parser")
            page_text = soup.get_text()

            if "No records found" in page_text or "0 Records" in page_text or "404" in page_text:
                self.log(f"That's Them result: No matching record for {phone_10}.")
                return {"found": False}

            name_el = soup.select_one(".name a, .name, h2.name, a.name, itemprop['name']")
            name = name_el.get_text(strip=True) if name_el else ""

            age_el = soup.select_one(".age, span.age")
            age = age_el.get_text(strip=True) if age_el else ""

            loc_el = soup.select_one(".address, .location")
            location = loc_el.get_text(strip=True) if loc_el else ""

            relatives_els = soup.select(".relatives a, a[href*='name']")
            relatives = ", ".join([r.get_text(strip=True) for r in relatives_els[:5]]) if relatives_els else ""

            if name:
                return {
                    "found": True,
                    "name": name,
                    "age": age,
                    "location": location,
                    "relatives": relatives,
                    "source": "That's Them"
                }
        except Exception as e:
            self.log(f"That's Them lookup note: {e}")

        return {"found": False}

    def _emit_alert_whistle(self):
        """Emit a loud whistle/beep sound alert on Windows system when a target account is hit."""
        try:
            import winsound
            for frequency in [1500, 2000, 2500, 3000]:
                winsound.Beep(frequency, 300)
        except Exception:
            try:
                print("\a\a\a\a\a")
            except Exception:
                pass

    def _clean_name(self, raw_name):
        """Clean and split full name into first and last name neatly."""
        if not raw_name:
            return "", ""
        cleaned = re.sub(r"(?i)\b(view|details|person|record|living|age|\d+)\b", "", raw_name)
        cleaned = re.sub(r"[^\w\s]", " ", cleaned).strip()
        parts = [p.capitalize() for p in cleaned.split() if len(p) > 1]
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], parts[0]
        first_name = parts[0]
        last_name = " ".join(parts[1:])
        return first_name, last_name

    async def _verify_google_signin_flow(self, page, phone_number, name):
        """
        Interacts with Google Sign-In using phone number & FastPeopleSearch name.
        """
        try:
            self.log(f"Navigating to Google Sign-In for phone number: {phone_number}...")
            await page.goto("https://accounts.google.com/v3/signin/identifier", wait_until="domcontentloaded", timeout=35000)
            await asyncio.sleep(2)

            # Step A: Locate Identifier input
            inp = page.locator("input[type='email'], input[name='identifier'], #identifierId, input[aria-label*='Email']").first
            if not await inp.is_visible():
                self.log("Google Sign-In identifier input not found.")
                return {"status": "FAILED", "message": "Identifier input not visible"}

            self.log(f"Entering phone number {phone_number} on Google Sign-In...")
            await inp.fill(phone_number)
            await asyncio.sleep(0.5)

            # Click Next
            next_btn = page.locator("#identifierNext, button:has-text('Next'), button:has-text('Далее')").first
            if await next_btn.is_visible():
                await next_btn.click()
            else:
                await page.keyboard.press("Enter")

            await asyncio.sleep(3.5)

            content = await page.content()
            page_text = BeautifulSoup(content, "html.parser").get_text()

            # Check if Error (No account linked / invalid number)
            if any(err in content for err in [
                "Could not find your Google Account",
                "Couldn't find your Google Account",
                "Enter a valid email or phone number",
                "Try again with a different"
            ]) or "Could not find your Google Account" in page_text:
                self.log(f"❌ Google Sign-In error: No account linked for number {phone_number}.")
                return {"status": "FAILED", "message": "No Google Account Linked"}

            # Sub-case 1: Directly asks for Password
            pwd_field = page.locator("input[type='password'], input[name='Passwd'], #password").first
            if (await pwd_field.is_visible() if await pwd_field.count() > 0 else False) or "Enter your password" in content or "Confirm your password" in content:
                self.log("============================================================")
                self.log(f"🚨 BINGO! Google directly requested Password for {phone_number}!")
                self.log("============================================================")
                self._emit_alert_whistle()
                return {"status": "HOLD_DIRECT_PASSWORD", "message": "Active Account - Direct Password Requested"}

            # Sub-case 2: Asks for Name (First Name & Last Name)
            fname_field = page.locator("input[name='firstName'], #firstName").first
            lname_field = page.locator("input[name='lastName'], #lastName").first

            if (await fname_field.is_visible() if await fname_field.count() > 0 else False):
                first_name, last_name = self._clean_name(name)
                self.log(f"Google requested Name verification. Entering First Name: '{first_name}', Last Name: '{last_name}'...")
                
                await fname_field.fill(first_name)
                if await lname_field.is_visible():
                    await lname_field.fill(last_name)

                await asyncio.sleep(0.5)

                name_next_btn = page.locator("#collectNameNext, #next, button:has-text('Next')").first
                if await name_next_btn.is_visible():
                    await name_next_btn.click()
                else:
                    await page.keyboard.press("Enter")

                await asyncio.sleep(3.5)

                content_after = await page.content()
                if not any(err in content_after for err in ["Wrong name", "Try again", "Could not verify"]):
                    self.log("============================================================")
                    self.log(f"🚨 BINGO! Name verified successfully on Google for {phone_number} ({first_name} {last_name})!")
                    self.log("============================================================")
                    self._emit_alert_whistle()
                    return {"status": "HOLD_NAME_VERIFIED", "message": "Active Account - Name Verified"}
                else:
                    self.log("❌ Name verification failed on Google Sign-In.")
                    return {"status": "FAILED", "message": "Name verification failed"}

            # Fallback check if password or verification screen loaded
            if "password" in page.url.lower() or "challenge" in page.url.lower():
                self.log(f"🚨 BINGO! Google Sign-In proceeded to verification/password for {phone_number}!")
                self._emit_alert_whistle()
                return {"status": "HOLD_DIRECT_PASSWORD", "message": "Active Account - Proceeded to Challenge"}

            self.log(f"⚠️ Google Sign-In could not proceed past identifier for {phone_number}.")
            return {"status": "FAILED", "message": "Identifier Next Failed"}

        except Exception as e:
            self.log(f"Google Sign-In flow error: {e}")
            return {"status": "FAILED", "message": str(e)}

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
