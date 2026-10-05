from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginInput(APIModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=8, max_length=128)


class RegisterInput(APIModel):
    name: str = Field(min_length=1, max_length=160)
    nik: str = Field(pattern=r"^\d{16}$")
    birthDate: date
    gender: str
    address: str = Field(min_length=1, max_length=4000)
    phone: str = Field(min_length=8, max_length=24)
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    confirm: str = Field(min_length=8, max_length=128)
    bpjs: str = Field(default="", max_length=13)

    @model_validator(mode="after")
    def validate_registration(self):
        if self.password != self.confirm:
            raise ValueError("Konfirmasi password tidak cocok.")
        if self.birthDate > date.today() or self.birthDate.year < 1900:
            raise ValueError("Tanggal lahir tidak valid.")
        if self.gender not in ("Laki-laki", "Perempuan"):
            raise ValueError("Pilih jenis kelamin.")
        if self.bpjs and (len(self.bpjs) != 13 or not self.bpjs.isdigit()):
            raise ValueError("Nomor BPJS harus 13 digit.")
        return self


class AppointmentInput(APIModel):
    patientId: int | None = None
    doctorId: int
    date: date
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    complaint: str = Field(min_length=1, max_length=4000)
    notes: str = Field(default="", max_length=4000)
    insurance: str = Field(default="general", pattern=r"^(general|bpjs)$")


class NursingInput(APIModel):
    systolic: int = Field(ge=40, le=300)
    diastolic: int = Field(ge=20, le=200)
    temperature: float = Field(ge=30, le=45)
    weight: float = Field(gt=0, le=500)
    height: float = Field(ge=30, le=250)
    pulse: int = Field(ge=20, le=250)
    respiration: int = Field(ge=1, le=100)
    spo2: int = Field(ge=1, le=100)
    pain: int = Field(ge=0, le=10)
    complaint: str = Field(min_length=1, max_length=4000)
    notes: str = Field(default="", max_length=4000)


class PrescriptionItemInput(APIModel):
    medicineId: int
    quantity: int = Field(ge=1, le=10_000)
    dosage: str = Field(min_length=1, max_length=80)
    frequency: str = Field(min_length=1, max_length=80)
    duration: str = Field(min_length=1, max_length=80)
    timing: str = Field(min_length=1, max_length=80)
    instruction: str = Field(default="", max_length=300)


class ExaminationInput(APIModel):
    anamnesis: str = Field(min_length=1, max_length=4000)
    physical: str = Field(min_length=1, max_length=4000)
    assessment: str = Field(default="", max_length=4000)
    diagnosis: str = Field(min_length=1, max_length=4000)
    secondary: str = Field(default="", max_length=4000)
    icd10: str = Field(default="", max_length=40)
    treatment: str = Field(default="", max_length=4000)
    treatmentFee: int = Field(default=0, ge=0, le=100_000_000)
    notes: str = Field(default="", max_length=4000)
    recommendation: str = Field(default="", max_length=4000)
    followup: str = Field(default="", max_length=4000)
    laboratory: str = Field(default="", max_length=4000)
    items: list[PrescriptionItemInput] = Field(default_factory=list, max_length=50)

    @field_validator("items")
    @classmethod
    def unique_medicines(cls, value):
        ids = [item.medicineId for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Obat duplikat. Gabungkan jumlahnya.")
        return value


class ReferralInput(APIModel):
    hospital: str = Field(min_length=1, max_length=160)
    specialist: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=4000)
    notes: str = Field(default="", max_length=4000)


class PaymentInput(APIModel):
    method: str = Field(default="Tunai", max_length=24)
    discount: int = Field(default=0, ge=0)


class StockInput(APIModel):
    delta: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(min_length=1, max_length=200)


class ProfileInput(APIModel):
    name: str = Field(min_length=1, max_length=160)
    nik: str = Field(pattern=r"^\d{16}$")
    birthDate: date
    gender: str
    phone: str = Field(min_length=8, max_length=24)
    bpjs: str = Field(default="", max_length=13)
    address: str = Field(min_length=1, max_length=4000)
    allergies: str = Field(default="", max_length=4000)
    history: str = Field(default="", max_length=4000)
    surgery: str = Field(default="", max_length=4000)
    medication: str = Field(default="", max_length=4000)
    emergency: str = Field(default="", max_length=200)


class UserActiveInput(APIModel):
    active: bool


class StaffInput(APIModel):
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    phone: str = Field(default="", max_length=24)
    role: str = Field(pattern=r"^(admin|nurse|pharmacist)$")


class DoctorInput(APIModel):
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=160)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    phone: str = Field(default="", max_length=24)
    specialty: str = Field(min_length=1, max_length=160)
    fee: int = Field(ge=0, le=100_000_000)
    active: bool = True


class ScheduleInput(APIModel):
    weekday: int = Field(ge=0, le=6)
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")
    interval: int = Field(ge=5, le=180)
    quota: int = Field(ge=1, le=100)


class MedicineInput(APIModel):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=32)
    price: int = Field(ge=0, le=100_000_000)
    minimum: int = Field(ge=0, le=1_000_000)
    expiry: date | None = None
    initialStock: int = Field(default=0, ge=0, le=1_000_000)

