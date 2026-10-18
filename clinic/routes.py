from datetime import date, datetime, timedelta
from functools import wraps
import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, Response
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError
from . import db
from .models import *
from .services import *

web=Blueprint('web',__name__)


def roles(*allowed):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args,**kwargs):
            if current_user.role not in allowed: abort(403)
            return fn(*args,**kwargs)
        return wrapped
    return decorator


def mutate(fn, destination):
    try:
        result=fn()
        db.session.commit()
        message=result if isinstance(result,str) else 'Perubahan berhasil disimpan.'
        if request.headers.get('X-Requested-With')=='fetch': return jsonify(ok=True,message=message)
        flash(message,'success')
    except (ValueError,IntegrityError,OperationalError) as error:
        db.session.rollback()
        message=str(error) if isinstance(error,ValueError) else 'Data bentrok atau telah berubah. Periksa email/NIK/slot, lalu coba lagi.'
        if request.headers.get('X-Requested-With')=='fetch': return jsonify(ok=False,message=message),409
        flash(message,'error')
    return redirect(destination)


def visit_access(visit_id, clinical=False):
    v=db.get_or_404(Visit,visit_id)
    role=current_user.role
    if role==Role.PATIENT and v.patient.user_id!=current_user.id: abort(403)
    if role==Role.DOCTOR and v.doctor.user_id!=current_user.id: abort(403)
    if role==Role.NURSE and v.status!=VisitStatus.WAITING_NURSE and not (v.nursing and v.nursing.nurse_id==current_user.id): abort(403)
    if role==Role.PHARMACIST and (clinical or not v.prescription): abort(403)
    if role==Role.CASHIER and not v.invoice: abort(403)
    return v


def appointment_access(aid):
    a=db.get_or_404(Appointment,aid)
    if current_user.role==Role.PATIENT and a.patient.user_id!=current_user.id: abort(403)
    if current_user.role not in (Role.PATIENT,Role.ADMIN): abort(403)
    return a


def scoped_visits():
    query=Visit.query.join(Appointment)
    if current_user.role==Role.PATIENT: query=query.filter(Appointment.patient_id==current_user.patient.id)
    elif current_user.role==Role.DOCTOR: query=query.filter(Appointment.doctor_id==current_user.doctor.id)
    elif current_user.role==Role.NURSE:
        query=query.outerjoin(NursingAssessment).filter(or_(Visit.status==VisitStatus.WAITING_NURSE,NursingAssessment.nurse_id==current_user.id))
    elif current_user.role==Role.PHARMACIST: query=query.join(Prescription)
    elif current_user.role==Role.CASHIER: query=query.filter(Visit.status==VisitStatus.WAITING_PAYMENT)
    return query


@web.get('/')
def index():
    doctors=Doctor.query.join(User).filter(User.active.is_(True)).all()
    today=date.today()
    return render_template('landing.html',doctors=doctors,today=today,
        availability={d.id:AppointmentService.slots(d.id,today) for d in doctors})


@web.route('/login',methods=['GET','POST'])
def login_page():
    if current_user.is_authenticated: return redirect(url_for('web.dashboard'))
    if request.method=='POST':
        user=User.query.filter_by(email=request.form.get('email','').strip().lower()).first()
        if user and user.active and user.check_password(request.form.get('password','')):
            login_user(user)
            return redirect(url_for('web.dashboard'))
        flash('Email atau password tidak benar, atau akun tidak aktif.','error')
    return render_template('auth.html',register=False)


@web.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        try:
            user=PatientService.register(request.form)
            db.session.commit()
            login_user(user)
            return redirect(url_for('web.dashboard'))
        except (ValueError,IntegrityError) as error:
            db.session.rollback()
            flash(str(error) if isinstance(error,ValueError) else 'Email atau NIK sudah terdaftar.','error')
            return render_template('auth.html',register=True),400
    return render_template('auth.html',register=True)


@web.post('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('web.index'))


@web.get('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('web.role_dashboard',role=current_user.role.value))


@web.get('/<role>/dashboard')
@login_required
def role_dashboard(role):
    if role!=current_user.role.value: abort(403)
    if current_user.role==Role.CASHIER: return redirect(url_for('web.cashier_payments'))
    return render_template('dashboard.html',**dashboard_data())


def dashboard_data():
    today=date.today()
    doctor_schedule_by_day={}
    if current_user.role==Role.DOCTOR:
        # Batasi jadwal dashboard ke profil dokter pada sesi yang sedang aktif.
        doctor_schedules=DoctorSchedule.query.filter_by(doctor_id=current_user.doctor.id).order_by(DoctorSchedule.weekday).all()
        doctor_schedule_by_day={schedule.weekday:schedule for schedule in doctor_schedules}
    visits=scoped_visits().order_by(Appointment.date.desc(),Visit.id.desc()).all()
    appointments=Appointment.query
    if current_user.role==Role.PATIENT: appointments=appointments.filter_by(patient_id=current_user.patient.id)
    elif current_user.role==Role.DOCTOR: appointments=appointments.filter_by(doctor_id=current_user.doctor.id)
    elif current_user.role!=Role.ADMIN: appointments=appointments.filter(db.false())
    appointments=appointments.order_by(Appointment.date.desc(),Appointment.time).limit(30).all()
    daily=[v for v in visits if v.appointment.date==today]
    metrics={s.value:sum(v.status==s for v in daily) for s in VisitStatus}
    revenue=0; month_revenue=0
    if current_user.role==Role.ADMIN:
        payments=Payment.query.all()
        revenue=sum(p.amount for p in payments if p.created_at.date()==today)
        month_revenue=sum(p.amount for p in payments if p.created_at.year==today.year and p.created_at.month==today.month)
    queue_visits=sorted([v for v in visits if v.status not in (VisitStatus.COMPLETED,VisitStatus.CANCELLED,VisitStatus.WAITING_VERIFICATION)],
        key=lambda v:(v.appointment.date,v.queue_state=='SKIPPED',v.appointment.time,v.id))
    screened=sum(bool(v.nursing and v.nursing.nurse_id==current_user.id) for v in daily) if current_user.role==Role.NURSE else 0
    return dict(visits=(visits if current_user.role==Role.PATIENT else queue_visits)[:30],appointments=appointments,metrics=metrics,today=today,daily=daily,screened=screened,
        revenue=revenue,month_revenue=month_revenue,doctors=Doctor.query.all(),doctor_schedule_by_day=doctor_schedule_by_day,
        low_stock=Medicine.query.filter(Medicine._stock<=Medicine.minimum).all() if current_user.role in (Role.ADMIN,Role.PHARMACIST) else [],
        active_visit=next((v for v in visits if v.status not in (VisitStatus.COMPLETED,VisitStatus.CANCELLED,VisitStatus.WAITING_VERIFICATION)),
            next((v for v in visits if v.status==VisitStatus.COMPLETED),None)))


@web.get('/api/dashboard-fragment')
@login_required
def dashboard_fragment():
    return render_template('_dashboard.html',**dashboard_data())


@web.route('/profile',methods=['GET','POST'])
@roles(Role.PATIENT)
def profile():
    if request.method=='POST': return mutate(lambda:PatientService.profile(current_user.patient,request.form),url_for('web.profile'))
    return render_template('profile.html',patient=current_user.patient)


@web.route('/appointments/new',methods=['GET','POST'])
@roles(Role.PATIENT,Role.ADMIN)
def booking():
    if request.method=='POST':
        patient=current_user.patient if current_user.role==Role.PATIENT else db.get_or_404(Patient,request.form.get('patient_id',type=int))
        return mutate(lambda:AppointmentService.book(patient,request.form),url_for('web.appointments'))
    return render_template('booking.html',appointment=None,doctors=Doctor.query.join(User).filter(User.active.is_(True)).all(),
        patients=Patient.query.all() if current_user.role==Role.ADMIN else [],today=date.today())


@web.get('/api/slots')
def slots():
    try:
        day=date.fromisoformat(request.args.get('date',''))
        doctor=int(request.args.get('doctor_id',''))
    except (ValueError,TypeError): return jsonify(slots=[]),400
    return jsonify(slots=AppointmentService.slots(doctor,day))


@web.get('/appointments')
@roles(Role.PATIENT,Role.ADMIN)
def appointments():
    query=Appointment.query.join(Patient).join(User,Patient.user_id==User.id)
    if current_user.role==Role.PATIENT: query=query.filter(Patient.user_id==current_user.id)
    q=request.args.get('q','').strip()
    if q: query=query.filter(or_(User.name.contains(q),Patient.nik.contains(q),Patient.mr.contains(q),User.phone.contains(q)))
    status=request.args.get('status','')
    if status in AppointmentStatus._value2member_map_: query=query.filter(Appointment.status==AppointmentStatus(status))
    if request.args.get('date'):
        try: query=query.filter(Appointment.date==date.fromisoformat(request.args['date']))
        except ValueError: abort(400)
    page=db.paginate(query.order_by(Appointment.date.desc(),Appointment.time).statement,page=request.args.get('page',1,type=int),per_page=12,error_out=False)
    return render_template('appointments.html',page=page,statuses=AppointmentStatus)


@web.route('/appointments/<int:aid>/reschedule',methods=['GET','POST'])
@roles(Role.PATIENT,Role.ADMIN)
def reschedule(aid):
    a=appointment_access(aid)
    if request.method=='POST': return mutate(lambda:AppointmentService.book(a.patient,request.form,a),url_for('web.appointments'))
    return render_template('booking.html',appointment=a,doctors=Doctor.query.join(User).filter(User.active.is_(True)).all(),patients=[],today=date.today())


@web.post('/appointments/<int:aid>/<action>')
@roles(Role.PATIENT,Role.ADMIN)
def appointment_action(aid,action):
    a=appointment_access(aid)
    if action in ('verify','reject') and current_user.role!=Role.ADMIN: abort(403)
    if action not in ('verify','reject','cancel'): abort(404)
    return mutate(lambda:AppointmentService.verify(a) if action=='verify' else AppointmentService.cancel(a,action=='reject'),url_for('web.appointments'))


@web.get('/records')
@roles(Role.PATIENT,Role.ADMIN,Role.DOCTOR)
def records():
    return render_template('records.html',visits=scoped_visits().order_by(Visit.id.desc()).all())


@web.get('/admin/referrals')
@roles(Role.ADMIN)
def referrals():
    q=request.args.get('q','').strip()
    requests=ReferralRequest.query.filter(ReferralRequest.status=='PENDING').join(Visit).join(Appointment).join(Patient,Appointment.patient_id==Patient.id).join(User,Patient.user_id==User.id)
    issued=Visit.query.join(Appointment).join(Referral)
    if q:
        match=or_(User.name.contains(q),Patient.mr.contains(q))
        requests=requests.filter(or_(match,ReferralRequest.hospital.contains(q),ReferralRequest.specialist.contains(q),ReferralRequest.reason.contains(q)))
        issued=issued.join(Patient,Appointment.patient_id==Patient.id).join(User,Patient.user_id==User.id).filter(or_(
            match,Referral.number.contains(q),Referral.hospital.contains(q),Referral.specialist.contains(q)))
    page=db.paginate(issued.order_by(Referral.created_at.desc(),Visit.id.desc()).statement,
        page=request.args.get('page',1,type=int),per_page=12,error_out=False)
    legacy_visits=Visit.query.join(Appointment).filter(Visit.examination.has(),
        ~Visit.referral.has(),~Visit.referral_request.has()).order_by(Appointment.date.desc(),Visit.id.desc()).all()
    return render_template('referrals.html',page=page,requests=requests.order_by(ReferralRequest.created_at.asc()).all(),legacy_visits=legacy_visits)


@web.post('/visits/<int:visit_id>/referral-request')
@roles(Role.DOCTOR)
def referral_request(visit_id):
    v=visit_access(visit_id)
    def create_request():
        if not v.examination: raise ValueError('Selesaikan pemeriksaan dokter sebelum mengajukan rujukan.')
        if v.referral or v.referral_request: raise ValueError('Kunjungan ini sudah memiliki surat atau pengajuan rujukan.')
        db.session.add(ReferralRequest(visit=v,
            specialist=required(request.form,'specialist',160),
            hospital=required(request.form,'hospital',160),
            reason=required(request.form,'reason',4000)))
        return 'Permintaan rujukan berhasil dikirim ke admin.'
    return mutate(create_request,url_for('web.visit',visit_id=v.id))


@web.post('/admin/referrals/<int:request_id>/issue')
@roles(Role.ADMIN)
def issue_referral(request_id):
    referral_request=db.get_or_404(ReferralRequest,request_id)
    def issue():
        if referral_request.status!='PENDING' or referral_request.visit.referral:
            raise ValueError('Permintaan ini sudah diproses.')
        specialist=required(request.form,'specialist',160)
        hospital=required(request.form,'hospital',160)
        notes=str(request.form.get('notes',''))[:4000]
        v=referral_request.visit
        db.session.add(Referral(visit=v,number=f'RJK-{date.today():%Y%m%d}-{v.id:05}',
            specialist=specialist,hospital=hospital,reason=referral_request.reason,notes=notes))
        referral_request.status='ISSUED'
        referral_request.admin=current_user
        referral_request.completed_at=datetime.now()
        return 'Surat rujukan berhasil dibuat.'
    return mutate(issue,url_for('web.referrals'))


@web.post('/admin/referrals/archive')
@roles(Role.ADMIN)
def archive_referral():
    def save_existing():
        v=db.get_or_404(Visit,request.form.get('visit_id',type=int))
        if v.referral or v.referral_request or not v.examination:
            raise ValueError('Kunjungan ini tidak tersedia untuk pencatatan surat lama.')
        try:
            issued_date=date.fromisoformat(request.form.get('issued_date',''))
        except ValueError:
            raise ValueError('Tanggal surat tidak valid.')
        db.session.add(Referral(visit=v,number=required(request.form,'number',40),
            specialist=required(request.form,'specialist',160),hospital=required(request.form,'hospital',160),
            reason=required(request.form,'reason',4000),notes=str(request.form.get('notes',''))[:4000],
            created_at=datetime.combine(issued_date,datetime.min.time())))
        return 'Surat rujukan lama berhasil dicatat.'
    return mutate(save_existing,url_for('web.referrals'))


@web.get('/patient/medical-record/<int:visit_id>')
@roles(Role.PATIENT)
def patient_record(visit_id):
    visit_access(visit_id,True)
    return redirect(url_for('web.visit',visit_id=visit_id))


@web.get('/visits/<int:visit_id>')
@login_required
def visit(visit_id):
    v=visit_access(visit_id)
    history=[]
    if current_user.role==Role.DOCTOR:
        history=Visit.query.join(Appointment).filter(Appointment.patient_id==v.patient.id,
            Appointment.doctor_id==v.doctor.id,Visit.id!=v.id).all()
    return render_template('visit.html',v=v,history=history,medicines=Medicine.query.order_by(Medicine.name).all() if current_user.role==Role.DOCTOR else [])


@web.post('/visits/<int:visit_id>/nursing')
@roles(Role.NURSE)
def nursing(visit_id):
    v=visit_access(visit_id)
    return mutate(lambda:WorkflowService.nurse(v,current_user,request.form),url_for('web.dashboard'))


@web.post('/visits/<int:visit_id>/start')
@roles(Role.DOCTOR)
def start_exam(visit_id):
    v=visit_access(visit_id)
    return mutate(lambda:WorkflowService.transition(v,[VisitStatus.WAITING_DOCTOR],VisitStatus.WITH_DOCTOR),url_for('web.visit',visit_id=v.id))


@web.post('/visits/<int:visit_id>/examination')
@roles(Role.DOCTOR)
def examination(visit_id):
    v=visit_access(visit_id)
    def action():
        keys=['medicine_id','quantity','dosage','frequency','duration','timing','instruction']
        columns={key:request.form.getlist(key+'[]') for key in keys}
        if len({len(col) for col in columns.values()})!=1: raise ValueError('Data resep tidak lengkap.')
        items=[dict(zip(keys,values)) for values in zip(*(columns[key] for key in keys))]
        WorkflowService.examine(v,request.form,items)
    return mutate(action,url_for('web.visit',visit_id=v.id))


@web.post('/visits/<int:visit_id>/pharmacy/<action>')
@roles(Role.PHARMACIST)
def pharmacy(visit_id,action):
    v=visit_access(visit_id)
    return mutate(lambda:PharmacyService.process(v,action,current_user),url_for('web.visit',visit_id=v.id))


@web.get('/cashier/payments')
@roles(Role.CASHIER)
def cashier_payments():
    visits=Visit.query.join(Appointment).filter(Visit.status==VisitStatus.WAITING_PAYMENT).order_by(Appointment.date,Appointment.time,Visit.id).all()
    return render_template('cashier_payments.html',visits=visits)


@web.post('/visits/<int:visit_id>/pay')
@roles(Role.CASHIER)
def pay(visit_id):
    v=visit_access(visit_id)
    def action():
        payment=BillingService.pay(v,current_user,request.form)
        return f'Pembayaran berhasil dikonfirmasi. Kembalian: Rp{payment.cash_change:,}.' if payment.method=='Tunai' else 'Pembayaran berhasil dikonfirmasi.'
    return mutate(action,url_for('web.receipt',visit_id=v.id))


@web.get('/visits/<int:visit_id>/receipt')
@roles(Role.PATIENT,Role.ADMIN,Role.CASHIER)
def receipt(visit_id):
    v=visit_access(visit_id)
    if not v.invoice: abort(404)
    return render_template('receipt.html',v=v,embedded=request.args.get('embedded')=='1')


@web.get('/admin/expense-invoices/<int:expense_id>')
@roles(Role.ADMIN)
def expense_receipt(expense_id):
    expense=db.get_or_404(ExpenseInvoice,expense_id)
    return render_template('expense_receipt.html',expense=expense)


@web.get('/visits/<int:visit_id>/prescription')
@roles(Role.PATIENT,Role.DOCTOR,Role.PHARMACIST)
def prescription(visit_id):
    v=visit_access(visit_id)
    if not v.prescription: abort(404)
    return render_template('prescription.html',v=v)


@web.post('/visits/<int:visit_id>/queue/<action>')
@roles(Role.ADMIN)
def queue_action(visit_id,action):
    v=visit_access(visit_id)
    def change():
        if v.status not in (VisitStatus.WAITING_NURSE,VisitStatus.WAITING_DOCTOR): raise ValueError('Pasien tidak berada pada antrean pemeriksaan.')
        if action not in ('call','skip','restore'): raise ValueError('Aksi antrean tidak valid.')
        v.queue_state={'call':'CALLED','skip':'SKIPPED','restore':'WAITING'}[action]
        message={'call':f'Antrean {v.queue}, silakan menuju ruang '+('perawat.' if v.status==VisitStatus.WAITING_NURSE else 'dokter.'),
                 'skip':'Antrean dilewati. Silakan hubungi petugas untuk dipanggil kembali.','restore':'Antrean dikembalikan ke daftar tunggu.'}[action]
        NotificationService.send(v.patient,message)
    return mutate(change,url_for('web.dashboard'))


@web.get('/api/patient/current-visit/status')
@roles(Role.PATIENT)
def current_status():
    v=scoped_visits().order_by(Visit.id.desc()).first()
    return jsonify(visit_id=v.id if v else None,queue_number=v.queue if v else None,
        status=v.status.value if v else 'PENDING',message=LABELS[v.status.value] if v else LABELS['PENDING'])


@web.get('/api/notifications')
@login_required
def notifications():
    NotificationService.reminders(current_user); db.session.commit()
    query=Notification.query.filter_by(user_id=current_user.id)
    return jsonify(unread=query.filter_by(read=False).count(),items=[dict(id=n.id,message=n.message,read=n.read,time=n.created_at.isoformat()) for n in query.order_by(Notification.id.desc()).limit(30)])


@web.post('/api/notifications/read')
@login_required
def read_notifications():
    Notification.query.filter_by(user_id=current_user.id,read=False).update({'read':True})
    db.session.commit()
    return jsonify(ok=True,message='Notifikasi ditandai dibaca.')


@web.route('/admin/patients',methods=['GET','POST'])
@roles(Role.ADMIN)
def patients():
    if request.method=='POST': return mutate(lambda:PatientService.register(request.form),url_for('web.patients'))
    query=Patient.query.join(User)
    q=request.args.get('q','').strip()
    if q: query=query.filter(or_(User.name.contains(q),Patient.nik.contains(q),Patient.mr.contains(q),User.phone.contains(q)))
    page=db.paginate(query.order_by(Patient.id.desc()).statement,page=request.args.get('page',1,type=int),per_page=12,error_out=False)
    return render_template('patients.html',page=page)


@web.get('/admin/patients/<int:pid>')
@roles(Role.ADMIN)
def patient_detail(pid):
    patient=db.get_or_404(Patient,pid)
    return render_template('patient_detail.html',patient=patient)


@web.route('/medicines',methods=['GET','POST'])
@roles(Role.ADMIN,Role.PHARMACIST)
def medicines():
    if request.method=='POST':
        def save():
            mid=request.form.get('id',type=int)
            med=db.get_or_404(Medicine,mid) if mid else Medicine(_stock=0)
            med.name=required(request.form,'name',160)
            med.category=required(request.form,'category',80); med.unit=required(request.form,'unit',32)
            med.price=number(request.form,'price',0,100000000,True)
            med.minimum=number(request.form,'minimum',0,1000000,True)
            med.expiry=date.fromisoformat(request.form['expiry']) if request.form.get('expiry') else None
            db.session.add(med); db.session.flush()
            delta=number(request.form,'delta',-1000000,1000000,True)
            if delta>0 and current_user.role==Role.PHARMACIST:
                raise ValueError('Restok masuk harus diajukan melalui pembelian supplier dan disetujui admin.')
            if delta: med.change_stock(delta,required(request.form,'reason',200),current_user.id)
        return mutate(save,url_for('web.medicines'))
    return render_template('medicines.html',medicines=Medicine.query.order_by(Medicine.name).all(),movements=StockMovement.query.order_by(StockMovement.id.desc()).limit(40).all(),today=date.today())


@web.route('/supplier-purchases',methods=['GET','POST'])
@login_required
def supplier_purchases():
    role=current_user.role
    if role not in (Role.ADMIN,Role.PHARMACIST): abort(403)
    if request.method=='POST':
        if role!=Role.PHARMACIST: abort(403)
        def create_request():
            medicine=db.get_or_404(Medicine,request.form.get('medicine_id',type=int))
            purchase=SupplierPurchase(supplier=required(request.form,'supplier',160),medicine=medicine,
                pharmacist_id=current_user.id,requested_quantity=number(request.form,'quantity',1,1000000,True),
                estimated_unit_cost=number(request.form,'estimated_unit_cost',1,100000000,True),
                reason=required(request.form,'reason',400))
            db.session.add(purchase)
        return mutate(create_request,url_for('web.supplier_purchases'))
    query=SupplierPurchase.query.order_by(SupplierPurchase.created_at.desc(),SupplierPurchase.id.desc())
    if role==Role.PHARMACIST: query=query.filter_by(pharmacist_id=current_user.id)
    return render_template('supplier_purchases.html',purchases=query.all(),medicines=Medicine.query.order_by(Medicine.name).all())


@web.post('/supplier-purchases/<int:purchase_id>/<action>')
@login_required
def supplier_purchase_action(purchase_id,action):
    purchase=db.get_or_404(SupplierPurchase,purchase_id)
    def update_purchase():
        role=current_user.role
        if action in ('approve_purchase','reject_purchase'):
            if role!=Role.ADMIN: abort(403)
        else:
            abort(404)

        if action=='approve_purchase':
            if purchase.status!=SupplierPurchaseStatus.PENDING_PURCHASE_APPROVAL: raise ValueError('Pengajuan pembelian tidak sedang menunggu keputusan.')
            received_at=datetime.now()
            if not (purchase.supplier_invoice or '').strip():
                purchase.supplier_invoice=generate_supplier_invoice_number(received_at)
            quantity=purchase.requested_quantity
            amount=purchase.requested_total
            movement_reason=f'Pembelian supplier {purchase.supplier}; pengajuan #{purchase.id}'[:200]
            purchase.medicine.change_stock(quantity,movement_reason,current_user.id)
            purchase.received_quantity=quantity
            purchase.actual_unit_cost=purchase.estimated_unit_cost
            purchase.received_at=received_at
            purchase.status=SupplierPurchaseStatus.PURCHASE_COMPLETED
            expense=purchase.expense_invoice
            if expense is None:
                expense=ExpenseInvoice(purchase=purchase,
                    number=f'EXP-{received_at:%Y%m%d}-{purchase.id:05}',
                    supplier=purchase.supplier,amount=amount,created_at=received_at)
                db.session.add(expense)
            else:
                expense.supplier=purchase.supplier; expense.amount=amount
            purchase.purchase_decided_by=current_user.id; purchase.purchase_decided_at=datetime.now()
            purchase.purchase_decision_note=request.form.get('note','')[:400]
        elif action=='reject_purchase':
            if purchase.status!=SupplierPurchaseStatus.PENDING_PURCHASE_APPROVAL: raise ValueError('Pengajuan pembelian tidak sedang menunggu keputusan.')
            purchase.status=SupplierPurchaseStatus.PURCHASE_REJECTED
            purchase.purchase_decided_by=current_user.id; purchase.purchase_decided_at=datetime.now()
            purchase.purchase_decision_note=required(request.form,'note',400)
    return mutate(update_purchase,url_for('web.supplier_purchases'))


@web.route('/admin/doctors',methods=['GET','POST'])
@roles(Role.ADMIN)
def doctors():
    if request.method=='POST':
        def save():
            did=request.form.get('id',type=int)
            if did:
                doctor=db.get_or_404(Doctor,did)
            else:
                sequence=User.query.filter_by(role=Role.DOCTOR).count()+1
                doctor=Doctor(user=User(role=Role.DOCTOR,
                    sip=f'445/{sequence:03d}/DINKES-SMD/2026'))
            doctor.user.name=required(request.form,'name',160)
            doctor.user.email=required(request.form,'email',160).lower()
            if '@' not in doctor.user.email: raise ValueError('Email tidak valid.')
            doctor.user.phone=request.form.get('phone','')[:24]
            if not did or request.form.get('password'): doctor.user.set_password(required(request.form,'password',128))
            doctor.user.active=bool(request.form.get('active'))
            doctor.specialty=required(request.form,'specialty',160)
            doctor.fee=number(request.form,'fee',0,100000000,True)
            db.session.add(doctor)
        return mutate(save,url_for('web.doctors'))
    return render_template('doctors.html',doctors=Doctor.query.all())


@web.post('/admin/schedules')
@roles(Role.ADMIN)
def schedule():
    def save():
        doctor=db.get_or_404(Doctor,request.form.get('doctor_id',type=int))
        weekday=number(request.form,'weekday',0,6,True)
        s=DoctorSchedule.query.filter_by(doctor_id=doctor.id,weekday=weekday).first()
        if request.form.get('remove'):
            if s: db.session.delete(s)
            return
        s=s or DoctorSchedule(doctor=doctor,weekday=weekday)
        try:
            start=datetime.strptime(request.form.get('start',''),'%H:%M')
            end=datetime.strptime(request.form.get('end',''),'%H:%M')
        except ValueError: raise ValueError('Jam praktik tidak valid.')
        if start>=end: raise ValueError('Jam akhir harus sesudah jam mulai.')
        s.start=start.strftime('%H:%M'); s.end=end.strftime('%H:%M')
        s.interval=number(request.form,'interval',5,180,True); s.quota=number(request.form,'quota',1,100,True)
        db.session.add(s)
    return mutate(save,url_for('web.doctors'))


@web.route('/admin/users',methods=['GET','POST'])
@roles(Role.ADMIN)
def users():
    if request.method=='POST':
        def save():
            uid=request.form.get('id',type=int)
            if uid:
                user=db.get_or_404(User,uid)
                if user.id==current_user.id: raise ValueError('Akun Anda sendiri tidak dapat dinonaktifkan di sini.')
                user.active=bool(request.form.get('active'))
                if request.form.get('password'): user.set_password(request.form['password'])
            else:
                role=request.form.get('role')
                if role not in ('admin','nurse','pharmacist','cashier'): raise ValueError('Gunakan menu Dokter/Pasien untuk peran tersebut.')
                user=User(email=required(request.form,'email',160).lower(),name=required(request.form,'name',160),role=Role(role))
                if '@' not in user.email: raise ValueError('Email tidak valid.')
                user.set_password(required(request.form,'password',128)); db.session.add(user)
        return mutate(save,url_for('web.users'))
    return render_template('users.html',users=User.query.order_by(User.id).all())


@web.get('/admin/reports')
@roles(Role.ADMIN)
def reports():
    today=date.today()
    try:
        start=date.fromisoformat(request.args.get('start') or today.replace(day=1).isoformat())
        end=date.fromisoformat(request.args.get('end') or today.isoformat())
    except ValueError: abort(400)
    if start>end: abort(400)
    payments=Payment.query.filter(Payment.created_at>=datetime.combine(start,datetime.min.time()),
        Payment.created_at<datetime.combine(end+timedelta(days=1),datetime.min.time())).order_by(Payment.created_at.desc()).all()
    expenses=ExpenseInvoice.query.filter(ExpenseInvoice.created_at>=datetime.combine(start,datetime.min.time()),
        ExpenseInvoice.created_at<datetime.combine(end+timedelta(days=1),datetime.min.time())).order_by(ExpenseInvoice.created_at.desc()).all()
    visits=Visit.query.join(Appointment).filter(Appointment.date.between(start,end)).all()
    transactions=[dict(category='Pendapatan',invoice=p.invoice.number,date=p.created_at,party=p.invoice.visit.patient.user.name,
        method=p.method,amount=p.amount,visit_id=p.invoice.visit_id,expense_id=None) for p in payments]
    transactions.extend(dict(category='Pengeluaran',invoice=e.number,date=e.created_at,party=e.supplier,
        method='Pembelian supplier',amount=e.amount,visit_id=None,expense_id=e.id) for e in expenses)
    transactions.sort(key=lambda item:item['date'],reverse=True)
    daily_chart=(end-start).days<=45
    chart_buckets={}
    cursor=start
    while cursor<=end:
        key=cursor.isoformat() if daily_chart else cursor.strftime('%Y-%m')
        label=cursor.strftime('%d/%m') if daily_chart else cursor.strftime('%m/%Y')
        chart_buckets[key]={'label':label,'income':0,'expense':0}
        if daily_chart:
            cursor+=timedelta(days=1)
        else:
            cursor=(cursor.replace(day=28)+timedelta(days=4)).replace(day=1)
    for payment in payments:
        key=payment.created_at.date().isoformat() if daily_chart else payment.created_at.strftime('%Y-%m')
        if key in chart_buckets: chart_buckets[key]['income']+=payment.amount
    for expense in expenses:
        key=expense.created_at.date().isoformat() if daily_chart else expense.created_at.strftime('%Y-%m')
        if key in chart_buckets: chart_buckets[key]['expense']+=expense.amount
    chart_points=list(chart_buckets.values())
    totals={category:sum(i.quantity*i.price for p in payments for i in p.invoice.items if i.category==category) for category in ('consultation','medicine','treatment')}
    if request.args.get('export')=='csv':
        stream=io.StringIO(); writer=csv.writer(stream)
        writer.writerow(['Kategori','Invoice','Tanggal','Pihak','Metode','Jumlah','Diskon','BPJS'])
        for p in payments: writer.writerow(['Pendapatan',p.invoice.number,p.created_at,p.invoice.visit.patient.user.name,p.method,p.amount,p.invoice.discount,p.invoice.coverage])
        for expense in expenses: writer.writerow(['Pengeluaran',expense.number,expense.created_at,expense.supplier,'Pembelian supplier',expense.amount,0,0])
        return Response('\ufeff'+stream.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=laporan.csv'})
    return render_template('reports.html',payments=payments,transactions=transactions,chart_points=chart_points,
        chart_interval='harian' if daily_chart else 'bulanan',visits=visits,totals=totals,start=start,end=end,
        expenses=expenses,revenue=sum(p.amount for p in payments),coverage=sum(p.invoice.coverage for p in payments),
        expense_total=sum(item.amount for item in expenses),
        net_income=sum(p.amount for p in payments)-sum(item.amount for item in expenses))


@web.get('/api/admin/finance')
@roles(Role.ADMIN)
def finance_api():
    today=date.today()
    try:
        start=date.fromisoformat(request.args.get('start') or today.replace(day=1).isoformat())
        end=date.fromisoformat(request.args.get('end') or today.isoformat())
    except ValueError: abort(400)
    if start>end: abort(400)
    lower=datetime.combine(start,datetime.min.time()); upper=datetime.combine(end+timedelta(days=1),datetime.min.time())
    payments=Payment.query.filter(Payment.created_at>=lower,Payment.created_at<upper).all()
    expenses=ExpenseInvoice.query.filter(ExpenseInvoice.created_at>=lower,ExpenseInvoice.created_at<upper).all()
    transactions=[dict(category='Pendapatan',invoice=p.invoice.number,date=p.created_at.isoformat(),
        party=p.invoice.visit.patient.user.name,amount=p.amount,method=p.method) for p in payments]
    transactions.extend(dict(category='Pengeluaran',invoice=e.number,date=e.created_at.isoformat(),
        party=e.supplier,amount=e.amount,method='Pembelian supplier') for e in expenses)
    transactions.sort(key=lambda item:item['date'],reverse=True)
    revenue=sum(p.amount for p in payments); expense_total=sum(e.amount for e in expenses)
    return jsonify(transactions=transactions,revenue=revenue,
        expenses=expense_total,net_income=revenue-expense_total)
