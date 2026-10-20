# Audit PBO Medika Husada

Audit 21 Oktober 2026. Perubahan kode hanya berupa 22 baris komentar Bahasa Indonesia pada enam file Python. Tidak ada refactor, perubahan logic, UI, route, akun, workflow, maupun skema database. Status Git sebelum pengerjaan bersih.

## Ruang lingkup

README menunjuk `back/app` (FastAPI) dan `front` sebagai aplikasi utama. `clinic` dan `app.py` adalah aplikasi Flask lama. Temuan pada Flask tidak berarti implementasi yang sama digunakan oleh FastAPI.

Audit mencakup model, layanan, skema, serialisasi, keamanan, route, konfigurasi, entry point, seed, fixture, dan skrip pengujian pada 26 file Python proyek. `begitulah.py` memuat contoh ABC dan turunan peran, tetapi bukan bukti implementasi pada aplikasi utama. File tersebut tidak diimpor/dijalankan karena memanggil `init_db()` di tingkat modul.

## Pemetaan

| Pilar PBO | File | Class/Method | Lokasi | Penjelasan |
|---|---|---|---|---|
| Abstraksi | `clinic/services.py` | `PaymentProcessor.amounts` | Baris 228–233 | ABC dengan abstractmethod menentukan kontrak strategi pembayaran yang benar-benar dipakai BillingService. |
| Pewarisan | `clinic/services.py` | `GeneralPayment`, `BPJSPayment` | Baris 236–245 | Kedua strategi mewarisi PaymentProcessor dan mengimplementasikan amounts. |
| Enkapsulasi | `clinic/models.py` | `User.set_password`, `check_password` | Baris 77–85 | Validasi dan hashing melalui method; awalan underscore adalah konvensi internal, bukan pembatas akses mutlak. |
| Enkapsulasi | `clinic/models.py` | `Medicine.change_stock` | Baris 216–229 | Memvalidasi mutasi, mencegah stok negatif melalui update bersyarat, dan mencatat StockMovement. Dipakai route stok dan layanan farmasi. |
| Polimorfisme | `clinic/services.py` | `amounts`, `BillingService.invoice` | Baris 242–261 | Pemanggilan method yang sama memilih implementasi strategi umum atau BPJS; hasil pembagian biaya berbeda. Strategi juga digunakan BillingService.pay. |
| Abstraksi | `back/app/schemas.py` | `APIModel` | Baris 6–9 | Kontrak validasi input bersama melalui Pydantic. Abstraksi skema, bukan ABC domain pembayaran. |
| Pewarisan | `back/app/database.py` | `Base(DeclarativeBase)` | Baris 10–13 | Dasar pemetaan SQLAlchemy diwarisi model seperti User, Patient, dan Doctor. |
| Pewarisan | `back/app/schemas.py` | `LoginInput(APIModel)` | Baris 12–16 | Skema turunan memakai konfigurasi dan perilaku validasi induk. |
| Enkapsulasi | `back/app/models.py` | `User.set_password`, `check_password` | Baris 89–95 | Method membungkus hashing/verifikasi; password_hash tetap publik. |
| Enkapsulasi | `back/app/services.py` | `adjust_stock` | Baris 426–444 | Pembungkusan pada lapisan layanan: validasi, penguncian baris, dan pencatatan mutasi. Bukan enkapsulasi atribut yang ketat. |
| Polimorfisme | `back/app/services.py` | `create_invoice`, `pay_invoice` | Baris 242 dan 384 | Belum ideal pada domain bisnis: perhitungan umum/BPJS menggunakan percabangan, bukan objek dengan interface dan implementasi berbeda. Tidak diberi komentar seolah sudah menerapkan polimorfisme. |

Patient dan Doctor pada kedua aplikasi memakai relasi ke User, bukan mewarisi User. Relasi foreign key tidak dihitung sebagai pewarisan.

## Batas penerapan

Keempat pilar ditemukan pada Flask lama. Pada aplikasi utama, pewarisan framework dan abstraksi skema sudah ada; enkapsulasi masih parsial karena atribut model publik dan perubahan stok juga dilakukan di process_pharmacy. Polimorfisme strategi bisnis belum ditemukan. Abstraksi domain berbasis ABC belum tersedia di backend utama.

Tidak dibuat class formalitas atau strategi baru untuk mengganti perhitungan yang berjalan. Penguatan pilar tersebut memerlukan perubahan desain/call site dan verifikasi workflow di luar penandaan ini; sesuai arahan pengguna, bagian yang belum ideal cukup dilaporkan.

## Validasi

- Seluruh 26 file Python lolos compile statis tanpa menjalankan modul.
- AST keenam file Python yang diubah identik dengan versi Git HEAD: perubahan hanya komentar.
- `git diff --check` lulus; diff diperiksa dan hanya memuat penambahan komentar. Dokumen ini merupakan satu file tambahan.
- Dependensi backend yang belum tersedia dipasang ke `.venv` dari `back/requirements.txt`; requirements tidak diubah.
- Tes Flask: `.venv\Scripts\python -m pytest tests -q`. Sebelum dan sesudah penandaan sama-sama menghasilkan **2 failed, 19 errors**. Dua kegagalan workflow menghasilkan NoResultFound: tes login sebagai admin, sedangkan seed Flask saat ini menyediakan komang sebagai admin. Error fixture berikutnya adalah indeks `uq_user_sip` duplikat; create_app menambahkan objek Index ke metadata bersama setiap kali dipanggil.
- Tes FastAPI dari folder `back`: `..\.venv\Scripts\python -m pytest tests -q --tb=short`, menghasilkan **4 passed, 1 failed**. Tes pembayaran tunai tidak mengirim cashReceived sehingga endpoint menolak dengan HTTP 409. Tes login, pembatasan peran, dan validasi autentikasi lulus. Ada satu peringatan deprecation Starlette terkait httpx.
- Pembanding FastAPI dijalankan pada salinan sementara seluruh file backend dari Git HEAD, dengan interpreter/dependensi yang sama. Hasilnya juga **4 passed, 1 failed** pada pembayaran tunai yang sama; kegagalan tersebut sudah ada pada kode awal.
- Startup proses Flask melalui entry module `app`, FastAPI melalui Uvicorn `app.main:app`, dan frontend melalui http.server berhasil. HTTP `/login` Flask = 200 dengan input password dan CSRF, `/health` FastAPI = 200/database connected, `/index.html` frontend = 200. Ini pemeriksaan HTTP, bukan uji visual browser.
- Semua startup menggunakan SQLite sementara di direktori temporer dengan auto-seed dimatikan. Fixture tes menggunakan database temporer sendiri. Tidak menjalankan seed/reset pada database operasional dan tidak menghubungkan pengujian ke MySQL operasional. Proses startup dihentikan setelah pemeriksaan.

Suite tes belum hijau; masalah di atas dilaporkan tanpa mengubah logic, seed, atau tes demi audit komentar. Startup MySQL operasional dan pengujian browser penuh tidak dilakukan. Tidak ada commit/push.

## File yang diubah

- `clinic/services.py` — komentar abstraksi, pewarisan, dan polimorfisme.
- `clinic/models.py` — komentar enkapsulasi password dan stok.
- `back/app/database.py` — komentar pewarisan ORM.
- `back/app/models.py` — komentar pembungkusan hashing.
- `back/app/schemas.py` — komentar abstraksi skema dan pewarisan.
- `back/app/services.py` — komentar pembungkusan validasi/mutasi stok.
- `PBO_AUDIT.md` — laporan audit dan keterbatasan validasi.
