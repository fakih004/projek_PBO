"""Transactional business rules shared by the FastAPI routes."""
from datetime import date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    DoctorExamination,
    DoctorSchedule,
    Invoice,
    InvoiceItem,
    Medicine,
    Notification,
    NursingAssessment,
    Payment,
    PaymentStatus,
    Prescription,
    PrescriptionItem,
    PrescriptionStatus,
    QueueCounter,
    Referral,
    Role,
    StockMovement,
    User,
    Visit,
    VisitStatus,
)


LABELS = {
    "WAITING_VERIFICATION": "Menunggu verifikasi ulang",
    "PENDING": "Menunggu verifikasi",
    "RESCHEDULED": "Jadwal diubah · menunggu verifikasi",
    "VERIFIED": "Terverifikasi",
    "CHECKED_IN": "Sudah hadir",
    "CANCELLED": "Dibatalkan",
    "REJECTED": "Ditolak",
    "WAITING_NURSE": "Menunggu pemeriksaan perawat",
    "WAITING_DOCTOR": "Menunggu dokter",
    "WITH_DOCTOR": "Pemeriksaan dokter",
    "WAITING_PHARMACY": "Resep diterima apotek",
    "PHARMACY_PROCESSING": "Obat sedang disiapkan",
    "MEDICINE_READY": "Obat siap diambil",
    "WAITING_PAYMENT": "Menunggu pembayaran",
    "COMPLETED": "Pelayanan selesai",
}


class DomainError(ValueError):
    pass


def notify(db: Session, user_id: int, message: str, unique_key: str | None = None) -> None:
    if unique_key and db.scalar(select(Notification.id).where(Notification.unique_key == unique_key)):
        return
    db.add(Notification(user_id=user_id, message=message, unique_key=unique_key))


def available_slots(
    db: Session, doctor_id: int, day: date, exclude_appointment_id: int | None = None
) -> list[dict]:
    doctor = db.get(Doctor, doctor_id)
    if not doctor or not doctor.user.active:
        return []
    schedule = db.scalar(
        select(DoctorSchedule).where(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.weekday == day.weekday(),
        )
    )
    if not schedule:
        return []
    appointments = db.scalars(
        select(Appointment).where(Appointment.doctor_id == doctor_id, Appointment.date == day)
    ).all()
    occupied = {
        appointment.time
        for appointment in appointments
        if appointment.slot_key and appointment.id != exclude_appointment_id
    }
    cursor = datetime.combine(day, datetime.strptime(schedule.start, "%H:%M").time())
    end = datetime.combine(day, datetime.strptime(schedule.end, "%H:%M").time())
    result: list[dict] = []
    while cursor < end and len(result) < schedule.quota:
        slot = cursor.strftime("%H:%M")
        result.append({"time": slot, "available": slot not in occupied and cursor > datetime.now()})
        cursor += timedelta(minutes=schedule.interval)
    return result


def book_appointment(
    db: Session,
    patient,
    data,
    appointment: Appointment | None = None,
) -> Appointment:
    if appointment and appointment.status not in {
        AppointmentStatus.PENDING,
        AppointmentStatus.RESCHEDULED,
        AppointmentStatus.VERIFIED,
    }:
        raise DomainError("Janji sudah diperiksa, selesai, atau dibatalkan.")
    if appointment and appointment.visit and appointment.visit.status not in {
        VisitStatus.WAITING_NURSE,
        VisitStatus.WAITING_VERIFICATION,
    }:
        raise DomainError("Pemeriksaan sudah dimulai. Janji tidak dapat diubah.")
    if not any(
        slot["time"] == data.time and slot["available"]
        for slot in available_slots(db, data.doctorId, data.date, appointment.id if appointment else None)
    ):
        raise DomainError("Slot penuh, sudah lewat, atau di luar jadwal dokter.")
    insurance = data.insurance == "bpjs"
    if insurance and (not patient.bpjs or not patient.bpjs_active):
        raise DomainError("Pasien belum memiliki BPJS aktif.")
    if appointment is None:
        appointment = Appointment(patient=patient)
        db.add(appointment)
    else:
        appointment.status = AppointmentStatus.RESCHEDULED
        if appointment.visit:
            appointment.visit.status = VisitStatus.WAITING_VERIFICATION
            appointment.visit.queue = "—"
            appointment.visit.queue_state = "WAITING"
    appointment.doctor_id = data.doctorId
    appointment.date = data.date
    appointment.time = data.time
    appointment.complaint = data.complaint
    appointment.notes = data.notes
    appointment.insurance = insurance
    appointment.slot_key = f"{data.doctorId}:{data.date.isoformat()}:{data.time}"
    appointment.status = AppointmentStatus.RESCHEDULED if appointment.id else AppointmentStatus.PENDING
    notify(
        db,
        patient.user_id,
        "Janji diperbarui dan menunggu verifikasi."
        if appointment.id
        else "Janji berhasil dibuat. Menunggu verifikasi admin.",
    )
    admin_ids = db.scalars(select(User.id).where(User.role == Role.ADMIN, User.active.is_(True))).all()
    for admin_id in admin_ids:
        notify(db, admin_id, f"Janji untuk {patient.user.name} menunggu verifikasi.")
    return appointment


def cancel_appointment(db: Session, appointment: Appointment, rejected: bool = False) -> None:
    if appointment.status not in {
        AppointmentStatus.PENDING,
        AppointmentStatus.RESCHEDULED,
        AppointmentStatus.VERIFIED,
    }:
        raise DomainError("Janji sudah diperiksa, selesai, atau dibatalkan.")
    if appointment.visit and appointment.visit.status not in {
        VisitStatus.WAITING_NURSE,
        VisitStatus.WAITING_VERIFICATION,
    }:
        raise DomainError("Pemeriksaan sudah dimulai. Janji tidak dapat dibatalkan.")
    appointment.status = AppointmentStatus.REJECTED if rejected else AppointmentStatus.CANCELLED
    appointment.slot_key = None
    if appointment.visit:
        appointment.visit.status = VisitStatus.CANCELLED
        appointment.visit.queue = "—"
    notify(
        db,
        appointment.patient.user_id,
        "Janji ditolak oleh admin." if rejected else "Janji dibatalkan. Slot tersedia kembali.",
    )


def verify_appointment(db: Session, appointment: Appointment) -> Visit:
    if appointment.status not in {AppointmentStatus.PENDING, AppointmentStatus.RESCHEDULED}:
        raise DomainError("Janji sudah diproses.")
    appointment.status = AppointmentStatus.VERIFIED
    counter = db.scalar(
        select(QueueCounter)
        .where(QueueCounter.doctor_id == appointment.doctor_id, QueueCounter.date == appointment.date)
        .with_for_update()
    )
    if counter is None:
        counter = QueueCounter(doctor_id=appointment.doctor_id, date=appointment.date, value=0)
        db.add(counter)
        db.flush()
    counter.value += 1
    visit = appointment.visit
    if visit is None:
        visit = Visit(appointment=appointment, queue="—")
        db.add(visit)
    visit.queue = f"D{appointment.doctor_id}-{counter.value:03}"
    visit.status = VisitStatus.WAITING_NURSE
    visit.queue_state = "WAITING"
    notify(
        db,
        appointment.patient.user_id,
        f"Appointment terverifikasi. Antrean {visit.queue}. Menunggu pemeriksaan perawat.",
    )
    return visit


def ensure_visit_day(visit: Visit) -> None:
    if visit.appointment.date > date.today():
        raise DomainError("Pemeriksaan hanya dapat dilakukan pada hari kunjungan atau sesudahnya.")


def transition(visit: Visit, expected: set[VisitStatus], target: VisitStatus) -> None:
    ensure_visit_day(visit)
    if visit.status not in expected:
        raise DomainError("Status sudah berubah. Muat ulang halaman sebelum melanjutkan.")
    visit.status = target
    visit.updated_at = datetime.now()


def save_nursing(db: Session, visit: Visit, nurse: User, data) -> None:
    transition(visit, {VisitStatus.WAITING_NURSE}, VisitStatus.WAITING_DOCTOR)
    if visit.nursing:
        raise DomainError("Pemeriksaan awal sudah tersimpan.")
    visit.nursing = NursingAssessment(
        nurse_id=nurse.id,
        systolic=data.systolic,
        diastolic=data.diastolic,
        temperature=data.temperature,
        weight=data.weight,
        height=data.height,
        pulse=data.pulse,
        respiration=data.respiration,
        spo2=data.spo2,
        pain=data.pain,
        complaint=data.complaint,
        notes=data.notes,
    )
    visit.appointment.status = AppointmentStatus.CHECKED_IN
    notify(db, visit.patient.user_id, LABELS[VisitStatus.WAITING_DOCTOR.value])


def start_examination(db: Session, visit: Visit) -> None:
    transition(visit, {VisitStatus.WAITING_DOCTOR}, VisitStatus.WITH_DOCTOR)
    notify(db, visit.patient.user_id, LABELS[VisitStatus.WITH_DOCTOR.value])


def create_invoice(db: Session, visit: Visit) -> Invoice:
    if visit.invoice:
        return visit.invoice
    items = [
        InvoiceItem(
            description="Konsultasi dokter",
            category="consultation",
            quantity=1,
            price=visit.doctor.fee,
        )
    ]
    if visit.examination and visit.examination.treatment_fee:
        items.append(
            InvoiceItem(
                description=visit.examination.treatment or "Tindakan",
                category="treatment",
                quantity=1,
                price=visit.examination.treatment_fee,
            )
        )
    if visit.prescription:
        items.extend(
            InvoiceItem(
                description=item.medicine.name,
                category="medicine",
                quantity=item.quantity,
                price=item.price,
            )
            for item in visit.prescription.items
        )
    total = sum(item.quantity * item.price for item in items)
    coverage = total if visit.appointment.insurance else 0
    invoice = Invoice(
        visit=visit,
        number=f"INV-{visit.appointment.date:%Y%m%d}-{visit.id:05}",
        subtotal=total,
        coverage=coverage,
        payable=total - coverage,
        items=items,
    )
    db.add(invoice)
    return invoice


def save_examination(db: Session, visit: Visit, data) -> None:
    transition(visit, {VisitStatus.WITH_DOCTOR}, VisitStatus.WAITING_PHARMACY if data.items else VisitStatus.WAITING_PAYMENT)
    if visit.examination:
        raise DomainError("Pemeriksaan dokter sudah tersimpan.")
    visit.examination = DoctorExamination(
        anamnesis=data.anamnesis,
        physical=data.physical,
        assessment=data.assessment,
        diagnosis=data.diagnosis,
        secondary=data.secondary,
        icd10=data.icd10,
        treatment=data.treatment,
        treatment_fee=data.treatmentFee,
        notes=data.notes,
        recommendation=data.recommendation,
        followup=data.followup,
        laboratory=data.laboratory,
    )
    if data.items:
        prescription = Prescription(visit=visit)
        for item in data.items:
            medicine = db.get(Medicine, item.medicineId)
            if not medicine:
                raise DomainError("Obat tidak valid.")
            prescription.items.append(
                PrescriptionItem(
                    medicine=medicine,
                    quantity=item.quantity,
                    price=medicine.price,
                    dosage=item.dosage,
                    frequency=item.frequency,
                    duration=item.duration,
                    timing=item.timing,
                    instruction=item.instruction,
                )
            )
        db.add(prescription)
    else:
        db.flush()
        create_invoice(db, visit)
    notify(db, visit.patient.user_id, LABELS[visit.status.value])


def process_pharmacy(db: Session, visit: Visit, action: str, actor: User) -> None:
    prescription = visit.prescription
    if not prescription:
        raise DomainError("Resep tidak ditemukan.")
    if action == "start":
        transition(visit, {VisitStatus.WAITING_PHARMACY}, VisitStatus.PHARMACY_PROCESSING)
        prescription.status = PrescriptionStatus.PROCESSING
    elif action == "shortage":
        if visit.status not in {VisitStatus.WAITING_PHARMACY, VisitStatus.PHARMACY_PROCESSING}:
            raise DomainError("Resep telah diproses.")
        prescription.status = PrescriptionStatus.OUT_OF_STOCK
        notify(db, visit.patient.user_id, "Apotek melaporkan stok tidak cukup.")
        admins = db.scalars(select(User).where(User.role == Role.ADMIN, User.active.is_(True))).all()
        for user in [*admins, visit.doctor.user]:
            notify(db, user.id, f"Stok tidak cukup untuk resep kunjungan #{visit.id}.")
        return
    elif action == "ready":
        if visit.status != VisitStatus.PHARMACY_PROCESSING:
            raise DomainError("Aksi farmasi tidak sesuai status saat ini.")
        medicine_ids = [item.medicine_id for item in prescription.items]
        locked = {
            med.id: med
            for med in db.scalars(
                select(Medicine).where(Medicine.id.in_(medicine_ids)).with_for_update()
            ).all()
        }
        for item in prescription.items:
            medicine = locked[item.medicine_id]
            if medicine.expiry and medicine.expiry < date.today():
                raise DomainError(f"{medicine.name} kedaluwarsa.")
            if medicine.stock < item.quantity:
                raise DomainError(f"Stok {medicine.name} tidak cukup.")
        for item in prescription.items:
            medicine = locked[item.medicine_id]
            medicine.stock -= item.quantity
            db.add(
                StockMovement(
                    medicine_id=medicine.id,
                    quantity=-item.quantity,
                    reason="Penyerahan resep",
                    actor_id=actor.id,
                    visit_id=visit.id,
                )
            )
        visit.status = VisitStatus.MEDICINE_READY
        prescription.status = PrescriptionStatus.READY
    elif action == "handover":
        transition(visit, {VisitStatus.MEDICINE_READY}, VisitStatus.WAITING_PAYMENT)
        prescription.status = PrescriptionStatus.DISPENSED
        create_invoice(db, visit)
    else:
        raise DomainError("Aksi farmasi tidak dikenal.")
    notify(db, visit.patient.user_id, LABELS[visit.status.value])


def pay_invoice(db: Session, visit: Visit, admin: User, data) -> Payment:
    invoice = visit.invoice
    if not invoice:
        raise DomainError("Invoice belum tersedia.")
    if data.discount > invoice.subtotal:
        raise DomainError("Diskon tidak boleh melebihi subtotal.")
    method = "BPJS" if visit.appointment.insurance else data.method
    if method not in {"BPJS", "Tunai", "Transfer", "QRIS", "Debit"}:
        raise DomainError("Metode pembayaran tidak valid.")
    if not visit.appointment.insurance and method == "BPJS":
        raise DomainError("Kunjungan ini bukan BPJS.")
    transition(visit, {VisitStatus.WAITING_PAYMENT}, VisitStatus.COMPLETED)
    status = PaymentStatus.BPJS_COVERED if visit.appointment.insurance else PaymentStatus.PAID
    net = invoice.subtotal - data.discount
    invoice.discount = data.discount
    invoice.coverage = net if visit.appointment.insurance else 0
    invoice.payable = 0 if visit.appointment.insurance else net
    invoice.status = status
    payment = Payment(
        invoice=invoice,
        admin_id=admin.id,
        amount=invoice.payable,
        method=method,
        status=status,
    )
    db.add(payment)
    visit.appointment.status = AppointmentStatus.COMPLETED
    notify(db, visit.patient.user_id, LABELS[VisitStatus.COMPLETED.value])
    return payment


def adjust_stock(db: Session, medicine: Medicine, delta: int, reason: str, actor: User) -> None:
    locked = db.scalar(select(Medicine).where(Medicine.id == medicine.id).with_for_update())
    if not locked or delta == 0:
        raise DomainError("Perubahan stok harus bukan nol.")
    if locked.stock + delta < 0:
        raise DomainError(f"Stok {locked.name} tidak cukup.")
    locked.stock += delta
    db.add(
        StockMovement(
            medicine_id=locked.id,
            quantity=delta,
            reason=reason,
            actor_id=actor.id,
        )
    )


def create_referral(db: Session, visit: Visit, data) -> Referral:
    if not visit.examination or visit.referral or visit.status == VisitStatus.COMPLETED:
        raise DomainError("Rujukan hanya dapat dibuat sekali setelah pemeriksaan dan sebelum kunjungan selesai.")
    referral = Referral(
        visit=visit,
        number=f"RUJ-{date.today():%Y%m%d}-{visit.id:05}",
        hospital=data.hospital,
        specialist=data.specialist,
        reason=data.reason,
        notes=data.notes,
    )
    db.add(referral)
    notify(db, visit.patient.user_id, "Surat rujukan tersedia pada rekam medis Anda.")
    return referral


def generate_reminders(db: Session, user: User) -> None:
    if user.role != Role.PATIENT or not user.patient:
        return
    now = datetime.now()
    for appointment in user.patient.appointments:
        if appointment.status not in {
            AppointmentStatus.PENDING,
            AppointmentStatus.RESCHEDULED,
            AppointmentStatus.VERIFIED,
        }:
            continue
        delta = datetime.combine(
            appointment.date, datetime.strptime(appointment.time, "%H:%M").time()
        ) - now
        window = "3h" if timedelta(0) < delta <= timedelta(hours=3) else "24h" if timedelta(hours=3) < delta <= timedelta(days=1) else None
        if window:
            notify(
                db,
                user.id,
                f"Pengingat: janji dengan {appointment.doctor.user.name}, {appointment.date} pukul {appointment.time}.",
                f"reminder:{appointment.id}:{appointment.date}:{appointment.time}:{window}",
            )

