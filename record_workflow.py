import os
import sys
import subprocess

def main():
    bot_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "bot_user_data"))
    os.makedirs(bot_dir, exist_ok=True)
    
    # Remove stale lock files
    for lock in ["SingletonLock", "lockfile", "SingletonCookie", "SingletonSocket"]:
        lp = os.path.join(bot_dir, lock)
        if os.path.exists(lp):
            try:
                os.remove(lp)
            except Exception:
                pass

    out_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "recorded_workflow.py"))
    target_url = "https://smsbower.app/cabinet/client/phonehistory"

    venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = sys.executable

    cmd = [
        venv_python,
        "-m",
        "playwright",
        "codegen",
        "--target", "python-async",
        "--channel", "chrome",
        "--user-data-dir", bot_dir,
        "-o", out_file,
        target_url
    ]

    print("============================================================")
    print("Launching Playwright Codegen Live Recorder...")
    print(f"User Data Directory: {bot_dir}")
    print(f"Output File: {out_file}")
    print("Perform your steps in Chrome — actions will be saved to recorded_workflow.py!")
    print("============================================================")

    try:
        subprocess.run(cmd)
    except Exception as e:
        print(f"Recorder launch error: {e}")

if __name__ == "__main__":
    main()
