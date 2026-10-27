"""Uji browser terisolasi untuk memastikan form login selalu kosong."""
import logging
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clinic import create_app, db
from clinic.models import Role, User
from seed import seed_data


ROLE_PASSWORDS = {
    Role.ADMIN: 'Admin123!',
    Role.DOCTOR: 'Dokter123!',
    Role.NURSE: 'Perawat123!',
    Role.PHARMACIST: 'Apoteker123!',
    Role.PATIENT: 'Pasien123!',
    Role.CASHIER: 'Kasir123!',
}


def assert_empty(page):
    expect(page.locator('#email')).to_have_value('')
    expect(page.locator('#password')).to_have_value('')
    expect(page.locator('#password')).to_have_attribute('type', 'password')
    expect(page.get_by_role('button', name='Tampilkan password')).to_have_text('Lihat')


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    with tempfile.TemporaryDirectory(prefix='medika-login-browser-') as folder:
        app = create_app({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(Path(folder) / 'login.db'),
        })
        with app.app_context():
            seed_data(demo=False)
            accounts = [
                (role.value, User.query.filter_by(role=role).first().email, password)
                for role, password in ROLE_PASSWORDS.items()
            ]

        server = make_server('127.0.0.1', 0, app, threaded=True)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                edge = Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
                browser = playwright.chromium.launch(
                    executable_path=str(edge) if edge.exists() else None,
                    headless=True,
                )
                page = browser.new_page(viewport={'width': 1366, 'height': 900})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                base = f'http://127.0.0.1:{port}'

                page.goto(base + '/login')
                for width in (1366, 768, 375):
                    page.set_viewport_size({'width': width, 'height': 900})
                    page.wait_for_timeout(200)
                    form_column = page.locator('.login-form-column').bounding_box()
                    visual_panel = page.locator('.login-visual-panel').bounding_box()
                    assert form_column and visual_panel
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    assert page.locator('.login-visual-panel img').evaluate(
                        '(image) => image.complete && image.naturalWidth === 1200 && getComputedStyle(image).objectFit === "contain"'
                    )
                    if width > 720:
                        assert visual_panel['x'] - (form_column['x'] + form_column['width']) >= 30
                    else:
                        assert visual_panel['y'] - (form_column['y'] + form_column['height']) >= 24
                    screenshot = Path(tempfile.gettempdir()) / f'medika-login-{width}.png'
                    page.screenshot(path=str(screenshot), full_page=True)
                    print(f'LULUS layout {width}px: {screenshot}')
                page.set_viewport_size({'width': 1366, 'height': 900})

                for role, email, password in accounts:
                    page.goto(base + '/')
                    expect(page).to_have_url(base + '/')
                    expect(page.locator('#loginForm')).to_have_count(0)
                    page.get_by_role('link', name='Masuk', exact=True).click()
                    page.wait_for_url('**/login')
                    page.wait_for_timeout(1100)
                    assert_empty(page)
                    page.locator('#email').fill(email)
                    page.locator('#password').fill(password)
                    page.get_by_role('button', name='Tampilkan password').click()
                    expect(page.locator('#password')).to_have_attribute('type', 'text')
                    page.get_by_role('button', name='Sembunyikan password').click()
                    page.get_by_role('button', name='Masuk ke akun').click()
                    page.get_by_role('button', name='Keluar', exact=True).wait_for()
                    page.get_by_role('button', name='Keluar', exact=True).click()
                    expect(page).to_have_url(base + '/')
                    expect(page.locator('#loginForm')).to_have_count(0)
                    page.get_by_role('link', name='Masuk', exact=True).click()
                    page.wait_for_url('**/login')
                    page.wait_for_timeout(1100)
                    assert_empty(page)
                    print(f'LULUS {role}: logout ke landing, Masuk membuka form kosong')

                page.locator('#email').fill('credential-lama@example.test')
                page.locator('#password').fill('PasswordLama123!')
                page.reload()
                page.wait_for_timeout(1100)
                assert_empty(page)
                print('LULUS refresh: email dan password kosong')

                page.locator('#email').fill('credential-bfcache@example.test')
                page.locator('#password').fill('PasswordBFCache123!')
                page.get_by_role('link', name='Daftar sekarang').click()
                page.go_back()
                page.wait_for_timeout(1100)
                assert_empty(page)
                print('LULUS Back/bfcache: email dan password kosong')

                page.goto(base + '/login')
                page.evaluate("""
                    setTimeout(() => {
                        document.querySelector('#email').value = 'autofill@example.test';
                        document.querySelector('#password').value = 'Autofill123!';
                    }, 100);
                """)
                page.wait_for_timeout(1100)
                assert_empty(page)
                print('LULUS autofill tertunda: email dan password dibersihkan')

                page.goto(base + '/login')
                page.locator('#email').press_sequentially('manual@example.test')
                page.locator('#password').press_sequentially('Manual123!')
                page.wait_for_timeout(1100)
                expect(page.locator('#email')).to_have_value('manual@example.test')
                expect(page.locator('#password')).to_have_value('Manual123!')
                print('LULUS aksesibilitas input: ketikan manual tidak dihapus')

                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            thread.join()
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


if __name__ == '__main__':
    main()
