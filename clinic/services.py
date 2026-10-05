"""Transactional domain services. Routes commit once; any failure rolls everything back."""
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
import math
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
from . import db
from .models import *

LABELS={
    'WAITING_VERIFICATION':'Menunggu verifikasi ulang',
    'PENDING':'Menunggu verifikasi', 'RESCHEDULED':'Jadwal diubah · menunggu verifikasi',
    'VERIFIED':'Terverifikasi', 'CHECKED_IN':'Sudah hadir', 'CANCELLED':'Dibatalkan', 'REJECTED':'Ditolak',
    'WAITING_NURSE':'Menunggu pemeriksaan perawat', 'WAITING_DOCTOR':'Menunggu dokter',
    'WITH_DOCTOR':'Pemeriksaan dokter', 'WAITING_PHARMACY':'Resep diterima apotek',
    'PHARMACY_PROCESSING':'Obat sedang disiapkan', 'MEDICINE_READY':'Obat siap diambil',
    'WAITING_PAYMENT':'Silakan menuju bagian pembayaran', 'COMPLETED':'Pelayanan selesai. Semoga lekas sembuh.',
    'UNPAID':'Belum dibayar', 'PAID':'Lunas', 'BPJS_COVERED':'Ditanggung BPJS',
    'patient':'Pasien', 'admin':'Admin', 'nurse':'Perawat', 'doctor':'Dokter', 'pharmacist':'Apoteker',
}


def required(data, key, limit=4000):
    value=str(data.get(key, '')).strip()
    if not value or len(value)>limit:
        raise ValueError(f'{key.replace("_", " ").capitalize()} wajib diisi (maks. {limit} karakter).')
    return value


def number(data, key, minimum, maximum, integer=False):
    try:
        value=float(data.get(key, ''))
    except (ValueError, TypeError):
        raise ValueError(f'{key} harus berupa angka.')
    if not math.isfinite(value) or not minimum<=value<=maximum or (integer and not value.is_integer()):
        raise ValueError(f'{key} harus antara {minimum} dan {maximum}.')
    return int(value) if integer else value


class NotificationService:
    @staticmethod
    def send(patient, message):
        db.session.add(Notification(user_id=patient.user_id, message=message))

    @staticmethod
    def reminders(user):
        if user.role != Role.PATIENT: return
        now=datetime.now()
        for a in user.patient.appointments:
            if a.status not in (AppointmentStatus.PENDING, AppointmentStatus.RESCHEDULED, AppointmentStatus.VERIFIED): continue
            delta=datetime.combine(a.date, datetime.strptime(a.time,'%H:%M').time())-now
            window='3h' if timedelta(0)<delta<=timedelta(hours=3) else '24h' if timedelta(hours=3)<delta<=timedelta(days=1) else None
            if window:
                key=f'reminder:{a.id}:{a.date}:{a.time}:{window}'
                db.session.execute(insert(Notification).values(user_id=user.id, unique_key=key,
                    message=f'Pengingat: janji dengan {a.doctor.user.name}, {a.date} pukul {a.time}.', read=False,
                    created_at=now).on_conflict_do_nothing(index_elements=['unique_key']))


class AppointmentService:
    @staticmethod
    def claim_edit(a, target):
        """Conditional writes serialize edits with verification and the first assessment."""
        result=db.session.execute(update(Appointment).where(Appointment.id==a.id,
            Appointment.status.in_([AppointmentStatus.PENDING,AppointmentStatus.RESCHEDULED,AppointmentStatus.VERIFIED])).values(status=target))
        if result.rowcount!=1:
            raise ValueError('Janji sudah diperiksa, selesai, atau dibatalkan.')
        if a.visit:
            result=db.session.execute(update(Visit).where(Visit.id==a.visit.id,
                Visit.status.in_([VisitStatus.WAITING_NURSE,VisitStatus.WAITING_VERIFICATION])).values(
                    status=VisitStatus.CANCELLED if target in (AppointmentStatus.CANCELLED,AppointmentStatus.REJECTED) else VisitStatus.WAITING_VERIFICATION,
                    queue='—',queue_state='WAITING',updated_at=datetime.now()))
            if result.rowcount!=1: raise ValueError('Pemeriksaan sudah dimulai. Janji tidak dapat diubah.')

    @staticmethod
    def slots(doctor_id, day, exclude_id=None):
        doctor=db.session.get(Doctor, doctor_id)
        if not doctor or not doctor.user.active: return []
        s=DoctorSchedule.query.filter_by(doctor_id=doctor_id, weekday=day.weekday()).first()
        if not s: return []
        occupied={a.time for a in Appointment.query.filter_by(doctor_id=doctor_id,date=day).all()
                  if a.slot_key and a.id!=exclude_id}
        start=datetime.combine(day,datetime.strptime(s.start,'%H:%M').time())
        end=datetime.combine(day,datetime.strptime(s.end,'%H:%M').time())
        result=[]
        while start<end and len(result)<s.quota:
            time=start.strftime('%H:%M')
            result.append({'time':time,'available':time not in occupied and start>datetime.now()})
            start+=timedelta(minutes=s.interval)
        return result

    @staticmethod
    def book(patient, data, appointment=None):
        try:
            day=date.fromisoformat(data.get('date',''))
            doctor_id=int(data.get('doctor_id',''))
        except (ValueError, TypeError): raise ValueError('Pilih dokter dan tanggal yang valid.')
        if appointment:
            AppointmentService.claim_edit(appointment,AppointmentStatus.RESCHEDULED)
        if not any(s['time']==data.get('time') and s['available'] for s in AppointmentService.slots(doctor_id,day,appointment.id if appointment else None)):
            raise ValueError('Slot penuh, sudah lewat, atau di luar jadwal dokter.')
        insurance=data.get('insurance')=='bpjs'
        if insurance and (not patient.bpjs or not patient.bpjs_active):
            raise ValueError('Lengkapi nomor BPJS aktif pada profil terlebih dahulu.')
        a=appointment or Appointment(patient=patient)
        a.doctor_id=doctor_id
        a.date=day
        a.time=data['time']
        a.complaint=required(data,'complaint')
        a.notes=str(data.get('notes',''))[:4000]
        a.insurance=insurance
        a.slot_key=f'{doctor_id}:{day}:{a.time}'
        a.status=AppointmentStatus.RESCHEDULED if appointment else AppointmentStatus.PENDING
        db.session.add(a)
        NotificationService.send(patient,'Janji diperbarui dan menunggu verifikasi.' if appointment else 'Janji berhasil dibuat. Menunggu verifikasi admin.')
        return a

    @staticmethod
    def cancel(a, rejected=False):
        AppointmentService.claim_edit(a,AppointmentStatus.REJECTED if rejected else AppointmentStatus.CANCELLED)
        a.slot_key=None
        NotificationService.send(a.patient,'Janji ditolak oleh admin.' if rejected else 'Janji dibatalkan. Slot tersedia kembali.')

    @staticmethod
    def verify(a):
        result=db.session.execute(update(Appointment).where(Appointment.id==a.id,
            Appointment.status.in_([AppointmentStatus.PENDING,AppointmentStatus.RESCHEDULED])).values(status=AppointmentStatus.VERIFIED))
        if result.rowcount!=1: raise ValueError('Janji sudah diproses.')
        stmt=insert(QueueCounter).values(doctor_id=a.doctor_id,date=a.date,value=1)
        seq=db.session.execute(stmt.on_conflict_do_update(index_elements=['doctor_id','date'],
            set_={'value':QueueCounter.value+1}).returning(QueueCounter.value)).scalar_one()
        visit=a.visit or Visit(appointment=a)
        visit.queue=f'D{a.doctor_id}-{seq:03}'
        visit.status=VisitStatus.WAITING_NURSE
        db.session.add(visit)
        NotificationService.send(a.patient,f'Appointment terverifikasi. Antrean {visit.queue}. Menunggu pemeriksaan perawat.')
        return visit


class WorkflowService:
    @staticmethod
    def transition(v, expected, target):
        if v.appointment.date>date.today():
            raise ValueError('Pemeriksaan hanya dapat dilakukan pada hari kunjungan atau sesudahnya.')
        result=db.session.execute(update(Visit).where(Visit.id==v.id, Visit.status.in_(expected)).values(status=target,updated_at=datetime.now()))
        if result.rowcount!=1: raise ValueError('Status sudah berubah. Muat ulang halaman sebelum melanjutkan.')
        NotificationService.send(v.patient,LABELS[target.value])

    @staticmethod
    def nurse(v, actor, data):
        values={}
        ranges={'systolic':(40,300,True),'diastolic':(20,200,True),'temperature':(30,45,False),
                'weight':(1,500,False),'height':(30,250,False),'pulse':(20,250,True),
                'respiration':(1,100,True),'spo2':(1,100,True),'pain':(0,10,True)}
        for key,(lo,hi,integer) in ranges.items(): values[key]=number(data,key,lo,hi,integer)
        values['complaint']=required(data,'complaint')
        values['notes']=data.get('notes','')[:4000]
        WorkflowService.transition(v,[VisitStatus.WAITING_NURSE],VisitStatus.WAITING_DOCTOR)
        db.session.add(NursingAssessment(visit=v,nurse_id=actor.id,**values))
        v.appointment.status=AppointmentStatus.CHECKED_IN

    @staticmethod
    def examine(v, data, items):
        fields={key:required(data,key) for key in ('anamnesis','physical','diagnosis')}
        for key in ('assessment','secondary','icd10','treatment','notes','recommendation','followup','laboratory'):
            fields[key]=str(data.get(key,''))[:4000]
        fields['treatment_fee']=number(data,'treatment_fee',0,100000000,True)
        prescription=Prescription()
        seen=set()
        for item in items:
            medicine=db.session.get(Medicine,number(item,'medicine_id',1,1000000,True))
            if not medicine or medicine.id in seen: raise ValueError('Obat tidak valid atau duplikat. Gabungkan jumlahnya.')
            seen.add(medicine.id)
            prescription.items.append(PrescriptionItem(medicine=medicine, quantity=number(item,'quantity',1,10000,True),price=medicine.price,
                **{key:required(item,key,80) for key in ('dosage','frequency','duration','timing')},instruction=str(item.get('instruction',''))[:300]))
        WorkflowService.transition(v,[VisitStatus.WITH_DOCTOR],VisitStatus.WAITING_PHARMACY if items else VisitStatus.WAITING_PAYMENT)
        db.session.add(DoctorExamination(visit=v,**fields))
        if items:
            prescription.visit=v
            db.session.add(prescription)
        else:
            BillingService.invoice(v)


class PharmacyService:
    @staticmethod
    def process(v, action, actor):
        p=v.prescription
        if not p: raise ValueError('Resep tidak ditemukan.')
        if action=='start':
            WorkflowService.transition(v,[VisitStatus.WAITING_PHARMACY],VisitStatus.PHARMACY_PROCESSING)
            p.status=PrescriptionStatus.PROCESSING
        elif action=='shortage':
            if v.status not in (VisitStatus.WAITING_PHARMACY,VisitStatus.PHARMACY_PROCESSING): raise ValueError('Resep telah diproses.')
            p.status=PrescriptionStatus.OUT_OF_STOCK
            NotificationService.send(v.patient,'Apotek melaporkan stok tidak cukup; petugas sedang menindaklanjuti.')
            for u in User.query.filter(User.role.in_([Role.ADMIN,Role.DOCTOR])).all():
                if u.role==Role.ADMIN or u.id==v.doctor.user_id:
                    db.session.add(Notification(user_id=u.id,message=f'Stok tidak cukup untuk resep kunjungan #{v.id}.'))
        elif action=='ready':
            WorkflowService.transition(v,[VisitStatus.PHARMACY_PROCESSING],VisitStatus.MEDICINE_READY)
            for item in p.items:
                if item.medicine.expiry and item.medicine.expiry<date.today(): raise ValueError(f'{item.medicine.name} kedaluwarsa.')
                item.medicine.change_stock(-item.quantity,'Penyerahan resep',actor.id,v.id)
            p.status=PrescriptionStatus.READY
        elif action=='handover':
            WorkflowService.transition(v,[VisitStatus.MEDICINE_READY],VisitStatus.WAITING_PAYMENT)
            p.status=PrescriptionStatus.DISPENSED
            BillingService.invoice(v)
        else: raise ValueError('Aksi farmasi tidak dikenal.')


class PaymentProcessor(ABC):
    @abstractmethod
    def amounts(self, total):
        """Return (insurance coverage, patient payable)."""


class GeneralPayment(PaymentProcessor):
    def amounts(self,total): return 0,total


class BPJSPayment(PaymentProcessor):
    def amounts(self,total): return total,0


class BillingService:
    @staticmethod
    def invoice(v):
        if v.invoice: return v.invoice
        items=[InvoiceItem(description='Konsultasi dokter',category='consultation',quantity=1,price=v.doctor.fee)]
        if v.examination and v.examination.treatment_fee:
            items.append(InvoiceItem(description=v.examination.treatment or 'Tindakan',category='treatment',quantity=1,price=v.examination.treatment_fee))
        if v.prescription:
            items.extend(InvoiceItem(description=i.medicine.name,category='medicine',quantity=i.quantity,price=i.price) for i in v.prescription.items)
        total=sum(i.quantity*i.price for i in items)
        processor=BPJSPayment() if v.appointment.insurance else GeneralPayment()
        coverage,payable=processor.amounts(total)
        inv=Invoice(visit=v,number=f'INV-{v.appointment.date:%Y%m%d}-{v.id:05}',subtotal=total,coverage=coverage,payable=payable,items=items)
        db.session.add(inv)
        return inv

    @staticmethod
    def pay(v, actor, data):
        inv=v.invoice
        if not inv: raise ValueError('Invoice belum tersedia.')
        discount=number(data,'discount',0,inv.subtotal,True)
        method='BPJS' if v.appointment.insurance else required(data,'method',24)
        if method not in ('BPJS','Tunai','Transfer','QRIS','Debit'): raise ValueError('Metode pembayaran tidak valid.')
        if not v.appointment.insurance and method=='BPJS': raise ValueError('Kunjungan ini bukan BPJS.')
        status=PaymentStatus.BPJS_COVERED if v.appointment.insurance else PaymentStatus.PAID
        WorkflowService.transition(v,[VisitStatus.WAITING_PAYMENT],VisitStatus.COMPLETED)
        inv.discount=discount
        inv.coverage,inv.payable=(BPJSPayment() if v.appointment.insurance else GeneralPayment()).amounts(inv.subtotal-discount)
        inv.status=status
        db.session.add(Payment(invoice=inv,admin_id=actor.id,amount=inv.payable,method=method,status=status))
        v.appointment.status=AppointmentStatus.COMPLETED


class PatientService:
    @staticmethod
    def profile(patient, data):
        nik=required(data,'nik',16)
        if len(nik)!=16 or not nik.isdigit(): raise ValueError('NIK harus 16 digit.')
        try: birth=date.fromisoformat(data.get('birth_date',''))
        except ValueError: raise ValueError('Tanggal lahir tidak valid.')
        if birth>date.today() or birth.year<1900: raise ValueError('Tanggal lahir tidak valid.')
        gender=data.get('gender')
        if gender not in ('Laki-laki','Perempuan'): raise ValueError('Pilih jenis kelamin.')
        phone=required(data,'phone',24)
        if not phone.lstrip('+').isdigit() or not 8<=len(phone)<=16: raise ValueError('Nomor telepon tidak valid.')
        bpjs=str(data.get('bpjs','')).strip() if data.get('has_bpjs') else ''
        if data.get('has_bpjs') and (len(bpjs)!=13 or not bpjs.isdigit()): raise ValueError('Nomor BPJS harus 13 digit.')
        patient.nik=nik; patient.birth_date=birth; patient.gender=gender
        patient.address=required(data,'address')
        patient.bpjs=bpjs; patient.bpjs_active=bool(bpjs)
        patient.user.name=required(data,'name',160); patient.user.phone=phone
        for key in ('allergies','history','surgery','medication','emergency'):
            setattr(patient,key,str(data.get(key,''))[:4000])

    @staticmethod
    def register(data):
        email=required(data,'email',160).lower()
        if '@' not in email or '.' not in email.split('@')[-1]: raise ValueError('Email tidak valid.')
        if data.get('password')!=data.get('confirm'): raise ValueError('Konfirmasi password tidak cocok.')
        user=User(email=email,role=Role.PATIENT)
        user.set_password(required(data,'password',128))
        patient=Patient(user=user)
        PatientService.profile(patient,data)
        db.session.add(user); db.session.add(patient); db.session.flush()
        patient.mr=f'KMH-{date.today().year}-{patient.id:05}'
        return user
