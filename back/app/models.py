from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .security import hash_password, verify_password


class Role(str, Enum):
    PATIENT = "patient"
    ADMIN = "admin"
    NURSE = "nurse"
    DOCTOR = "doctor"
    PHARMACIST = "pharmacist"


class VisitStatus(str, Enum):
    WAITING_VERIFICATION = "WAITING_VERIFICATION"
    WAITING_NURSE = "WAITING_NURSE"
    WAITING_DOCTOR = "WAITING_DOCTOR"
    WITH_DOCTOR = "WITH_DOCTOR"
    WAITING_PHARMACY = "WAITING_PHARMACY"
    PHARMACY_PROCESSING = "PHARMACY_PROCESSING"
    MEDICINE_READY = "MEDICINE_READY"
    WAITING_PAYMENT = "WAITING_PAYMENT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AppointmentStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    CHECKED_IN = "CHECKED_IN"
    COMPLETED = "COMPLETED"


class PaymentStatus(str, Enum):
    UNPAID = "UNPAID"
    PAID = "PAID"
    BPJS_COVERED = "BPJS_COVERED"


class PrescriptionStatus(str, Enum):
    NEW = "NEW"
    PROCESSING = "PROCESSING"
    READY = "READY"
    DISPENSED = "DISPENSED"
    OUT_OF_STOCK = "OUT_OF_STOCK"


def enum_column(enum_type, name: str):
    return SQLEnum(enum_type, name=name, native_enum=False, length=40)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[Role] = mapped_column(enum_column(Role, "role"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(24), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    patient: Mapped[Patient | None] = relationship(back_populates="user", uselist=False)
    doctor: Mapped[Doctor | None] = relationship(back_populates="user", uselist=False)

    def set_password(self, password: str) -> None:
        self.password_hash = hash_password(password)

    def check_password(self, password: str) -> bool:
        return verify_password(password, self.password_hash)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    mr: Mapped[str | None] = mapped_column(String(32), unique=True)
    nik: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    bpjs: Mapped[str] = mapped_column(String(13), default="", nullable=False)
    bpjs_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allergies: Mapped[str] = mapped_column(Text, default="", nullable=False)
    history: Mapped[str] = mapped_column(Text, default="", nullable=False)
    surgery: Mapped[str] = mapped_column(Text, default="", nullable=False)
    medication: Mapped[str] = mapped_column(Text, default="", nullable=False)
    emergency: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    user: Mapped[User] = relationship(back_populates="patient")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="patient")


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    specialty: Mapped[str] = mapped_column(String(160), nullable=False)
    fee: Mapped[int] = mapped_column(Integer, default=75_000, nullable=False)
    user: Mapped[User] = relationship(back_populates="doctor")
    schedules: Mapped[list[DoctorSchedule]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )


class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"
    __table_args__ = (UniqueConstraint("doctor_id", "weekday", name="uq_doctor_weekday"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start: Mapped[str] = mapped_column(String(5), nullable=False)
    end: Mapped[str] = mapped_column(String(5), nullable=False)
    interval: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    quota: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    doctor: Mapped[Doctor] = relationship(back_populates="schedules")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    complaint: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    insurance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        enum_column(AppointmentStatus, "appointment_status"),
        default=AppointmentStatus.PENDING,
        nullable=False,
    )
    slot_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    patient: Mapped[Patient] = relationship(back_populates="appointments")
    doctor: Mapped[Doctor] = relationship()
    visit: Mapped[Visit | None] = relationship(back_populates="appointment", uselist=False)


class QueueCounter(Base):
    __tablename__ = "queue_counters"
    __table_args__ = (UniqueConstraint("doctor_id", "date", name="uq_queue_doctor_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), unique=True, nullable=False)
    queue: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[VisitStatus] = mapped_column(
        enum_column(VisitStatus, "visit_status"), default=VisitStatus.WAITING_NURSE, nullable=False
    )
    queue_state: Mapped[str] = mapped_column(String(24), default="WAITING", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    appointment: Mapped[Appointment] = relationship(back_populates="visit")
    nursing: Mapped[NursingAssessment | None] = relationship(
        back_populates="visit", uselist=False, cascade="all, delete-orphan"
    )
    examination: Mapped[DoctorExamination | None] = relationship(
        back_populates="visit", uselist=False, cascade="all, delete-orphan"
    )
    prescription: Mapped[Prescription | None] = relationship(
        back_populates="visit", uselist=False, cascade="all, delete-orphan"
    )
    invoice: Mapped[Invoice | None] = relationship(
        back_populates="visit", uselist=False, cascade="all, delete-orphan"
    )
    referral: Mapped[Referral | None] = relationship(
        back_populates="visit", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def patient(self) -> Patient:
        return self.appointment.patient

    @property
    def doctor(self) -> Doctor:
        return self.appointment.doctor


class NursingAssessment(Base):
    __tablename__ = "nursing_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), unique=True, nullable=False)
    nurse_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    systolic: Mapped[int] = mapped_column(Integer, nullable=False)
    diastolic: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    pulse: Mapped[int] = mapped_column(Integer, nullable=False)
    respiration: Mapped[int] = mapped_column(Integer, nullable=False)
    spo2: Mapped[int] = mapped_column(Integer, nullable=False)
    pain: Mapped[int] = mapped_column(Integer, nullable=False)
    complaint: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    visit: Mapped[Visit] = relationship(back_populates="nursing")


class DoctorExamination(Base):
    __tablename__ = "doctor_examinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), unique=True, nullable=False)
    anamnesis: Mapped[str] = mapped_column(Text, nullable=False)
    physical: Mapped[str] = mapped_column(Text, nullable=False)
    assessment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    diagnosis: Mapped[str] = mapped_column(Text, nullable=False)
    secondary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    icd10: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    treatment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    treatment_fee: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    followup: Mapped[str] = mapped_column(Text, default="", nullable=False)
    laboratory: Mapped[str] = mapped_column(Text, default="", nullable=False)
    visit: Mapped[Visit] = relationship(back_populates="examination")


class Medicine(Base):
    __tablename__ = "medicines"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_medicine_stock"),
        CheckConstraint("price >= 0", name="ck_medicine_price"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="Umum", nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="tablet", nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    expiry: Mapped[date | None] = mapped_column(Date)


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    visit_id: Mapped[int | None] = mapped_column(ForeignKey("visits.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    medicine: Mapped[Medicine] = relationship()


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), unique=True, nullable=False)
    status: Mapped[PrescriptionStatus] = mapped_column(
        enum_column(PrescriptionStatus, "prescription_status"),
        default=PrescriptionStatus.NEW,
        nullable=False,
    )
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    visit: Mapped[Visit] = relationship(back_populates="prescription")
    items: Mapped[list[PrescriptionItem]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan"
    )


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_prescription_quantity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"), nullable=False)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    dosage: Mapped[str] = mapped_column(String(80), nullable=False)
    frequency: Mapped[str] = mapped_column(String(80), nullable=False)
    duration: Mapped[str] = mapped_column(String(80), nullable=False)
    timing: Mapped[str] = mapped_column(String(80), nullable=False)
    instruction: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    prescription: Mapped[Prescription] = relationship(back_populates="items")
    medicine: Mapped[Medicine] = relationship()


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), unique=True, nullable=False)
    number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coverage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payable: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        enum_column(PaymentStatus, "payment_status"), default=PaymentStatus.UNPAID, nullable=False
    )
    visit: Mapped[Visit] = relationship(back_populates="invoice")
    items: Mapped[list[InvoiceItem]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    payment: Mapped[Payment | None] = relationship(
        back_populates="invoice", uselist=False, cascade="all, delete-orphan"
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    invoice: Mapped[Invoice] = relationship(back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), unique=True, nullable=False)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(enum_column(PaymentStatus, "payment_record_status"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    invoice: Mapped[Invoice] = relationship(back_populates="payment")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notification_user_read", "user_id", "read"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    message: Mapped[str] = mapped_column(String(400), nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unique_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id"), unique=True, nullable=False)
    number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    hospital: Mapped[str] = mapped_column(String(160), nullable=False)
    specialist: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    visit: Mapped[Visit] = relationship(back_populates="referral")

