# Medika Husada FastAPI Backend

Backend REST untuk frontend `../front`, menggunakan FastAPI, SQLAlchemy 2, JWT, dan MySQL `project_pbo`.

## Menjalankan

```powershell
cd C:\Users\USER\OneDrive\Documents\projek_pbo-main\back
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python seed.py
python run.py
```

API tersedia di `http://127.0.0.1:8000`, dokumentasi interaktif di `http://127.0.0.1:8000/docs`, dan health check di `http://127.0.0.1:8000/health`.

Konfigurasi bawaan cocok untuk Laragon MySQL lokal (`root` tanpa password). Bila MySQL Anda memakai password, ubah `DATABASE_URL` dalam `.env`, misalnya:

```text
DATABASE_URL=mysql+pymysql://root:PASSWORD@127.0.0.1:3306/project_pbo?charset=utf8mb4
```

Jangan gunakan `JWT_SECRET` contoh untuk production.

## Cakupan API

- Registrasi, login JWT, current user, dan state berbasis peran.
- Booking, slot jadwal, reschedule, verifikasi, penolakan, pembatalan, dan antrean.
- Pemeriksaan perawat dan dokter, resep, rujukan, serta pembatasan akses rekam medis.
- Workflow farmasi atomik, validasi kedaluwarsa, pengurangan stok, dan audit stok.
- Invoice, pembayaran umum/BPJS, pencegahan pembayaran ganda, dan laporan CSV.
- Pengelolaan pengguna, dokter, jadwal, obat, profil pasien, dan notifikasi.
- OpenAPI otomatis melalui `/docs` dan `/openapi.json`.

Seed hanya berjalan saat tabel pengguna kosong sehingga data operasional yang sudah ada tidak ditimpa.

