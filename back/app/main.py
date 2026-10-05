from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
import csv
import io

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal, create_schema, get_db
from .models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    DoctorSchedule,
    Medicine,
    Notification,
    Patient,
    Payment,
    Role,
    StockMovement,
    User,
    Visit,
    VisitStatus,
)
from .schemas import (
    AppointmentInput,
    DoctorInput,
    ExaminationInput,
    LoginInput,
    MedicineInput,
    NursingInput,
    PaymentInput,
    ProfileInput,
    ReferralInput,
    RegisterInput,
    ScheduleInput,
    StaffInput,
    StockInput,
    UserActiveInput,
)
from .security import allow_roles, create_access_token, current_user
from .seed import seed_database
from .serializers import serialize_doctor, serialize_user, state_for
from .services import (
    DomainError,
    adjust_stock,
    available_slots,
    book_appointment,
    cancel_appointment,
    create_referral,
    generate_reminders,
    pay_invoice,
    process_pharmacy,
    save_examination,
    save_nursing,
    start_examination,
    verify_appointment,
)


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.auto_create_tables:
        create_schema()
    if settings.auto_seed:
        with SessionLocal() as db:
            seed_database(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="API sistem informasi Klinik Medika Husada.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(_request, error: DomainError):
    return JSONResponse(status_code=409, content={"detail": str(error)})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request, error: RequestValidationError):
    errors = error.errors()
    message = errors[0].get("msg", "Data tidak valid.") if errors else "Data tidak valid."
    return JSONResponse(status_code=422, content={"detail": message})


def commit(db: Session) -> None:
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Data bentrok atau telah berubah. Periksa email, NIK, atau slot lalu coba lagi.",
        )


def changed(db: Session, user: User, message: str) -> dict:
    commit(db)
    return {"ok": True, "message": message, "state": state_for(db, user)}


def load_appointment(db: Session, appointment_id: int, lock: bool = False) -> Appointment:
    query = select(Appointment).where(Appointment.id == appointment_id)
    if lock:
        query = query.with_for_update()
    appointment = db.scalar(query)
    if not appointment:
        raise HTTPException(status_code=404, detail="Janji temu tidak ditemukan.")
    return appointment


def appointment_access(appointment: Appointment, user: User) -> None:
    if user.role == Role.PATIENT and appointment.patient.user_id != user.id:
        raise HTTPException(status_code=403, detail="Janji temu bukan milik Anda.")
    if user.role not in {Role.PATIENT, Role.ADMIN}:
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke janji temu ini.")


def load_visit(db: Session, visit_id: int, lock: bool = False) -> Visit:
    query = select(Visit).where(Visit.id == visit_id)
    if lock:
        query = query.with_for_update()
    visit = db.scalar(query)
    if not visit:
        raise HTTPException(status_code=404, detail="Kunjungan tidak ditemukan.")
    return visit


def visit_access(visit: Visit, user: User, clinical: bool = False) -> None:
    if user.role == Role.PATIENT and visit.patient.user_id != user.id:
        raise HTTPException(status_code=403, detail="Kunjungan bukan milik Anda.")
    if user.role == Role.DOCTOR and visit.doctor.user_id != user.id:
        raise HTTPException(status_code=403, detail="Kunjungan bukan pasien dokter ini.")
    if user.role == Role.NURSE and visit.status != VisitStatus.WAITING_NURSE and (
        not visit.nursing or visit.nursing.nurse_id != user.id
    ):
        raise HTTPException(status_code=403, detail="Kunjungan tidak berada dalam cakupan perawat.")
    if user.role == Role.PHARMACIST and (clinical or not visit.prescription):
        raise HTTPException(status_code=403, detail="Kunjungan tidak berada dalam cakupan farmasi.")


def register_patient(db: Session, data: RegisterInput) -> User:
    email = data.email.lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise DomainError("Email tidak valid.")
    if not data.phone.lstrip("+").isdigit():
        raise DomainError("Nomor telepon tidak valid.")
    user = User(
        email=email,
        name=data.name,
        role=Role.PATIENT,
        phone=data.phone,
        active=True,
    )
    user.set_password(data.password)
    patient = Patient(
        user=user,
        nik=data.nik,
        birth_date=data.birthDate,
        gender=data.gender,
        address=data.address,
        bpjs=data.bpjs,
        bpjs_active=bool(data.bpjs),
    )
    db.add_all([user, patient])
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email atau NIK sudah digunakan.")
    patient.mr = f"KMH-{date.today().year}-{patient.id:05}"
    db.add(Notification(user_id=user.id, message="Selamat datang di Medika Husada."))
    return user


@app.get("/", tags=["system"])
def root():
    return {
        "name": settings.app_name,
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected", "time": datetime.now().isoformat()}


prefix = settings.api_prefix


@app.post(f"{prefix}/auth/login", tags=["auth"])
def login(data: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not user.active or not user.check_password(data.password):
        raise HTTPException(status_code=401, detail="Email atau password tidak valid, atau akun nonaktif.")
    return {
        "accessToken": create_access_token(user.id),
        "tokenType": "bearer",
        "user": serialize_user(user),
        "state": state_for(db, user),
    }


@app.post(f"{prefix}/auth/register", status_code=201, tags=["auth"])
def register(data: RegisterInput, db: Session = Depends(get_db)):
    user = register_patient(db, data)
    commit(db)
    return {
        "accessToken": create_access_token(user.id),
        "tokenType": "bearer",
        "user": serialize_user(user),
        "state": state_for(db, user),
    }


@app.get(f"{prefix}/auth/me", tags=["auth"])
def me(user: User = Depends(current_user)):
    return serialize_user(user)


@app.get(f"{prefix}/state", tags=["application"])
def get_state(user: User = Depends(current_user), db: Session = Depends(get_db)):
    generate_reminders(db, user)
    commit(db)
    return state_for(db, user)


@app.get(f"{prefix}/public", tags=["application"])
def public_data(db: Session = Depends(get_db)):
    doctors = list(
        db.scalars(
            select(Doctor).join(User).where(User.active.is_(True)).order_by(Doctor.id)
        ).all()
    )
    today = date.today()
    slots_by_doctor = {
        str(doctor.id): available_slots(db, doctor.id, today) for doctor in doctors
    }
    return {
        "date": today.isoformat(),
        "users": [serialize_user(doctor.user) for doctor in doctors],
        "doctors": [serialize_doctor(doctor) for doctor in doctors],
        "slots": slots_by_doctor,
    }


@app.get(f"{prefix}/slots", tags=["appointments"])
def slots(
    doctor_id: int,
    day: date = Query(alias="date"),
    exclude_id: int | None = None,
    db: Session = Depends(get_db),
):
    return {"items": available_slots(db, doctor_id, day, exclude_id)}


@app.post(f"{prefix}/appointments", status_code=201, tags=["appointments"])
def create_appointment(
    data: AppointmentInput,
    user: User = Depends(allow_roles(Role.PATIENT, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    patient = user.patient if user.role == Role.PATIENT else db.get(Patient, data.patientId)
    if not patient:
        raise HTTPException(status_code=404, detail="Pasien tidak ditemukan.")
    appointment = book_appointment(db, patient, data)
    commit(db)
    return {
        "ok": True,
        "message": "Janji berhasil dibuat dan menunggu verifikasi.",
        "appointmentId": appointment.id,
        "state": state_for(db, user),
    }


@app.put(f"{prefix}/appointments/{{appointment_id}}", tags=["appointments"])
def reschedule_appointment(
    appointment_id: int,
    data: AppointmentInput,
    user: User = Depends(allow_roles(Role.PATIENT, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    appointment = load_appointment(db, appointment_id, lock=True)
    appointment_access(appointment, user)
    book_appointment(db, appointment.patient, data, appointment)
    return changed(db, user, "Jadwal diperbarui dan menunggu verifikasi ulang.")


@app.post(f"{prefix}/appointments/{{appointment_id}}/verify", tags=["appointments"])
def verify(
    appointment_id: int,
    user: User = Depends(allow_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    appointment = load_appointment(db, appointment_id, lock=True)
    verify_appointment(db, appointment)
    return changed(db, user, "Janji terverifikasi dan nomor antrean dibuat.")


@app.post(f"{prefix}/appointments/{{appointment_id}}/cancel", tags=["appointments"])
def cancel(
    appointment_id: int,
    user: User = Depends(allow_roles(Role.PATIENT, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    appointment = load_appointment(db, appointment_id, lock=True)
    appointment_access(appointment, user)
    cancel_appointment(db, appointment)
    return changed(db, user, "Janji dibatalkan dan slot dilepas.")


@app.post(f"{prefix}/appointments/{{appointment_id}}/reject", tags=["appointments"])
def reject(
    appointment_id: int,
    user: User = Depends(allow_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    appointment = load_appointment(db, appointment_id, lock=True)
    cancel_appointment(db, appointment, rejected=True)
    return changed(db, user, "Janji ditolak.")


@app.post(f"{prefix}/visits/{{visit_id}}/queue/{{action}}", tags=["visits"])
def queue_action(
    visit_id: int,
    action: str,
    user: User = Depends(allow_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    visit = load_visit(db, visit_id, lock=True)
    if visit.status not in {VisitStatus.WAITING_NURSE, VisitStatus.WAITING_DOCTOR}:
        raise DomainError("Pasien tidak berada pada antrean pemeriksaan.")
    states = {"call": "CALLED", "skip": "SKIPPED", "restore": "WAITING"}
    if action not in states:
        raise DomainError("Aksi antrean tidak valid.")
    visit.queue_state = states[action]
    return changed(db, user, "Status antrean diperbarui.")


@app.post(f"{prefix}/visits/{{visit_id}}/nursing", tags=["visits"])
def nursing(
    visit_id: int,
    data: NursingInput,
    user: User = Depends(allow_roles(Role.NURSE)),
    db: Session = Depends(get_db),
):
    visit = load_visit(db, visit_id, lock=True)
    visit_access(visit, user)
    save_nursing(db, visit, user, data)
    return changed(db, user, "Pemeriksaan awal tersimpan.")


@app.post(f"{prefix}/visits/{{visit_id}}/start", tags=["visits"])
def start_exam(
    visit_id: int,
    user: User = Depends(allow_roles(Role.DOCTOR)),
    db: Session = Depends(get_db),
):
    visit = load_visit(db, visit_id, lock=True)
    visit_access(visit, user)
    start_examination(db, visit)
    return changed(db, user, "Pemeriksaan dokter dimulai.")


@app.post(f"{prefix}/visits/{{visit_id}}/examination", tags=["visits"])
def examination(
    visit_id: int,
    data: ExaminationInput,
    user: User = Depends(allow_roles(Role.DOCTOR)),
    db: Session = Depends(get_db),
):
    visit = load_visit(db, visit_id, lock=True)
    visit_access(visit, user)
    save_examination(db, visit, data)
    return changed(db, user, "Pemeriksaan dokter tersimpan.")


@app.post(f"{prefix}/visits/{{visit_id}}/pharmacy/{{action}}", tags=["pharmacy"])
def pharmacy(
    visit_id: int,
    action: str,
    user: User = Depends(allow_roles(Role.PHARMACIST)),
    db: Session = Depends(get_db),
):
    visit = load_visit(db, visit_id, lock=True)
    visit_access(visit, user)
    process_pharmacy(db, visit, action, user)
    return changed(db, user, "Status farmasi diperbarui.")


@app.post(f"{prefix}/visits/{{visit_id}}/payment", tags=["billing"])
def payment(
    visit_id: int,
    data: PaymentInput,
    user: User = Depends(allow_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    visit = load_visit(db, visit_id, lock=True)
    pay_invoice(db, visit, user, data)
    return changed(db, user, "Pembayaran berhasil dikonfirmasi.")


@app.post(f"{prefix}/visits/{{visit_id}}/referral", tags=["visits"])
def referral(
    visit_id: int,
    data: ReferralInput,
    user: User = Depends(allow_roles(Role.DOCTOR)),
    db: Session = Depends(get_db),
):
    visit = load_visit(db, visit_id, lock=True)
    visit_access(visit, user, clinical=True)
    create_referral(db, visit, data)
    return changed(db, user, "Surat rujukan diterbitkan.")


@app.patch(f"{prefix}/medicines/{{medicine_id}}/stock", tags=["pharmacy"])
def stock(
    medicine_id: int,
    data: StockInput,
    user: User = Depends(allow_roles(Role.ADMIN, Role.PHARMACIST)),
    db: Session = Depends(get_db),
):
    medicine = db.get(Medicine, medicine_id)
    if not medicine:
        raise HTTPException(status_code=404, detail="Obat tidak ditemukan.")
    adjust_stock(db, medicine, data.delta, data.reason, user)
    return changed(db, user, "Stok berhasil diperbarui.")


@app.post(f"{prefix}/medicines", status_code=201, tags=["pharmacy"])
def create_medicine(
    data: MedicineInput,
    user: User = Depends(allow_roles(Role.ADMIN, Role.PHARMACIST)),
    db: Session = Depends(get_db),
):
    medicine = Medicine(
        name=data.name,
        category=data.category,
        unit=data.unit,
        stock=0,
        price=data.price,
        minimum=data.minimum,
        expiry=data.expiry,
    )
    db.add(medicine)
    db.flush()
    if data.initialStock:
        adjust_stock(db, medicine, data.initialStock, "Stok awal", user)
    return changed(db, user, "Obat berhasil ditambahkan.")


@app.put(f"{prefix}/profile", tags=["patients"])
def update_profile(
    data: ProfileInput,
    user: User = Depends(allow_roles(Role.PATIENT)),
    db: Session = Depends(get_db),
):
    if data.birthDate > date.today() or data.birthDate.year < 1900:
        raise DomainError("Tanggal lahir tidak valid.")
    if data.gender not in {"Laki-laki", "Perempuan"}:
        raise DomainError("Pilih jenis kelamin.")
    if not data.phone.lstrip("+").isdigit():
        raise DomainError("Nomor telepon tidak valid.")
    if data.bpjs and (len(data.bpjs) != 13 or not data.bpjs.isdigit()):
        raise DomainError("Nomor BPJS harus 13 digit.")
    patient = user.patient
    user.name = data.name
    user.phone = data.phone
    patient.nik = data.nik
    patient.birth_date = data.birthDate
    patient.gender = data.gender
    patient.address = data.address
    patient.bpjs = data.bpjs
    patient.bpjs_active = bool(data.bpjs)
    patient.allergies = data.allergies
    patient.history = data.history
    patient.surgery = data.surgery
    patient.medication = data.medication
    patient.emergency = data.emergency
    return changed(db, user, "Profil berhasil diperbarui.")


@app.post(f"{prefix}/notifications/read", tags=["application"])
def read_notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    for item in db.scalars(
        select(Notification).where(Notification.user_id == user.id, Notification.read.is_(False))
    ).all():
        item.read = True
    return changed(db, user, "Semua notifikasi ditandai dibaca.")


@app.post(f"{prefix}/admin/users", status_code=201, tags=["administration"])
def create_staff(
    data: StaffInput,
    admin: User = Depends(allow_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    user = User(
        email=data.email.lower(),
        name=data.name,
        role=Role(data.role),
        phone=data.phone,
        active=True,
    )
    user.set_password(data.password)
    db.add(user)
    return changed(db, admin, "Akun petugas berhasil dibuat.")


@app.patch(f"{prefix}/admin/users/{{user_id}}", tags=["administration"])
def update_user_status(
    user_id: int,
    data: UserActiveInput,
    admin: User = Depends(allow_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    if target.id == admin.id and not data.active:
        raise DomainError("Akun sendiri tidak dapat dinonaktifkan.")
    target.active = data.active
    return changed(db, admin, "Status akun diperbarui.")


@app.post(f"{prefix}/admin/doctors", status_code=201, tags=["administration"])
def create_doctor(
    data: DoctorInput,
    admin: User = Depends(allow_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    if not data.password:
        raise DomainError("Password wajib untuk dokter baru.")
    user = User(
        email=data.email.lower(),
        name=data.name,
        role=Role.DOCTOR,
        phone=data.phone,
        active=data.active,
    )
    user.set_password(data.password)
    db.add(Doctor(user=user, specialty=data.specialty, fee=data.fee))
    return changed(db, admin, "Dokter berhasil ditambahkan.")


@app.put(f"{prefix}/admin/doctors/{{doctor_id}}", tags=["administration"])
def update_doctor(
    doctor_id: int,
    data: DoctorInput,
    admin: User = Depends(allow_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Dokter tidak ditemukan.")
    doctor.user.name = data.name
    doctor.user.email = data.email.lower()
    doctor.user.phone = data.phone
    doctor.user.active = data.active
    if data.password:
        doctor.user.set_password(data.password)
    doctor.specialty = data.specialty
    doctor.fee = data.fee
    return changed(db, admin, "Data dokter diperbarui.")


@app.put(f"{prefix}/admin/doctors/{{doctor_id}}/schedules", tags=["administration"])
def upsert_schedule(
    doctor_id: int,
    data: ScheduleInput,
    admin: User = Depends(allow_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Dokter tidak ditemukan.")
    try:
        start_time = datetime.strptime(data.start, "%H:%M").time()
        end_time = datetime.strptime(data.end, "%H:%M").time()
    except ValueError:
        raise DomainError("Jam praktik tidak valid.")
    if start_time >= end_time:
        raise DomainError("Jam akhir harus sesudah jam mulai.")
    schedule = db.scalar(
        select(DoctorSchedule).where(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.weekday == data.weekday,
        )
    )
    if not schedule:
        schedule = DoctorSchedule(doctor=doctor, weekday=data.weekday)
    schedule.start = data.start
    schedule.end = data.end
    schedule.interval = data.interval
    schedule.quota = data.quota
    db.add(schedule)
    return changed(db, admin, "Jadwal dokter diperbarui.")


@app.delete(f"{prefix}/admin/doctors/{{doctor_id}}/schedules/{{weekday}}", tags=["administration"])
def delete_schedule(
    doctor_id: int,
    weekday: int,
    admin: User = Depends(allow_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    schedule = db.scalar(
        select(DoctorSchedule).where(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.weekday == weekday,
        )
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan.")
    db.delete(schedule)
    return changed(db, admin, "Jadwal dokter dihapus.")


@app.get(f"{prefix}/reports.csv", tags=["reports"])
def export_report(
    start: date | None = None,
    end: date | None = None,
    _admin: User = Depends(allow_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
):
    today = date.today()
    start = start or today.replace(day=1)
    end = end or today
    if start > end:
        raise HTTPException(status_code=422, detail="Tanggal awal harus sebelum tanggal akhir.")
    payments = db.scalars(
        select(Payment)
        .where(
            Payment.created_at >= datetime.combine(start, time.min),
            Payment.created_at < datetime.combine(end + timedelta(days=1), time.min),
        )
        .order_by(Payment.created_at.desc())
    ).all()
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["Invoice", "Tanggal", "Metode", "Biaya bruto", "Diskon", "BPJS", "Dibayar pasien"])
    for payment_item in payments:
        invoice = payment_item.invoice
        writer.writerow(
            [
                invoice.number,
                payment_item.created_at.isoformat(),
                payment_item.method,
                invoice.subtotal,
                invoice.discount,
                invoice.coverage,
                payment_item.amount,
            ]
        )
    return Response(
        content="\ufeff" + stream.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=laporan-medika-husada.csv"},
    )

