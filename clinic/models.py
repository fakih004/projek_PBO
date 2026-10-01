from datetime import datetime
from enum import Enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


class Role(str, Enum):
    PATIENT='patient'
    ADMIN='admin'
    NURSE='nurse'
    DOCTOR='doctor'
    PHARMACIST='pharmacist'


class VisitStatus(str, Enum):
    WAITING_VERIFICATION='WAITING_VERIFICATION'
    WAITING_NURSE='WAITING_NURSE'
    WAITING_DOCTOR='WAITING_DOCTOR'
    WITH_DOCTOR='WITH_DOCTOR'
    WAITING_PHARMACY='WAITING_PHARMACY'
    PHARMACY_PROCESSING='PHARMACY_PROCESSING'
    MEDICINE_READY='MEDICINE_READY'
    WAITING_PAYMENT='WAITING_PAYMENT'
    COMPLETED='COMPLETED'
    CANCELLED='CANCELLED'


class AppointmentStatus(str, Enum):
    PENDING='PENDING'
    VERIFIED='VERIFIED'
    REJECTED='REJECTED'
    RESCHEDULED='RESCHEDULED'
    CANCELLED='CANCELLED'
    CHECKED_IN='CHECKED_IN'
    COMPLETED='COMPLETED'


class PaymentStatus(str, Enum):
    UNPAID='UNPAID'
    WAITING_VERIFICATION='WAITING_VERIFICATION'
    PAID='PAID'
    BPJS_COVERED='BPJS_COVERED'
    FAILED='FAILED'
    CANCELLED='CANCELLED'


class PrescriptionStatus(str, Enum):
    NEW='NEW'
    PROCESSING='PROCESSING'
    READY='READY'
    DISPENSED='DISPENSED'
    OUT_OF_STOCK='OUT_OF_STOCK'


class User(UserMixin, db.Model):
    id=db.Column(db.Integer, primary_key=True)
    email=db.Column(db.String(160), unique=True, nullable=False)
    name=db.Column(db.String(160), nullable=False)
    _password_hash=db.Column('password_hash', db.String(256), nullable=False)
    role=db.Column(db.Enum(Role), nullable=False)
    active=db.Column(db.Boolean, default=True, nullable=False)
    phone=db.Column(db.String(24), default='')
    created_at=db.Column(db.DateTime, default=datetime.now)
    patient=db.relationship('Patient', backref='user', uselist=False)
    doctor=db.relationship('Doctor', backref='user', uselist=False)

    def set_password(self, password):
        if len(password) < 8:
            raise ValueError('Password minimal 8 karakter.')
        self._password_hash=generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self._password_hash, password)


class Patient(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.ForeignKey('user.id'), unique=True, nullable=False)
    mr=db.Column(db.String(32), unique=True)
    nik=db.Column(db.String(16), unique=True, nullable=False)
    birth_date=db.Column(db.Date, nullable=False)
    gender=db.Column(db.String(16), nullable=False)
    address=db.Column(db.Text, nullable=False)
    bpjs=db.Column(db.String(13), default='')
    bpjs_active=db.Column(db.Boolean, default=False)
    allergies=db.Column(db.Text, default='')
    history=db.Column(db.Text, default='')
    surgery=db.Column(db.Text, default='')
    medication=db.Column(db.Text, default='')
    emergency=db.Column(db.String(200), default='')


class Doctor(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.ForeignKey('user.id'), unique=True, nullable=False)
    specialty=db.Column(db.String(160), nullable=False)
    fee=db.Column(db.Integer, default=75000, nullable=False)
    schedules=db.relationship('DoctorSchedule', backref='doctor')


class DoctorSchedule(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    doctor_id=db.Column(db.ForeignKey('doctor.id'), nullable=False)
    weekday=db.Column(db.Integer, nullable=False)
    start=db.Column(db.String(5), nullable=False)
    end=db.Column(db.String(5), nullable=False)
    interval=db.Column(db.Integer, default=30, nullable=False)
    quota=db.Column(db.Integer, default=12, nullable=False)
    __table_args__=(db.UniqueConstraint('doctor_id','weekday'),)


class Appointment(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    patient_id=db.Column(db.ForeignKey('patient.id'), nullable=False)
    doctor_id=db.Column(db.ForeignKey('doctor.id'), nullable=False)
    date=db.Column(db.Date, nullable=False)
    time=db.Column(db.String(5), nullable=False)
    complaint=db.Column(db.Text, nullable=False)
    notes=db.Column(db.Text, default='')
    insurance=db.Column(db.Boolean, default=False)
    status=db.Column(db.Enum(AppointmentStatus), default=AppointmentStatus.PENDING, nullable=False)
    # Released on cancellation; NULL permits multiple historical bookings of a slot.
    slot_key=db.Column(db.String(80), unique=True)
    created_at=db.Column(db.DateTime, default=datetime.now)
    patient=db.relationship(Patient, backref='appointments')
    doctor=db.relationship(Doctor)
    visit=db.relationship('Visit', backref='appointment', uselist=False)


class QueueCounter(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    doctor_id=db.Column(db.ForeignKey('doctor.id'), nullable=False)
    date=db.Column(db.Date, nullable=False)
    value=db.Column(db.Integer, default=0, nullable=False)
    __table_args__=(db.UniqueConstraint('doctor_id','date'),)


class Visit(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    appointment_id=db.Column(db.ForeignKey('appointment.id'), unique=True, nullable=False)
    queue=db.Column(db.String(24), nullable=False)
    status=db.Column(db.Enum(VisitStatus), default=VisitStatus.WAITING_NURSE, nullable=False)
    queue_state=db.Column(db.String(24), default='WAITING')
    updated_at=db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    nursing=db.relationship('NursingAssessment', backref='visit', uselist=False)
    examination=db.relationship('DoctorExamination', backref='visit', uselist=False)
    prescription=db.relationship('Prescription', backref='visit', uselist=False)
    invoice=db.relationship('Invoice', backref='visit', uselist=False)
    referral=db.relationship('Referral', backref='visit', uselist=False)
    @property
    def patient(self): return self.appointment.patient
    @property
    def doctor(self): return self.appointment.doctor


class NursingAssessment(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    visit_id=db.Column(db.ForeignKey('visit.id'), unique=True, nullable=False)
    nurse_id=db.Column(db.ForeignKey('user.id'), nullable=False)
    systolic=db.Column(db.Integer, nullable=False)
    diastolic=db.Column(db.Integer, nullable=False)
    temperature=db.Column(db.Float, nullable=False)
    weight=db.Column(db.Float, nullable=False)
    height=db.Column(db.Float, nullable=False)
    pulse=db.Column(db.Integer, nullable=False)
    respiration=db.Column(db.Integer, nullable=False)
    spo2=db.Column(db.Integer, nullable=False)
    pain=db.Column(db.Integer, nullable=False)
    complaint=db.Column(db.Text, nullable=False)
    notes=db.Column(db.Text, default='')
    @property
    def bmi(self): return round(self.weight / (self.height/100)**2, 1)


class DoctorExamination(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    visit_id=db.Column(db.ForeignKey('visit.id'), unique=True, nullable=False)
    anamnesis=db.Column(db.Text, nullable=False)
    physical=db.Column(db.Text, nullable=False)
    assessment=db.Column(db.Text, default='')
    diagnosis=db.Column(db.Text, nullable=False)
    secondary=db.Column(db.Text, default='')
    icd10=db.Column(db.String(40), default='')
    treatment=db.Column(db.Text, default='')
    treatment_fee=db.Column(db.Integer, default=0)
    notes=db.Column(db.Text, default='')
    recommendation=db.Column(db.Text, default='')
    followup=db.Column(db.Text, default='')
    laboratory=db.Column(db.Text, default='')


class Medicine(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(160), unique=True, nullable=False)
    category=db.Column(db.String(80), default='Umum')
    unit=db.Column(db.String(32), default='tablet')
    _stock=db.Column('stock', db.Integer, default=0, nullable=False)
    price=db.Column(db.Integer, nullable=False)
    minimum=db.Column(db.Integer, default=20, nullable=False)
    expiry=db.Column(db.Date)
    __table_args__=(db.CheckConstraint('stock >= 0'),db.CheckConstraint('price >= 0'))
    @property
    def stock(self): return self._stock
    def change_stock(self, delta, reason, actor_id, visit_id=None):
        from sqlalchemy import update
        if not delta or not reason.strip():
            raise ValueError('Jumlah perubahan dan alasan stok wajib diisi.')
        result=db.session.execute(update(Medicine).where(Medicine.id==self.id, Medicine._stock+delta>=0)
                                  .values(_stock=Medicine._stock+delta).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise ValueError(f'Stok {self.name} tidak cukup.')
        db.session.add(StockMovement(medicine_id=self.id, quantity=delta, reason=reason, actor_id=actor_id, visit_id=visit_id))
        db.session.expire(self, ['_stock'])


class StockMovement(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    medicine_id=db.Column(db.ForeignKey('medicine.id'), nullable=False)
    quantity=db.Column(db.Integer, nullable=False)
    reason=db.Column(db.String(200), nullable=False)
    actor_id=db.Column(db.ForeignKey('user.id'), nullable=False)
    visit_id=db.Column(db.ForeignKey('visit.id'))
    created_at=db.Column(db.DateTime, default=datetime.now)
    medicine=db.relationship(Medicine)


class Prescription(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    visit_id=db.Column(db.ForeignKey('visit.id'), unique=True, nullable=False)
    status=db.Column(db.Enum(PrescriptionStatus), default=PrescriptionStatus.NEW, nullable=False)
    notes=db.Column(db.Text, default='')
    items=db.relationship('PrescriptionItem', backref='prescription', cascade='all, delete-orphan')


class PrescriptionItem(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    prescription_id=db.Column(db.ForeignKey('prescription.id'), nullable=False)
    medicine_id=db.Column(db.ForeignKey('medicine.id'), nullable=False)
    quantity=db.Column(db.Integer, nullable=False)
    price=db.Column(db.Integer, nullable=False)
    dosage=db.Column(db.String(80), nullable=False)
    frequency=db.Column(db.String(80), nullable=False)
    duration=db.Column(db.String(80), nullable=False)
    timing=db.Column(db.String(80), nullable=False)
    instruction=db.Column(db.String(300), default='')
    medicine=db.relationship(Medicine)
    __table_args__=(db.CheckConstraint('quantity > 0'),)


class Invoice(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    visit_id=db.Column(db.ForeignKey('visit.id'), unique=True, nullable=False)
    number=db.Column(db.String(40), unique=True, nullable=False)
    subtotal=db.Column(db.Integer, nullable=False)
    discount=db.Column(db.Integer, default=0, nullable=False)
    coverage=db.Column(db.Integer, default=0, nullable=False)
    payable=db.Column(db.Integer, nullable=False)
    status=db.Column(db.Enum(PaymentStatus), default=PaymentStatus.UNPAID, nullable=False)
    items=db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan')
    payment=db.relationship('Payment', backref='invoice', uselist=False)


class InvoiceItem(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    invoice_id=db.Column(db.ForeignKey('invoice.id'), nullable=False)
    description=db.Column(db.String(200), nullable=False)
    category=db.Column(db.String(24), nullable=False)
    quantity=db.Column(db.Integer, nullable=False)
    price=db.Column(db.Integer, nullable=False)


class Payment(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    invoice_id=db.Column(db.ForeignKey('invoice.id'), unique=True, nullable=False)
    admin_id=db.Column(db.ForeignKey('user.id'), nullable=False)
    amount=db.Column(db.Integer, nullable=False)
    method=db.Column(db.String(24), nullable=False)
    status=db.Column(db.Enum(PaymentStatus), nullable=False)
    created_at=db.Column(db.DateTime, default=datetime.now)


class Notification(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.ForeignKey('user.id'), nullable=False, index=True)
    message=db.Column(db.String(400), nullable=False)
    read=db.Column(db.Boolean, default=False, nullable=False)
    unique_key=db.Column(db.String(100), unique=True)
    created_at=db.Column(db.DateTime, default=datetime.now)


class Referral(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    visit_id=db.Column(db.ForeignKey('visit.id'), unique=True, nullable=False)
    number=db.Column(db.String(40), unique=True, nullable=False)
    hospital=db.Column(db.String(160), nullable=False)
    specialist=db.Column(db.String(160), nullable=False)
    reason=db.Column(db.Text, nullable=False)
    notes=db.Column(db.Text, default='')
    created_at=db.Column(db.DateTime, default=datetime.now)
    clinical=db.relationship('ReferralClinical', backref='referral', uselist=False, cascade='all, delete-orphan')


class ReferralClinical(db.Model):
    """Additive extension: old referral rows and all original columns remain intact."""
    id=db.Column(db.Integer, primary_key=True)
    referral_id=db.Column(db.ForeignKey('referral.id'), unique=True, nullable=False)
    diagnosis=db.Column(db.Text, nullable=False)
    examination=db.Column(db.Text, nullable=False)
    treatments=db.Column(db.Text, nullable=False)
    medicines=db.Column(db.Text, nullable=False)
    condition=db.Column(db.Text, nullable=False)
    referral_date=db.Column(db.Date, nullable=False)
    updated_at=db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    version=db.Column(db.Integer, nullable=False, default=1)


class PartnerHospital(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(160), unique=True, nullable=False)
    departments=db.Column(db.String(300), default='')
    address=db.Column(db.String(300), default='')
    phone=db.Column(db.String(24), default='')
    active=db.Column(db.Boolean, default=True, nullable=False)


class ClinicSettings(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    bank=db.Column(db.String(80), nullable=False, default='BCA')
    account_number=db.Column(db.String(40), nullable=False, default='1234567890')
    account_name=db.Column(db.String(160), nullable=False, default='Klinik Medika Husada')
    bank_demo=db.Column(db.Boolean, nullable=False, default=True)


class PaymentRequest(db.Model):
    """Patient declarations, separate from settled Payment so revenue stays accurate."""
    id=db.Column(db.Integer, primary_key=True)
    invoice_id=db.Column(db.ForeignKey('invoice.id'), nullable=False, index=True)
    method=db.Column(db.String(24), nullable=False)
    amount=db.Column(db.Integer, nullable=False)
    status=db.Column(db.Enum(PaymentStatus), nullable=False, default=PaymentStatus.WAITING_VERIFICATION)
    # One active request per invoice; rejected attempts remain as history.
    active_key=db.Column(db.Integer, unique=True)
    submitted_at=db.Column(db.DateTime, nullable=False, default=datetime.now)
    reviewed_at=db.Column(db.DateTime)
    reviewed_by=db.Column(db.ForeignKey('user.id'))
    invoice=db.relationship(Invoice, backref='requests')
