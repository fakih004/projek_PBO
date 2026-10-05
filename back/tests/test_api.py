from datetime import date, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Appointment, Medicine, Payment, StockMovement, Visit, VisitStatus


def next_practice_day(client, doctor_id: int) -> tuple[str, str]:
    day = date.today() + timedelta(days=1)
    for _ in range(14):
        response = client.get(
            "/api/v1/slots", params={"doctor_id": doctor_id, "date": day.isoformat()}
        )
        available = [item for item in response.json()["items"] if item["available"]]
        if available:
            return day.isoformat(), available[0]["time"]
        day += timedelta(days=1)
    raise AssertionError("Tidak menemukan slot praktik untuk pengujian.")


def test_health_docs_and_invalid_auth(client):
    assert client.get("/health").json()["database"] == "connected"
    assert client.get("/openapi.json").status_code == 200
    public = client.get("/api/v1/public")
    assert public.status_code == 200
    assert len(public.json()["doctors"]) == 2
    assert client.get("/api/v1/state").status_code == 401
    assert client.post(
        "/api/v1/auth/login", json={"email": "admin@medikahusada.local", "password": "salah123"}
    ).status_code == 401


def test_role_scoped_state_and_password_is_never_serialized(client, auth):
    patient_state = client.get("/api/v1/state", headers=auth("pasien")).json()
    assert patient_state["session"]["userId"]
    assert len(patient_state["patients"]) == 1
    assert "password" not in str(patient_state).lower()

    admin_state = client.get("/api/v1/state", headers=auth("admin")).json()
    assert len(admin_state["patients"]) == 3
    assert {user["role"] for user in admin_state["users"]} >= {
        "admin", "nurse", "doctor", "pharmacist", "patient"
    }


def test_full_cross_role_workflow(client, auth):
    patient_headers = auth("pasien")
    patient_state = client.get("/api/v1/state", headers=patient_headers).json()
    doctor_id = patient_state["doctors"][0]["id"]
    appointment_day, appointment_time = next_practice_day(client, doctor_id)
    booking = client.post(
        "/api/v1/appointments",
        headers=patient_headers,
        json={
            "doctorId": doctor_id,
            "date": appointment_day,
            "time": appointment_time,
            "complaint": "Keluhan pengujian API",
            "notes": "",
            "insurance": "general",
        },
    )
    assert booking.status_code == 201, booking.text
    appointment_id = booking.json()["appointmentId"]

    admin_headers = auth("admin")
    verified = client.post(
        f"/api/v1/appointments/{appointment_id}/verify", headers=admin_headers
    )
    assert verified.status_code == 200, verified.text
    visit_id = next(
        item["id"]
        for item in verified.json()["state"]["visits"]
        if item["appointmentId"] == appointment_id
    )

    # Clinical workflow is only allowed on or after the visit date.
    with SessionLocal() as db:
        appointment = db.get(Appointment, appointment_id)
        appointment.date = date.today()
        db.commit()

    nursing = client.post(
        f"/api/v1/visits/{visit_id}/nursing",
        headers=auth("perawat"),
        json={
            "systolic": 120,
            "diastolic": 80,
            "temperature": 36.6,
            "weight": 65,
            "height": 170,
            "pulse": 75,
            "respiration": 18,
            "spo2": 98,
            "pain": 1,
            "complaint": "Keluhan pengujian API",
            "notes": "Stabil",
        },
    )
    assert nursing.status_code == 200, nursing.text

    doctor_headers = auth("fakih")
    assert client.post(f"/api/v1/visits/{visit_id}/start", headers=doctor_headers).status_code == 200
    doctor_state = client.get("/api/v1/state", headers=doctor_headers).json()
    medicine_id = doctor_state["medicines"][0]["id"]
    before = next(item["stock"] for item in doctor_state["medicines"] if item["id"] == medicine_id)
    examined = client.post(
        f"/api/v1/visits/{visit_id}/examination",
        headers=doctor_headers,
        json={
            "anamnesis": "Demam",
            "physical": "Kondisi umum baik",
            "diagnosis": "Diagnosis pengujian",
            "treatment": "Pemeriksaan",
            "treatmentFee": 15_000,
            "notes": "CATATAN INTERNAL",
            "items": [
                {
                    "medicineId": medicine_id,
                    "quantity": 3,
                    "dosage": "1 tablet",
                    "frequency": "2 kali sehari",
                    "duration": "3 hari",
                    "timing": "Sesudah makan",
                    "instruction": "Pengujian",
                }
            ],
        },
    )
    assert examined.status_code == 200, examined.text

    pharmacy_headers = auth("apoteker")
    for action, expected in (
        ("start", "PHARMACY_PROCESSING"),
        ("ready", "MEDICINE_READY"),
        ("handover", "WAITING_PAYMENT"),
    ):
        response = client.post(
            f"/api/v1/visits/{visit_id}/pharmacy/{action}", headers=pharmacy_headers
        )
        assert response.status_code == 200, response.text
        visit = next(item for item in response.json()["state"]["visits"] if item["id"] == visit_id)
        assert visit["status"] == expected

    paid = client.post(
        f"/api/v1/visits/{visit_id}/payment",
        headers=admin_headers,
        json={"method": "Tunai", "discount": 0},
    )
    assert paid.status_code == 200, paid.text
    completed = next(item for item in paid.json()["state"]["visits"] if item["id"] == visit_id)
    assert completed["status"] == "COMPLETED"
    assert completed["invoice"]["status"] == "PAID"

    duplicate = client.post(
        f"/api/v1/visits/{visit_id}/payment",
        headers=admin_headers,
        json={"method": "Tunai", "discount": 0},
    )
    assert duplicate.status_code == 409
    with SessionLocal() as db:
        visit = db.get(Visit, visit_id)
        assert visit.status == VisitStatus.COMPLETED
        assert db.scalar(select(Medicine.stock).where(Medicine.id == medicine_id)) == before - 3
        assert len(db.scalars(select(Payment).where(Payment.invoice_id == visit.invoice.id)).all()) == 1
        assert len(db.scalars(select(StockMovement).where(StockMovement.visit_id == visit_id)).all()) == 1


def test_authorization_and_validation(client, auth):
    state = client.get("/api/v1/state", headers=auth("admin")).json()
    if state["visits"]:
        visit_id = state["visits"][0]["id"]
        assert client.post(
            f"/api/v1/visits/{visit_id}/payment",
            headers=auth("siti"),
            json={"method": "Tunai", "discount": 0},
        ).status_code == 403
    invalid = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Pasien Uji",
            "nik": "123",
            "birthDate": "2035-01-01",
            "gender": "X",
            "address": "Alamat",
            "phone": "abc",
            "email": "invalid",
            "password": "Testing123!",
            "confirm": "berbeda123",
        },
    )
    assert invalid.status_code == 422


def test_admin_configuration_endpoints(client, auth):
    admin = auth("admin")
    created = client.post(
        "/api/v1/admin/users",
        headers=admin,
        json={
            "name": "Perawat API",
            "email": "perawat.api@example.com",
            "password": "Testing123!",
            "phone": "081299999999",
            "role": "nurse",
        },
    )
    assert created.status_code == 201, created.text
    user_id = next(
        item["id"] for item in created.json()["state"]["users"] if item["email"] == "perawat.api@example.com"
    )
    assert client.patch(
        f"/api/v1/admin/users/{user_id}", headers=admin, json={"active": False}
    ).status_code == 200

    medicine = client.post(
        "/api/v1/medicines",
        headers=admin,
        json={
            "name": "Obat API",
            "category": "Pengujian",
            "unit": "tablet",
            "price": 2_000,
            "minimum": 5,
            "initialStock": 10,
        },
    )
    assert medicine.status_code == 201, medicine.text
    item = next(value for value in medicine.json()["state"]["medicines"] if value["name"] == "Obat API")
    assert item["stock"] == 10
    assert client.patch(
        f"/api/v1/medicines/{item['id']}/stock",
        headers=admin,
        json={"delta": -11, "reason": "Tidak boleh"},
    ).status_code == 409

