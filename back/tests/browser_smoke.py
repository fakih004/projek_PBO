"""Manual browser smoke test; requires backend :8000 and frontend :5173 running."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def main() -> None:
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(EDGE))
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "response",
            lambda response: failed_requests.append(f"{response.status} {response.url}")
            if response.status >= 400 and "favicon" not in response.url
            else None,
        )
        page.goto("http://127.0.0.1:5173/", wait_until="networkidle")
        assert page.get_by_text("Langkah kecil untuk", exact=False).count() == 1
        assert page.get_by_text("Tampilan gagal dimuat", exact=True).count() == 0
        assert page.get_by_text("slot tersedia hari ini", exact=False).count() == 2

        page.goto("http://127.0.0.1:5173/?demo=admin#/dashboard", wait_until="networkidle")
        page.get_by_text("API tersambung").wait_for()
        assert page.get_by_text("Siti Rahmawati", exact=True).count() >= 1
        assert page.get_by_text("FastAPI + MySQL", exact=True).count() == 1

        for role, name in (
            ("nurse", "Ns. Dian Lestari"),
            ("doctor", "dr. Muhammad Fakih Nabal"),
            ("pharmacist", "apt. Rahmat Hidayat"),
            ("patient", "Budi Santoso"),
        ):
            page.locator("[data-role-switch]").select_option(role)
            page.get_by_text(name, exact=True).first.wait_for()
        assert page.get_by_text("Profil Saya", exact=True).count() >= 1

        page.goto("http://127.0.0.1:5173/#/profile", wait_until="networkidle")
        assert page.locator('input[name="nik"]').input_value() == "3273201990000006"

        smoke = browser.new_page()
        smoke.goto("http://127.0.0.1:5173/tests/smoke.html", wait_until="networkidle")
        assert smoke.title().startswith("PASS 13 checks"), smoke.title()
        smoke.close()
        assert not console_errors, console_errors
        assert not page_errors, page_errors
        assert not failed_requests, failed_requests
        browser.close()
    print(json.dumps({"browser": "PASS", "roles": ["admin", "nurse", "doctor", "pharmacist", "patient"], "frontendChecks": 13, "apiErrors": 0}))


if __name__ == "__main__":
    main()

