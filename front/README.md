# Medika Husada Frontend

Frontend yang me-reuse **Iconic Hospital Bootstrap template** dari `html-versiokn/html-versiokn/dist/hospital` dan terhubung ke FastAPI/MySQL di `../back`.

## Menjalankan

Jalankan backend terlebih dahulu pada port `8000`, lalu frontend (tidak memerlukan Node.js atau proses build):

```powershell
cd front
python -m http.server 5173
```

Buka `http://127.0.0.1:5173`.

## Akun demo

| Peran | Email | Password |
|---|---|---|
| Admin | `admin@medikahusada.local` | `Admin123!` |
| Perawat | `perawat@medikahusada.local` | `Perawat123!` |
| Dokter | `fakih@medikahusada.local` | `Dokter123!` |
| Apoteker | `apoteker@medikahusada.local` | `Apoteker123!` |
| Pasien | `pasien@medikahusada.local` | `Pasien123!` |

Menu **Mode Demo** di kanan atas login ulang ke akun demo pada backend. Ini memudahkan pengujian satu alur kunjungan dari admin, perawat, dokter, apoteker, lalu kembali ke admin untuk pembayaran.

## Cakupan

- Landing page, login, dan registrasi pasien.
- Dashboard berbasis peran.
- Booking, slot jadwal, verifikasi, reschedule, penolakan, dan pembatalan.
- Antrean serta pemeriksaan perawat.
- Pemeriksaan dokter, resep, dan rujukan.
- Proses farmasi dan pengurangan stok.
- Invoice, pembayaran, struk, dan laporan CSV.
- Manajemen pasien, dokter, pengguna, obat, profil, dan notifikasi.
- Layout desktop/mobile dan tampilan cetak.

Seluruh data operasional tersimpan di MySQL `project_pbo`. Token login disimpan pada `sessionStorage` dan hilang ketika sesi tab browser ditutup. Tombol **Muat ulang data** mengambil state terbaru dari server.

## Struktur

```text
front/
├── index.html
└── assets/
    ├── css/app.css
    ├── js/data.js
    ├── js/store.js
    ├── js/views.js
    ├── js/app.js
    ├── fonts/
    └── hospital/       # aset terpilih dari template sumber
```

`assets/js/api-store.js` adalah adapter FastAPI. `store.js` dan `data.js` tetap dipertahankan untuk smoke test frontend terisolasi; halaman utama menggunakan API dan bukan `localStorage`.

Alamat backend dapat diubah dalam `assets/js/config.js`.
