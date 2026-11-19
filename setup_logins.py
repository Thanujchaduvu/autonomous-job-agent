import os
import sys
from playwright.sync_api import sync_playwright

PORTALS = [
    {
        "key": "internshala",
        "name": "Internshala",
        "login_url": "https://internshala.com/login/student",
        "check_url": "https://internshala.com/student/dashboard",
        "logged_out_marker": "login",
    },
    {
        "key": "naukri",
        "name": "Naukri",
        "login_url": "https://www.naukri.com/nlogin/login",
        "check_url": "https://www.naukri.com/mnjuser/homepage",
        "logged_out_marker": "nlogin",
    },
    {
        "key": "wellfound",
        "name": "Wellfound",
        "login_url": "https://wellfound.com/login",
        "check_url": "https://wellfound.com/jobs",
        "logged_out_marker": "login",
    },
]


def setup_portal(portal: dict):
    os.makedirs("data/browser_profile", exist_ok=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir="data/browser_profile",
            headless=False,
            viewport={"width": 1366, "height": 768},
        )
        page = context.pages[0] if context.pages else context.new_page()

        print(f"\n--- {portal['name']} ---")
        print(f"Checking existing session at {portal['check_url']}...")
        try:
            page.goto(portal["check_url"], wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2500)
        except Exception:
            pass

        current_url = ""
        try:
            if not page.is_closed():
                current_url = page.url.lower()
        except Exception:
            pass

        if current_url and portal["logged_out_marker"] not in current_url:
            print(f"[OK] {portal['name']} is ALREADY logged in! (Current URL: {page.url})")
            ans = input("Press ENTER to keep this session, or type 'relogin' to log in again: ").strip().lower()
            if ans != "relogin":
                try:
                    context.close()
                except Exception:
                    pass
                return

        print(f"Opening {portal['name']} login page: {portal['login_url']}")
        try:
            if page.is_closed():
                page = context.new_page()
            page.goto(portal["login_url"], wait_until="domcontentloaded", timeout=25000)
        except Exception as exc:
            print(f"Navigation notice: {exc}")

        input(
            f"\nAction Required:\n"
            f"1. Log in to {portal['name']} in the Chromium window.\n"
            f"2. Wait until your logged-in homepage/dashboard finishes loading.\n"
            f"3. Press ENTER here in PowerShell (you can leave the browser open; it will close automatically)..."
        )

        try:
            if not page.is_closed():
                print(f"[SAVED] {portal['name']} session stored (Active URL: {page.url})")
        except Exception:
            print(f"[SAVED] {portal['name']} browser profile flushed to disk.")

        try:
            context.close()
        except Exception:
            pass


def main():
    target = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "all"
    selected = [p for p in PORTALS if target in ("all", p["key"])]

    print("==========================================================")
    print("  Persistent Portal Login Setup (data/browser_profile)    ")
    print("==========================================================")
    for portal in selected:
        setup_portal(portal)

    print("\nPortal login setup complete!")


if __name__ == "__main__":
    main()