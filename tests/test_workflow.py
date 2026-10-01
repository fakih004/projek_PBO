from datetime import date, timedelta
import pytest
from clinic import db
from clinic.models import *
from clinic.services import *


PASSWORDS={'admin':'Admin123!','perawat':'Perawat123!','apoteker':'Apoteker123!','fakih':'Dokter123!','alia':'Dokter123!','pasien':'Pasien123!','ratna':'Pasien123!','siti':'Pasien123!'}


def login(client,role):
    client.post('/logout')
    return client.post('/login',data={'email':role+'@medikahusada.local','password':PASSWORDS[role]})


def book(client,insurance=False):
    login(client,'ratna' if insurance else 'pasien')
    d=Doctor.query.first(); day=date.today()+timedelta(days=1)
    while not AppointmentService.slots(d.id,day): day+=timedelta(days=1)
    response=client.post('/appointments/new',data=dict(doctor_id=d.id,date=day.isoformat(),time='08:00',complaint='Keluhan uji',insurance='bpjs' if insurance else 'general'))
    assert response.status_code==302
    a=Appointment.query.order_by(Appointment.id.desc()).first()
    assert a and a.status==AppointmentStatus.PENDING
    return a.id


def verified(client,insurance=False):
    aid=book(client,insurance)
    login(client,'admin')
    response=client.post(f'/appointments/{aid}/verify')
    assert response.status_code==302
    v=Visit.query.filter_by(appointment_id=aid).one()
    # Move test appointment to today so downstream clinical actions are valid.
    v.appointment.date=date.today(); db.session.commit()
    return v.id


def examined(client,insurance=False):
    vid=verified(client,insurance)
    login(client,'perawat')
    response=client.post(f'/visits/{vid}/nursing',data=dict(systolic=120,diastolic=80,temperature=36.6,weight=65,height=170,pulse=75,respiration=18,spo2=98,pain=1,complaint='Keluhan uji',notes='Catatan perawat'))
    assert response.status_code==302
    db.session.expire_all(); assert db.session.get(Visit,vid).status==VisitStatus.WAITING_DOCTOR
    login(client,'fakih'); client.post(f'/visits/{vid}/start')
    med=Medicine.query.first()
    response=client.post(f'/visits/{vid}/examination',data={'anamnesis':'Demam','physical':'Baik','diagnosis':'Diagnosis uji','treatment':'Pemeriksaan','treatment_fee':'15000','notes':'INTERNAL SECRET',
        'medicine_id[]':[str(med.id)],'quantity[]':['3'],'dosage[]':['1 tablet'],'frequency[]':['2 kali sehari'],'duration[]':['3 hari'],'timing[]':['Sesudah makan'],'instruction[]':['Uji resep']})
    assert response.status_code==302
    db.session.expire_all(); assert db.session.get(Visit,vid).status==VisitStatus.WAITING_PHARMACY
    return vid


@pytest.mark.parametrize('insurance',[False,True])
def test_complete_cross_role_workflow(client,insurance):
    vid=examined(client,insurance)
    v=db.session.get(Visit,vid); mid=v.prescription.items[0].medicine_id; before=db.session.get(Medicine,mid).stock
    # Referral is issued by the assigned doctor only.
    client.post(f'/visits/{vid}/referral',data=dict(hospital='RS Tujuan',specialist='Penyakit Dalam',reason='Evaluasi lanjut'))
    assert Referral.query.filter_by(visit_id=vid).count()==1
    login(client,'apoteker')
    for action,expected in [('start',VisitStatus.PHARMACY_PROCESSING),('ready',VisitStatus.MEDICINE_READY),('handover',VisitStatus.WAITING_PAYMENT)]:
        client.post(f'/visits/{vid}/pharmacy/{action}'); db.session.expire_all()
        assert db.session.get(Visit,vid).status==expected
    assert db.session.get(Medicine,mid).stock==before-3
    invoice=db.session.get(Visit,vid).invoice
    assert invoice.subtotal==75000+15000+invoice.items[-1].price*3
    assert invoice.payable==(0 if insurance else invoice.subtotal)
    login(client,'admin'); client.post(f'/visits/{vid}/pay',data=dict(method='Tunai',discount=0)); db.session.expire_all()
    assert db.session.get(Visit,vid).status==VisitStatus.COMPLETED
    assert Payment.query.count()==1
    client.post(f'/visits/{vid}/pay',data=dict(method='Tunai',discount=0))
    assert Payment.query.count()==1
    login(client,'ratna' if insurance else 'pasien')
    for url in [f'/visits/{vid}',f'/visits/{vid}/receipt',f'/visits/{vid}/prescription',f'/visits/{vid}/referral','/records','/api/patient/current-visit/status','/api/notifications']:
        response=client.get(url); assert response.status_code==200, url
        assert b'INTERNAL SECRET' not in response.data
    assert Notification.query.count()>=8
    assert StockMovement.query.filter_by(visit_id=vid).count()==1
    login(client,'siti'); assert client.get(f'/visits/{vid}/receipt').status_code==403


def test_authorization_and_record_isolation(client):
    vid=verified(client)
    login(client,'siti')
    assert client.get(f'/patient/medical-record/{vid}').status_code==403
    assert client.get(f'/visits/{vid}').status_code==403
    assert client.get('/admin/patients').status_code==403
    assert client.post(f'/appointments/{db.session.get(Visit,vid).appointment_id}/verify').status_code==403
    login(client,'alia'); assert client.get(f'/visits/{vid}').status_code==403
    assert client.post(f'/visits/{vid}/start').status_code==403
    login(client,'apoteker'); assert client.get(f'/visits/{vid}').status_code==403
    assert client.get('/records').status_code==403


def test_double_booking_cancel_reschedule(client):
    aid=book(client); a=db.session.get(Appointment,aid)
    data=dict(doctor_id=a.doctor_id,date=a.date.isoformat(),time=a.time,complaint='Uji',insurance='general')
    client.post('/appointments/new',data=data)
    assert Appointment.query.count()==1
    data['time']='08:30'
    client.post(f'/appointments/{aid}/reschedule',data=data); db.session.expire_all()
    assert db.session.get(Appointment,aid).time=='08:30'
    assert AppointmentService.slots(a.doctor_id,a.date)[0]['available']
    client.post(f'/appointments/{aid}/cancel'); db.session.expire_all()
    assert db.session.get(Appointment,aid).slot_key is None
    client.post('/appointments/new',data=data); assert Appointment.query.count()==2


def test_stock_shortage_rolls_back_and_ready_not_repeated(client):
    vid=examined(client); med=db.session.get(Visit,vid).prescription.items[0].medicine
    med._stock=1; db.session.commit(); mid=med.id
    login(client,'apoteker'); client.post(f'/visits/{vid}/pharmacy/start')
    client.post(f'/visits/{vid}/pharmacy/ready'); db.session.expire_all()
    assert db.session.get(Medicine,mid).stock==1
    assert db.session.get(Visit,vid).status==VisitStatus.PHARMACY_PROCESSING
    db.session.get(Medicine,mid).change_stock(10,'Tambah stok uji',User.query.filter_by(role=Role.PHARMACIST).first().id); db.session.commit()
    client.post(f'/visits/{vid}/pharmacy/ready'); client.post(f'/visits/{vid}/pharmacy/ready'); db.session.expire_all()
    assert db.session.get(Medicine,mid).stock==8
    assert StockMovement.query.filter_by(visit_id=vid).count()==1


def test_queue_unique_and_duplicate_verification(client):
    aid=book(client); login(client,'admin'); client.post(f'/appointments/{aid}/verify'); client.post(f'/appointments/{aid}/verify')
    assert Visit.query.count()==1
    v=Visit.query.first(); assert v.queue=='D1-001'
    client.post(f'/visits/{v.id}/queue/call'); db.session.expire_all(); assert db.session.get(Visit,v.id).queue_state=='CALLED'


@pytest.mark.parametrize('account,urls',[
    ('admin',['/admin/dashboard','/admin/patients','/admin/patients/1','/appointments','/appointments/new','/admin/doctors','/medicines','/admin/users','/admin/reports','/admin/reports?export=csv','/records','/referrals']),
    ('pasien',['/patient/dashboard','/appointments','/appointments/new','/profile','/records','/referrals']),
    ('fakih',['/doctor/dashboard','/records','/referrals']),
    ('perawat',['/nurse/dashboard']),('apoteker',['/pharmacist/dashboard','/medicines'])])
def test_role_pages_render(client,account,urls):
    response=login(client,account); assert response.status_code==302
    for url in urls+['/api/dashboard-fragment','/api/notifications']:
        response=client.get(url); assert response.status_code==200,url


def test_public_and_registration(client):
    for url in ['/','/login','/register']:
        assert client.get(url).status_code==200
    data=dict(name='Pasien Baru',nik='1234567890123456',birth_date='1995-03-01',gender='Perempuan',address='Jl. Baru',phone='081234567899',email='baru@example.com',password='Testing123!',confirm='Testing123!')
    client.post('/register',data=data)
    patient=Patient.query.filter_by(nik=data['nik']).one()
    assert patient.mr and patient.user.check_password('Testing123!')
    assert 'Testing123!' not in patient.user._password_hash
    assert client.get('/profile').status_code==200


def test_csrf_required(app):
    app.config['WTF_CSRF_ENABLED']=True
    client=app.test_client()
    assert client.post('/login',data={'email':'admin@medikahusada.local','password':'Admin123!'}).status_code==400


def test_no_medication_and_out_of_order(client):
    vid=verified(client)
    login(client,'fakih')
    client.post(f'/visits/{vid}/start'); db.session.expire_all()
    assert db.session.get(Visit,vid).status==VisitStatus.WAITING_NURSE
    login(client,'perawat')
    client.post(f'/visits/{vid}/nursing',data=dict(systolic=120,diastolic=80,temperature=36.6,weight=65,height=170,pulse=75,respiration=18,spo2=98,pain=1,complaint='Uji'))
    login(client,'fakih'); client.post(f'/visits/{vid}/start')
    client.post(f'/visits/{vid}/examination',data=dict(anamnesis='Uji',physical='Uji',diagnosis='Uji',treatment_fee=0))
    db.session.expire_all(); v=db.session.get(Visit,vid)
    assert v.status==VisitStatus.WAITING_PAYMENT
    assert v.invoice.payable==75000
    assert v.prescription is None


def test_verified_reschedule_releases_slot_and_requires_reverification(client):
    aid=book(client)
    login(client,'admin'); client.post(f'/appointments/{aid}/verify')
    a=db.session.get(Appointment,aid); old_key=a.slot_key; vid=a.visit.id
    login(client,'pasien')
    client.post(f'/appointments/{aid}/reschedule',data=dict(doctor_id=a.doctor_id,date=a.date.isoformat(),time='09:00',complaint='Jadwal baru',insurance='general'))
    db.session.expire_all(); a=db.session.get(Appointment,aid)
    assert a.status==AppointmentStatus.RESCHEDULED
    assert a.visit.status==VisitStatus.WAITING_VERIFICATION
    assert a.slot_key!=old_key
    login(client,'admin'); client.post(f'/appointments/{aid}/verify'); db.session.expire_all()
    assert db.session.get(Visit,vid).status==VisitStatus.WAITING_NURSE
    assert db.session.get(Visit,vid).queue=='D1-002'
    login(client,'pasien'); client.post(f'/appointments/{aid}/cancel'); db.session.expire_all()
    assert db.session.get(Visit,vid).status==VisitStatus.CANCELLED
    assert db.session.get(Appointment,aid).slot_key is None
    assert client.get('/patient/dashboard').status_code==200


def test_invalid_input_and_reminders(client):
    aid=book(client); a=db.session.get(Appointment,aid)
    # Reminder generation must be idempotent for repeated polling.
    from datetime import datetime
    when=datetime.now()+timedelta(hours=1)
    a.date=when.date(); a.time=when.strftime('%H:%M'); db.session.commit()
    client.get('/api/notifications'); client.get('/api/notifications')
    assert Notification.query.filter(Notification.unique_key.isnot(None)).count()==1
    client.post('/api/notifications/read')
    assert Notification.query.filter_by(user_id=a.patient.user_id,read=False).count()==0
    login(client,'admin'); client.post(f'/appointments/{aid}/verify')
    vid=Visit.query.one().id
    login(client,'perawat')
    client.post(f'/visits/{vid}/nursing',data=dict(systolic='nan',diastolic=80,temperature=36.6,weight=65,height=0,pulse=75,respiration=18,spo2=98,pain=1,complaint='Uji'))
    assert NursingAssessment.query.count()==0
    assert Visit.query.one().status==VisitStatus.WAITING_NURSE


def test_multiple_medicine_shortage_is_atomic(client):
    vid=examined(client)
    p=db.session.get(Visit,vid).prescription
    second=Medicine.query.filter(Medicine.id!=p.items[0].medicine_id).first()
    second._stock=1
    p.items.append(PrescriptionItem(medicine=second,quantity=10,price=second.price,dosage='Uji',frequency='Uji',duration='Uji',timing='Uji'))
    first_id=p.items[0].medicine_id; first_stock=p.items[0].medicine.stock
    db.session.commit()
    login(client,'apoteker'); client.post(f'/visits/{vid}/pharmacy/start'); client.post(f'/visits/{vid}/pharmacy/ready')
    db.session.expire_all()
    assert db.session.get(Medicine,first_id).stock==first_stock
    assert StockMovement.query.filter_by(visit_id=vid).count()==0
    assert db.session.get(Visit,vid).status==VisitStatus.PHARMACY_PROCESSING


def test_admin_configuration_and_stock(client):
    login(client,'admin')
    client.post('/admin/doctors',data=dict(name='dr. Uji',email='uji@medikahusada.local',password='Testing123!',specialty='Dokter Umum',fee=80000,active='on'))
    doctor=Doctor.query.join(User).filter(User.email=='uji@medikahusada.local').one()
    client.post('/admin/schedules',data=dict(doctor_id=doctor.id,weekday=0,start='08:00',end='10:00',interval=30,quota=3))
    monday=date.today()+timedelta(days=(7-date.today().weekday())%7+7)
    assert len(AppointmentService.slots(doctor.id,monday))==3
    client.post('/medicines',data=dict(name='Obat uji',category='Umum',unit='tablet',price=2000,minimum=5,delta=10,reason='Penerimaan'))
    medicine=Medicine.query.filter_by(name='Obat uji').one()
    assert medicine.stock==10
    client.post('/medicines',data=dict(id=medicine.id,name=medicine.name,category='Umum',unit='tablet',price=2000,minimum=5,delta=-11,reason='Penyesuaian'))
    db.session.expire_all(); assert db.session.get(Medicine,medicine.id).stock==10
    client.post('/admin/users',data=dict(name='Petugas uji',email='petugas@example.com',password='Testing123!',role='nurse'))
    user=User.query.filter_by(email='petugas@example.com').one()
    client.post('/admin/users',data=dict(id=user.id))
    client.post('/logout')
    response=client.post('/login',data=dict(email=user.email,password='Testing123!'))
    assert response.status_code==200
    assert client.get('/nurse/dashboard').status_code==302


def test_parallel_booking_database_constraint(app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier=Barrier(2)
    day=date.today()+timedelta(days=1)
    while not AppointmentService.slots(1,day): day+=timedelta(days=1)
    def attempt(account):
        with app.app_context():
            client=app.test_client(); login(client,account)
            barrier.wait(timeout=15)
            return client.post('/appointments/new',data=dict(doctor_id=1,date=day.isoformat(),time='08:00',complaint='Booking bersamaan',insurance='general')).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(attempt,['pasien','ratna']))==[302,302]
    db.session.expire_all()
    assert Appointment.query.count()==1
    assert Notification.query.count()==1


def test_nurse_completed_screening_and_clinical_page_render(client):
    vid=examined(client)
    login(client,'perawat')
    response=client.get('/nurse/dashboard')
    assert response.status_code==200 and b'Selesai screening' in response.data
    assert client.get(f'/visits/{vid}').status_code==200
    assert b'INTERNAL SECRET' not in client.get(f'/visits/{vid}').data
    login(client,'fakih')
    assert b'INTERNAL SECRET' in client.get(f'/visits/{vid}').data
    # Cancel/reschedule cannot rewind a clinical visit.
    login(client,'pasien'); a=db.session.get(Visit,vid).appointment
    client.post(f'/appointments/{a.id}/cancel'); db.session.expire_all()
    assert db.session.get(Visit,vid).status==VisitStatus.WAITING_PHARMACY
    assert db.session.get(Appointment,a.id).slot_key is not None


def test_database_persists_across_application_restart(app,client):
    from clinic import create_app
    aid=book(client)
    restarted=create_app({'TESTING':True,'WTF_CSRF_ENABLED':False,'SECRET_KEY':'test-only',
        'SQLALCHEMY_DATABASE_URI':app.config['SQLALCHEMY_DATABASE_URI']})
    with restarted.app_context():
        another=restarted.test_client(); login(another,'admin')
        assert Appointment.query.count()==1
        assert another.get('/appointments').status_code==200
        another.post(f'/appointments/{aid}/verify')
        assert Visit.query.count()==1
        db.session.remove(); db.engine.dispose()
