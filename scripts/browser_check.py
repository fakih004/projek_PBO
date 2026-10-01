"""Run against the local development server. Saves actual UI evidence under docs/screenshots."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'screenshots'
OUT.mkdir(parents=True,exist_ok=True)


def main():
    with sync_playwright() as p:
        edge=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
        browser=p.chromium.launch(executable_path=str(edge) if edge.exists() else None,headless=True)
        context=browser.new_context()
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.goto('http://127.0.0.1:5000',wait_until='networkidle')
        for width in [375,768,1366,1920]:
            page.set_viewport_size({'width':width,'height':900})
            page.screenshot(path=str(OUT/f'landing-{width}.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Landing overflow {width}'
        page.goto('http://127.0.0.1:5000/login')
        page.locator('[name=email]').fill('admin@medikahusada.local')
        page.locator('[name=password]').fill('Admin123!')
        page.get_by_role('button',name='Masuk ke akun').click()
        page.wait_for_url('**/admin/dashboard')
        for width in [375,768,1366,1920]:
            page.set_viewport_size({'width':width,'height':900})
            page.screenshot(path=str(OUT/f'admin-{width}.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),f'Dashboard overflow {width}'
        page.set_viewport_size({'width':375,'height':900})
        page.get_by_role('button',name='Buka navigasi').click()
        assert 'open' in page.locator('#sidebar').get_attribute('class')
        page.set_viewport_size({'width':1366,'height':900})
        page.get_by_role('button',name='Keluar',exact=True).click()
        for account,password,role in [('pasien','Pasien123!','patient'),('perawat','Perawat123!','nurse'),('fakih','Dokter123!','doctor'),('apoteker','Apoteker123!','pharmacist')]:
            page.goto('http://127.0.0.1:5000/login')
            page.locator('[name=email]').fill(account+'@medikahusada.local')
            page.locator('[name=password]').fill(password)
            page.get_by_role('button',name='Masuk ke akun').click()
            page.wait_for_url(f'**/{role}/dashboard')
            page.screenshot(path=str(OUT/f'{role}-dashboard.png'),full_page=True)
            if role=='patient':
                page.get_by_role('link',name='Lihat struk').first.click()
                assert page.locator('#receipt-dialog').is_visible()
                page.locator('[data-close-dialog]').click()
                page.goto('http://127.0.0.1:5000/appointments/new')
                page.wait_for_selector('.slot')
                page.screenshot(path=str(OUT/'booking.png'),full_page=True)
            page.get_by_role('button',name='Keluar',exact=True).click()
        assert not errors,errors
        browser.close()
        print('Browser check passed: 5 roles, receipt modal, booking slots, navigation, 4 viewport sizes; no JS errors.')


if __name__=='__main__': main()
