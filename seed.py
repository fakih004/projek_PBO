"""Idempotent demo data. Existing users and operational records are never reset."""
from datetime import date, timedelta
from clinic import create_app, db
from clinic.models import *
from clinic.services import AppointmentService, NotificationService


def seed_data(demo=True):
    accounts=[('admin','Siti Rahmawati',Role.ADMIN,'Admin123!'),
        ('perawat','Ns. Dian Lestari',Role.NURSE,'Perawat123!'),
        ('apoteker','apt. Rahmat Hidayat',Role.PHARMACIST,'Apoteker123!'),
        ('fakih','dr. Muhammad Fakih Nabal',Role.DOCTOR,'Dokter123!'),
        ('alia','dr. Alia Fransiska Dewi Arum Trilestari',Role.DOCTOR,'Dokter123!'),
        ('pasien','Budi Santoso',Role.PATIENT,'Pasien123!'),
        ('ratna','Ratna Permata',Role.PATIENT,'Pasien123!'),
        ('siti','Siti Aminah',Role.PATIENT,'Pasien123!')]
    new_database=not User.query.first()
    for index,(email,name,role,password) in enumerate(accounts):
        user=User.query.filter_by(email=email+'@medikahusada.local').first()
        if user: continue
        user=User(email=email+'@medikahusada.local',name=name,role=role,phone='081234567890')
        user.set_password(password); db.session.add(user); db.session.flush()
        if role==Role.DOCTOR:
            doctor=Doctor(user=user,specialty='Dokter Umum' if email=='fakih' else 'Obstetri dan Ginekologi',fee=75000 if email=='fakih' else 150000)
            db.session.add(doctor); db.session.flush()
            for day in range(6):
                db.session.add(DoctorSchedule(doctor=doctor,weekday=day,start='08:00' if email=='fakih' else '14:00',end='14:00' if email=='fakih' else '20:00',interval=30,quota=12))
        if role==Role.PATIENT:
            patient=Patient(user=user,nik=f'327320199000{index:04}',birth_date=date(1990,5,12),gender='Laki-laki' if email=='pasien' else 'Perempuan',
                address='Jl. Melati No. 12',bpjs='0001234567890' if email=='ratna' else '',bpjs_active=email=='ratna',allergies='Tidak diketahui',history='Tidak tercatat')
            db.session.add(patient); db.session.flush(); patient.mr=f'KMH-{date.today().year}-{patient.id:05}'
    names=['Paracetamol 500 mg','Amoxicillin 500 mg','Omeprazole 20 mg','Cetirizine 10 mg','Vitamin B Complex','Asam Folat','Ferrous Sulfate','Antacid','Ibuprofen 400 mg','ORS']
    for i,name in enumerate(names):
        if not Medicine.query.filter_by(name=name).first():
            medicine=Medicine(name=name,category='Obat',unit='sachet' if name=='ORS' else 'tablet',_stock=0,price=1000+i*500,minimum=20,expiry=date.today()+timedelta(days=365))
            db.session.add(medicine); db.session.flush()
            medicine.change_stock(15 if i==8 else 200,'Stok awal demo',User.query.filter_by(role=Role.ADMIN).first().id)
    db.session.commit()
    if new_database and demo:
        doctor=Doctor.query.first()
        patients=Patient.query.all()
        day=date.today()
        while not any(s['available'] for s in AppointmentService.slots(doctor.id,day)):
            day+=timedelta(days=1)
        slots=[s['time'] for s in AppointmentService.slots(doctor.id,day) if s['available']]
        for i,p in enumerate(patients):
            if i>=len(slots): break
            AppointmentService.book(p,dict(doctor_id=doctor.id,date=day.isoformat(),time=slots[i],complaint='Konsultasi kesehatan rutin',insurance='bpjs' if p.bpjs else 'general'))
        # A separate completed historical example gives the portal a printable receipt.
        p=patients[0]
        a=Appointment(patient=p,doctor=doctor,date=date.today()-timedelta(days=7),time='08:00',complaint='Kontrol kesehatan (data demo)',insurance=False,status=AppointmentStatus.COMPLETED)
        v=Visit(appointment=a,queue='DEMO-001',status=VisitStatus.COMPLETED)
        db.session.add(v); db.session.flush()
        v.nursing=NursingAssessment(nurse_id=User.query.filter_by(role=Role.NURSE).first().id,systolic=120,diastolic=80,temperature=36.5,weight=65,height=170,pulse=75,respiration=18,spo2=98,pain=0,complaint=a.complaint)
        v.examination=DoctorExamination(anamnesis='Kontrol rutin (contoh)',physical='Kondisi umum baik',diagnosis='Pemeriksaan kesehatan umum',treatment='Konsultasi',treatment_fee=0,recommendation='Pola hidup sehat',followup='Kontrol sesuai kebutuhan')
        medicine=Medicine.query.first()
        v.prescription=Prescription(status=PrescriptionStatus.DISPENSED,items=[PrescriptionItem(medicine=medicine,quantity=2,price=medicine.price,dosage='Sesuai petunjuk dokter',frequency='Sesuai kebutuhan',duration='Sesuai evaluasi',timing='Sesudah makan',instruction='Data resep demo, bukan anjuran pengobatan.')])
        medicine.change_stock(-2,'Resep historis demo',User.query.filter_by(role=Role.PHARMACIST).first().id,v.id)
        from clinic.services import BillingService
        inv=BillingService.invoice(v); inv.status=PaymentStatus.PAID
        inv.payment=Payment(admin_id=User.query.filter_by(role=Role.ADMIN).first().id,amount=inv.payable,method='Tunai',status=PaymentStatus.PAID,created_at=datetime.now()-timedelta(days=7))
        NotificationService.send(p,'Selamat datang. Riwayat contoh tersedia pada Rekam Medis Saya.')
        db.session.commit()


if __name__=='__main__':
    app=create_app()
    with app.app_context(): seed_data()
    print('Seed selesai. Akun demo tersedia; lihat README.md. Jalankan python app.py.')
