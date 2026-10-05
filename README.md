# Medika Husada — Sistem Informasi Klinik

Implementasi utama sekarang dipisahkan menjadi frontend statis dan backend REST:

```text
front/   Iconic Hospital UI, HTML/CSS/JavaScript
back/    FastAPI, SQLAlchemy 2, JWT, dan MySQL
```

Versi utama tidak menggunakan Flask. Folder `front/` disajikan sebagai file statis dan seluruh API berada di `back/` menggunakan FastAPI.

Data aplikasi utama tersimpan pada database MySQL `project_pbo`. Frontend berkomunikasi dengan backend melalui `http://127.0.0.1:8000/api/v1`.

## Menjalankan aplikasi

Terminal pertama:

```powershell
cd C:\Users\USER\OneDrive\Documents\projek_pbo-main\back
python -m pip install -r requirements.txt
python seed.py
python run.py
```

Terminal kedua:

```powershell
cd C:\Users\USER\OneDrive\Documents\projek_pbo-main\front
python -m http.server 5173
```

Buka:

- Aplikasi: `http://127.0.0.1:5173`
- Dokumentasi API: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

Konfigurasi MySQL bawaan adalah `root` tanpa password pada `127.0.0.1:3306`. Salin `back/.env.example` menjadi `back/.env` dan ubah `DATABASE_URL` bila konfigurasi MySQL berbeda.

## Akun demo

| Peran | Email | Password |
|---|---|---|
| Admin | `admin@medikahusada.local` | `Admin123!` |
| Perawat | `perawat@medikahusada.local` | `Perawat123!` |
| Dokter | `fakih@medikahusada.local` | `Dokter123!` |
| Apoteker | `apoteker@medikahusada.local` | `Apoteker123!` |
| Pasien | `pasien@medikahusada.local` | `Pasien123!` |

Seed bersifat idempoten: seed dilewati bila database sudah memiliki pengguna.

## Pengujian

```powershell
python -m pytest back\tests -q
python -m pytest tests -q
```

Smoke test browser lintas frontend/backend tersedia di `back/tests/browser_smoke.py` dan membutuhkan kedua server sedang berjalan serta paket Playwright.

Detail tambahan tersedia di [panduan backend](back/README.md) dan [panduan frontend](front/README.md).

