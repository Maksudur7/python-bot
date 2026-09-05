import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from automation_bot import SMSBowerBot

async def test_bot_fps_methods():
    print("Testing SMSBowerBot FastPeopleSearch & Google Flow methods...")
    bot = SMSBowerBot()
    assert hasattr(bot, "_search_fastpeoplesearch"), "SMSBowerBot missing _search_fastpeoplesearch method!"
    assert hasattr(bot, "_verify_google_signin_flow"), "SMSBowerBot missing _verify_google_signin_flow method!"
    assert hasattr(bot, "_emit_alert_whistle"), "SMSBowerBot missing _emit_alert_whistle method!"
    
    # Test name cleaning
    fn, ln = bot._clean_name("John Doe (Age 45)")
    assert fn == "John" and ln == "Doe", f"Name clean failed: {fn}, {ln}"
    print(f"Name clean test passed: '{fn}' '{ln}'")
    
    print("SUCCESS: All SMSBowerBot methods verified point-to-point!")

if __name__ == "__main__":
    asyncio.run(test_bot_fps_methods())
