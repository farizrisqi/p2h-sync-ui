import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(Path(__file__).parent / ".env")

from scraper import run as scrape
from sheets_sync import sync_p2h_sheet


def main():
    print("Mengambil data dari ppa-dmp.net...")
    try:
        with sync_playwright() as playwright:
            csv_path = scrape(playwright)
        print(f"Data berhasil diunduh: {csv_path.name}")
    except Exception as e:
        print(f"GAGAL mengambil data: {e}")
        sys.exit(1)

    print("Mengirim data ke Google Sheets...")
    try:
        count = sync_p2h_sheet(csv_path)
        print(f"Berhasil sync {count} baris ke Google Sheets.")
    except Exception as e:
        print(f"GAGAL sync ke Google Sheets: {e}")
        sys.exit(1)

    print("Selesai! Data sudah diperbarui.")


if __name__ == "__main__":
    main()
