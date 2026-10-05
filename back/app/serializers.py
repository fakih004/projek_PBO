from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import (
    Appointment,
    Doctor,
    Medicine,
    Notification,
    NursingAssessment,
    Patient,
    Role,
    StockMovement,
    User,
    Visit,
    VisitStatus,
)


def enum_value(value):
    return value.value if hasattr(value, "value") else value


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": enum_value(user.role),
        "active": user.active,
    }


def serialize_patient(patient: Patient) -> dict:
    return {
        "id": patient.id,
        "userId": patient.user_id,
        "mr": patient.mr,
        "nik": patient.nik,
        "birthDate": patient.birth_date.isoformat(),
        "gender": patient.gender,
        "address": patient.address,
        "bpjs": patient.bpjs,
        "bpjsActive": patient.bpjs_active,
        "allergies": patient.allergies,
        "history": patient.history,
        "surgery": patient.surgery,
        "medication": patient.medication,
        "emergency": patient.emergency,
    }


def serialize_doctor(doctor: Doctor) -> dict:
    return {
        "id": doctor.id,
        "userId": doctor.user_id,
        "specialty": doctor.specialty,
        "fee": doctor.fee,
        "avatar": f"assets/hospital/assets/images/xs/avatar{((doctor.id - 1) % 5) + 1}.jpg",
        "schedules": [
            {
                "id": item.id,
                "doctorId": item.doctor_id,
                "weekday": item.weekday,
                "start": item.start,
                "end": item.end,
                "interval": item.interval,
                "quota": item.quota,
            }
            for item in sorted(doctor.schedules, key=lambda value: value.weekday)
        ],
    }


def serialize_appointment(appointment: Appointment) -> dict:
    return {
        "id": appointment.id,
        "patientId": appointment.patient_id,
        "doctorId": appointment.doctor_id,
        "date": appointment.date.isoformat(),
        "time": appointment.time,
        "complaint": appointment.complaint,
        "notes": appointment.notes,
        "insurance": appointment.insurance,
        "status": enum_value(appointment.status),
        "visitId": appointment.visit.id if appointment.visit else None,
    }


def serialize_visit(visit: Visit, viewer: User) -> dict:
    nursing = None
    if visit.nursing:
        nursing = {
            key: getattr(visit.nursing, key)
            for key in (
                "systolic",
                "diastolic",
                "temperature",
                "weight",
                "height",
                "pulse",
                "respiration",
                "spo2",
                "pain",
                "complaint",
                "notes",
            )
        }
    examination = None
    if visit.examination:
        examination = {
            "anamnesis": visit.examination.anamnesis,
            "physical": visit.examination.physical,
            "assessment": visit.examination.assessment,
            "diagnosis": visit.examination.diagnosis,
            "secondary": visit.examination.secondary,
            "icd10": visit.examination.icd10,
            "treatment": visit.examination.treatment,
            "treatmentFee": visit.examination.treatment_fee,
            "notes": visit.examination.notes if viewer.role == Role.DOCTOR else "",
            "recommendation": visit.examination.recommendation,
            "followup": visit.examination.followup,
            "laboratory": visit.examination.laboratory,
        }
    prescription = None
    if visit.prescription:
        prescription = {
            "status": enum_value(visit.prescription.status),
            "items": [
                {
                    "medicineId": item.medicine_id,
                    "quantity": item.quantity,
                    "price": item.price,
                    "dosage": item.dosage,
                    "frequency": item.frequency,
                    "duration": item.duration,
                    "timing": item.timing,
                    "instruction": item.instruction,
                }
                for item in visit.prescription.items
            ],
        }
    invoice = None
    if visit.invoice:
        invoice = {
            "number": visit.invoice.number,
            "subtotal": visit.invoice.subtotal,
            "discount": visit.invoice.discount,
            "coverage": visit.invoice.coverage,
            "payable": visit.invoice.payable,
            "status": enum_value(visit.invoice.status),
            "method": visit.invoice.payment.method if visit.invoice.payment else "",
            "paidAt": visit.invoice.payment.created_at.isoformat() if visit.invoice.payment else None,
            "items": [
                {
                    "description": item.description,
                    "category": item.category,
                    "quantity": item.quantity,
                    "price": item.price,
                }
                for item in visit.invoice.items
            ],
        }
    referral = None
    if visit.referral:
        referral = {
            "number": visit.referral.number,
            "hospital": visit.referral.hospital,
            "specialist": visit.referral.specialist,
            "reason": visit.referral.reason,
            "notes": visit.referral.notes,
            "createdAt": visit.referral.created_at.isoformat(),
        }
    return {
        "id": visit.id,
        "appointmentId": visit.appointment_id,
        "queue": visit.queue,
        "queueState": visit.queue_state,
        "status": enum_value(visit.status),
        "nursing": nursing,
        "examination": examination,
        "prescription": prescription,
        "invoice": invoice,
        "referral": referral,
    }


def scoped_visits(db: Session, user: User) -> list[Visit]:
    query = select(Visit).join(Appointment)
    if user.role == Role.PATIENT:
        query = query.where(Appointment.patient_id == user.patient.id)
    elif user.role == Role.DOCTOR:
        query = query.where(Appointment.doctor_id == user.doctor.id)
    elif user.role == Role.NURSE:
        query = query.outerjoin(NursingAssessment).where(
            or_(Visit.status == VisitStatus.WAITING_NURSE, NursingAssessment.nurse_id == user.id)
        )
    elif user.role == Role.PHARMACIST:
        from .models import Prescription

        query = query.join(Prescription)
    return list(db.scalars(query.order_by(Visit.id)).unique().all())


def state_for(db: Session, user: User) -> dict:
    visits = scoped_visits(db, user)
    if user.role == Role.ADMIN:
        appointments = list(db.scalars(select(Appointment).order_by(Appointment.id)).all())
        patients = list(db.scalars(select(Patient).order_by(Patient.id)).all())
        users = list(db.scalars(select(User).order_by(User.id)).all())
    elif user.role == Role.PATIENT:
        appointments = list(
            db.scalars(
                select(Appointment)
                .where(Appointment.patient_id == user.patient.id)
                .order_by(Appointment.id)
            ).all()
        )
        patients = [user.patient]
        users = [user]
    else:
        appointment_ids = {visit.appointment_id for visit in visits}
        appointments = list(
            db.scalars(
                select(Appointment)
                .where(Appointment.id.in_(appointment_ids or {-1}))
                .order_by(Appointment.id)
            ).all()
        )
        patient_ids = {appointment.patient_id for appointment in appointments}
        patients = list(
            db.scalars(select(Patient).where(Patient.id.in_(patient_ids or {-1}))).all()
        )
        users = [user, *(patient.user for patient in patients)]

    doctors = list(db.scalars(select(Doctor).join(User).where(User.active.is_(True)).order_by(Doctor.id)).all())
    users.extend(doctor.user for doctor in doctors)
    deduped_users = {item.id: item for item in users}
    medicines = list(db.scalars(select(Medicine).order_by(Medicine.name)).all())
    movements = []
    if user.role in {Role.ADMIN, Role.PHARMACIST}:
        movements = list(db.scalars(select(StockMovement).order_by(StockMovement.id.desc()).limit(200)).all())
    notifications = list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.id.desc())
            .limit(50)
        ).all()
    )
    return {
        "meta": {"version": 4, "source": "fastapi", "serverTime": datetime.now().isoformat()},
        "session": {"userId": user.id},
        "users": [serialize_user(item) for item in sorted(deduped_users.values(), key=lambda value: value.id)],
        "patients": [serialize_patient(item) for item in patients],
        "doctors": [serialize_doctor(item) for item in doctors],
        "appointments": [serialize_appointment(item) for item in appointments],
        "visits": [serialize_visit(item, user) for item in visits],
        "medicines": [
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "unit": item.unit,
                "stock": item.stock,
                "price": item.price,
                "minimum": item.minimum,
                "expiry": item.expiry.isoformat() if item.expiry else None,
            }
            for item in medicines
        ],
        "stockMovements": [
            {
                "id": item.id,
                "medicineId": item.medicine_id,
                "quantity": item.quantity,
                "reason": item.reason,
                "createdAt": item.created_at.isoformat(),
            }
            for item in movements
        ],
        "notifications": [
            {
                "id": item.id,
                "userId": item.user_id,
                "message": item.message,
                "read": item.read,
                "createdAt": item.created_at.isoformat(),
            }
            for item in notifications
        ],
    }

