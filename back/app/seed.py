"""Idempotent starter data for local development."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Doctor,
    DoctorSchedule,
    Medicine,
    Patient,
    Role,
    StockMovement,
    User,
)


DEMO_ACCOUNTS = [
    ("admin", "Siti Rahmawati", Role.ADMIN, "Admin123!"),
    ("perawat", "Ns. Dian Lestari", Role.NURSE, "Perawat123!"),
    ("apoteker", "apt. Rahmat Hidayat", Role.PHARMACIST, "Apoteker123!"),
    ("fakih", "dr. Muhammad Fakih Nabal", Role.DOCTOR, "Dokter123!"),
    ("alia", "dr. Alia Fransiska Dewi Arum Trilestari", Role.DOCTOR, "Dokter123!"),
    ("pasien", "Budi Santoso", Role.PATIENT, "Pasien123!"),
    ("ratna", "Ratna Permata", Role.PATIENT, "Pasien123!"),
    ("siti", "Siti Aminah", Role.PATIENT, "Pasien123!"),
]


def seed_database(db: Session) -> bool:
    """Seed only a new database. Returns True when data was inserted."""
    if db.scalar(select(User.id).limit(1)):
        return False

    users: dict[str, User] = {}
    for index, (handle, name, role, password) in enumerate(DEMO_ACCOUNTS):
        user = User(
            email=f"{handle}@medikahusada.local",
            name=name,
            role=role,
            phone=f"0812345678{index:02}",
            active=True,
        )
        user.set_password(password)
        db.add(user)
        users[handle] = user
    db.flush()

    doctors = [
        Doctor(user=users["fakih"], specialty="Dokter Umum", fee=75_000),
        Doctor(user=users["alia"], specialty="Obstetri dan Ginekologi", fee=150_000),
    ]
    db.add_all(doctors)
    db.flush()
    for doctor, start, end in ((doctors[0], "08:00", "14:00"), (doctors[1], "14:00", "20:00")):
        for weekday in range(6):
            doctor.schedules.append(
                DoctorSchedule(
                    weekday=weekday,
                    start=start,
                    end=end,
                    interval=30,
                    quota=12,
                )
            )

    patient_specs = [
        ("pasien", "3273201990000006", "Laki-laki", "", False, "Tidak diketahui"),
        ("ratna", "3273201990000007", "Perempuan", "0001234567890", True, "Penisilin"),
        ("siti", "3273201990000008", "Perempuan", "", False, ""),
    ]
    for index, (handle, nik, gender, bpjs, active, allergies) in enumerate(patient_specs, 1):
        patient = Patient(
            user=users[handle],
            nik=nik,
            birth_date=date(1990, 5, 12) if handle != "siti" else date(1994, 11, 2),
            gender=gender,
            address=f"Jl. Melati No. {index}",
            bpjs=bpjs,
            bpjs_active=active,
            allergies=allergies,
            history="Tidak tercatat",
            emergency=f"Keluarga · 08120000000{index}",
        )
        db.add(patient)
        db.flush()
        patient.mr = f"KMH-{date.today().year}-{patient.id:05}"

    medicine_specs = [
        ("Paracetamol 500 mg", "Analgesik", "tablet", 200, 1_000, 20),
        ("Amoxicillin 500 mg", "Antibiotik", "kapsul", 120, 1_800, 20),
        ("Omeprazole 20 mg", "Lambung", "kapsul", 80, 2_200, 15),
        ("Cetirizine 10 mg", "Antihistamin", "tablet", 90, 2_500, 20),
        ("Vitamin B Complex", "Vitamin", "tablet", 15, 1_600, 20),
        ("Asam Folat", "Vitamin", "tablet", 150, 1_200, 20),
        ("Ibuprofen 400 mg", "Analgesik", "tablet", 12, 2_400, 20),
    ]
    for name, category, unit, stock, price, minimum in medicine_specs:
        medicine = Medicine(
            name=name,
            category=category,
            unit=unit,
            stock=stock,
            price=price,
            minimum=minimum,
            expiry=date.today() + timedelta(days=365),
        )
        db.add(medicine)
        db.flush()
        db.add(
            StockMovement(
                medicine_id=medicine.id,
                quantity=stock,
                reason="Stok awal demo",
                actor_id=users["admin"].id,
            )
        )
    db.commit()
    return True

