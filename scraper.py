import os
import re
from pathlib import Path

from playwright.sync_api import Playwright

SCRIPT_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = SCRIPT_DIR / "downloads"


def run(playwright: Playwright) -> Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() != "false"

    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(
        ignore_https_errors=True,
        viewport={"width": 1920, "height": 1080},
    )
    page = context.new_page()
    page.set_default_timeout(120_000)
    page.set_default_navigation_timeout(120_000)

    try:
        nrp = os.environ["PPA_NRP"]
        password = os.environ["PPA_PASSWORD"]

        print("  → Membuka halaman login...")
        page.goto("https://ppa-dmp.net/auth")
        page.get_by_text("NRP").click()
        page.get_by_role("textbox", name="NRP").fill(nrp)
        page.get_by_text("Password").click()
        page.get_by_role("textbox", name="Password").fill(password)
        page.get_by_role("button", name="Enter").click()

        print("  → Login berhasil, navigasi ke halaman P2H...")
        page.get_by_role("link", name=" SHE ").first.click()
        page.get_by_role("link", name=" FORM ").click()
        page.get_by_role("link", name=" REPORT ").click()
        page.get_by_role("link", name=" MOBILE ").click()
        page.get_by_role("link", name=" P2H ").click()
        page.get_by_role("link", name=" MONITORING").first.click()
        page.get_by_text(re.compile(r"^NEED APPROVE")).click()

        print("  → Mengekspor data CSV...")
        with page.expect_download() as download_info:
            page.get_by_role("button", name="Export").click()

        download = download_info.value
        downloaded_path = DOWNLOAD_DIR / download.suggested_filename
        download.save_as(downloaded_path)
        print(f"  → File tersimpan: {downloaded_path.name}")

    except Exception:
        page.screenshot(path=str(DOWNLOAD_DIR / "failure.png"), full_page=True)
        raise
    finally:
        page.close()
        context.close()
        browser.close()

    return downloaded_path
