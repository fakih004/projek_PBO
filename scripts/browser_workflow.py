"""Isolated real-browser workflow; does not modify the localhost demo database."""
import sys
import tempfile
import threading
import logging
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server
from clinic import create_app, db
from clinic.models import DoctorSchedule, Visit, Payment, Medicine
from seed import seed_data

OUT=Path(__file__).resolve().parents[1]/'docs'/'screenshots'


def capture(page,name):
    for button in page.locator('#toasts .toast button').all():
        if button.is_visible(): button.click()
    page.evaluate('window.scrollTo(0, 0)')
    page.screenshot(path=str(OUT/name),full_page=True)


def main():
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='medika-browser-') as folder:
        app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(Path(folder)/'browser.db')})
        with app.app_context():
            seed_data(demo=False)
            # Broad fixture schedule makes the test independent of ordinary practice hours.
            for schedule in DoctorSchedule.query.all():
                schedule.start='00:00'; schedule.end='23:59'; schedule.interval=1; schedule.quota=1440
            # Sunday also needs a schedule for tests run that day.
            if not DoctorSchedule.query.filter_by(doctor_id=1,weekday=date.today().weekday()).first():
                db.session.add(DoctorSchedule(doctor_id=1,weekday=date.today().weekday(),start='00:00',end='23:59',interval=1,quota=1440))
            db.session.commit()
        server=make_server('127.0.0.1',5001,app,threaded=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            with sync_playwright() as p:
                edge=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
                browser=p.chromium.launch(executable_path=str(edge) if edge.exists() else None,headless=True)
                errors=[]
                def account(name,password):
                    context=browser.new_context(viewport={'width':1366,'height':900})
                    page=context.new_page(); page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto('http://127.0.0.1:5001/login')
                    page.locator('[name=email]').fill(name+'@medikahusada.local'); page.locator('[name=password]').fill(password)
                    page.get_by_role('button',name='Masuk ke akun').click(); page.wait_for_url('**/dashboard')
                    return page
                patient=account('pasien','Pasien123!')
                admin=account('admin','Admin123!')
                nurse=account('perawat','Perawat123!')
                doctor=account('fakih','Dokter123!')
                pharmacist=account('apoteker','Apoteker123!')
                patient.goto('http://127.0.0.1:5001/appointments/new')
                # Avoid selecting the next minute, which can expire while filling the form.
                patient.locator('.slot:not([disabled])').last.click()
                patient.locator('[name=complaint]').fill('Keluhan untuk pengujian alur browser')
                patient.locator('#booking-submit').click(); patient.wait_for_url('**/appointments')
                expect(patient.locator('tbody tr')).to_contain_text('Menunggu verifikasi')
                patient.goto('http://127.0.0.1:5001/patient/dashboard')
                # Admin sees the new appointment through polling, without navigating or refreshing.
                admin.get_by_role('button',name='Verifikasi',exact=True).first.click(timeout=15000)
                admin.locator('#confirm-yes').click()
                expect(admin.locator('.toast').last).to_contain_text('berhasil')
                expect(patient.locator('.progress-card')).to_be_visible(timeout=15000)
                expect(patient.locator('.progress-card')).to_contain_text('Menunggu pemeriksaan perawat')
                with app.app_context(): vid=Visit.query.one().id
                nurse.goto(f'http://127.0.0.1:5001/visits/{vid}')
                vitals=dict(systolic=120,diastolic=80,temperature=36.7,weight=65,height=170,pulse=76,respiration=18,spo2=98,pain=2)
                for name,value in vitals.items(): nurse.locator(f'[name={name}]').fill(str(value))
                expect(nurse.locator('#bmi-preview')).to_contain_text('22.5')
                capture(nurse,'nurse-examination.png')
                nurse.get_by_role('button',name='Simpan & kirim ke dokter').click(); nurse.wait_for_url('**/nurse/dashboard')
                doctor.goto(f'http://127.0.0.1:5001/visits/{vid}')
                doctor.get_by_role('button',name='Mulai pemeriksaan',exact=True).click(); doctor.locator('#confirm-yes').click()
                doctor.locator('[name=anamnesis]').fill('Anamnesis uji browser')
                doctor.locator('[name=physical]').fill('Pemeriksaan fisik uji browser')
                doctor.locator('[name=diagnosis]').fill('Diagnosis uji browser')
                doctor.locator('[name=treatment_fee]').fill('15000')
                for index in range(2):
                    doctor.locator('#add-medicine').click(); row=doctor.locator('.prescription-row').nth(index)
                    row.locator('select[name="medicine_id[]"]').select_option(str(index+1))
                    for name,value in {'quantity':'2','dosage':'1 tablet','frequency':'2 kali sehari','duration':'2 hari'}.items():
                        row.locator(f'[name="{name}[]"]').fill(value)
                capture(doctor,'doctor-examination.png')
                doctor.get_by_role('button',name='Selesaikan pemeriksaan').click()
                expect(doctor.locator('.page-head .badge')).to_contain_text('Resep diterima')
                pharmacist.goto(f'http://127.0.0.1:5001/visits/{vid}')
                pharmacist.get_by_role('button',name='Mulai racik',exact=True).click()
                capture(pharmacist,'pharmacist-prescription.png')
                pharmacist.get_by_role('button',name='Obat siap',exact=True).click(); pharmacist.locator('#confirm-yes').click()
                expect(patient.locator('.progress-card .section-head .badge')).to_contain_text('Obat siap',timeout=15000)
                capture(patient,'patient-queue.png')
                pharmacist.get_by_role('button',name='Serahkan ke kasir/admin').click(); pharmacist.locator('#confirm-yes').click()
                admin.goto(f'http://127.0.0.1:5001/visits/{vid}')
                admin.get_by_role('button',name='Konfirmasi pembayaran',exact=True).click(); admin.locator('#confirm-yes').click()
                admin.wait_for_url('**/receipt'); expect(admin.locator('.receipt')).to_contain_text('Lunas')
                capture(admin,'receipt.png')
                expect(patient.locator('.progress-card')).to_contain_text('Pelayanan Anda telah selesai.',timeout=15000)
                for width in [375,768,1366,1920]:
                    doctor.set_viewport_size({'width':width,'height':900})
                    assert doctor.evaluate('document.documentElement.scrollWidth <= innerWidth'),f'Clinical overflow {width}'
                with app.app_context():
                    assert Payment.query.one().amount==95000
                    assert db.session.get(Medicine,1).stock==198
                    assert db.session.get(Medicine,2).stock==198
                    assert Visit.query.one().prescription.items.__len__()==2
                assert not errors,errors
                browser.close()
                print('Browser workflow passed: booking > admin verification > nurse > doctor (2 medicines) > pharmacy > payment; cross-session polling and database persistence verified.')
        finally:
            server.shutdown(); thread.join()
            with app.app_context(): db.session.remove(); db.engine.dispose()


if __name__=='__main__': main()
