# Panduan 4 Pilar OOP/PBO — Medika Husada

Dokumen ini adalah bahan belajar dan bahan presentasi.

Semua contoh diambil dari source project Medika Husada.

Tidak ada class atau method baru yang dibuat untuk melengkapi dokumen ini.

> **Tanggal audit:** 28 Oktober 2026
>
> **Catatan:** nomor baris mengikuti source pada saat audit. Nomor dapat bergeser jika file diubah kemudian.

## Daftar Isi

1. [Source yang dibaca](#source-yang-dibaca)
2. [Apa itu OOP](#apa-itu-oop)
3. [Class, object, attribute, dan method](#class-object-attribute-dan-method)
4. [Empat pilar OOP](#empat-pilar-oop)
5. [Pemetaan ke role Medika Husada](#pemetaan-ke-role-medika-husada)
6. [Tabel bukti source](#tabel-bukti-source)
7. [File yang harus dibuka saat presentasi](#file-yang-harus-dibuka-saat-presentasi)
8. [Jawaban singkat saat dosen bertanya](#jawaban-singkat-saat-dosen-bertanya)
9. [Cheat sheet presentasi](#cheat-sheet-presentasi)
10. [Kesimpulan audit](#kesimpulan-audit)

---

# Source yang Dibaca

Source utama yang diaudit:

| File | Yang diperiksa |
|---|---|
| `app.py` | Titik masuk aplikasi Flask. |
| `clinic/__init__.py` | Pembuatan aplikasi, database, login manager, dan blueprint. |
| `clinic/models.py` | Class data seperti `User`, `Doctor`, `Patient`, `Medicine`, dan `Payment`. |
| `clinic/services.py` | Aturan janji temu, pemeriksaan, farmasi, dan pembayaran. |
| `clinic/routes.py` | Hubungan tombol/HTTP request dengan service dan pembatasan role. |
| `seed.py` | Object contoh seperti Komang, Gea, Bintang, Fatur, Fakih, Alia, dan pasien. |
| `begitulah.py` | Contoh PBO terpisah. File ini tidak diimpor oleh aplikasi utama, jadi tidak dipakai sebagai bukti utama. |
| `back/app/models.py` | Model pada backend API terpisah. |
| `back/app/services.py` | Service pada backend API terpisah. |
| `back/app/schemas.py` | Class validasi input pada backend API terpisah. |
| `back/app/database.py` | Class dasar database pada backend API terpisah. |
| `back/app/main.py` | Route API dan pembatasan role pada backend API terpisah. |

## Aplikasi Mana yang Menjadi Fokus?

`app.py` menjalankan aplikasi dari package `clinic`:

```python
from clinic import create_app

app = create_app()
```

Karena itu, bukti utama pada panduan ini berasal dari folder `clinic`.

Folder `back/app` adalah implementasi API lain di repository yang sama.

Folder tersebut sudah dibaca sebagai pembanding, tetapi tidak dicampur dengan bukti aplikasi Flask.

---

# Apa itu OOP?

OOP adalah singkatan dari **Object-Oriented Programming**.

Dalam Bahasa Indonesia disebut **Pemrograman Berorientasi Objek (PBO)**.

Gampangnya, OOP menyusun program seperti dunia nyata.

Di klinik ada:

- pengguna;
- pasien;
- dokter;
- obat;
- janji temu;
- kunjungan;
- resep; dan
- pembayaran.

Di dalam program, hal-hal tersebut dibuat menjadi class dan object.

OOP cocok untuk Medika Husada karena setiap bagian klinik punya data dan tugas yang berbeda.

Contohnya:

- pasien membuat janji;
- admin memverifikasi;
- perawat mengisi pemeriksaan awal;
- dokter membuat diagnosis;
- apoteker menyiapkan obat; dan
- kasir memproses pembayaran.

---

# Class, Object, Attribute, dan Method

## Class = Cetakan

Class adalah cetakan.

Class menjelaskan data dan fungsi yang dimiliki suatu jenis benda atau orang.

Contoh class yang ada di `clinic/models.py`:

- `User`;
- `Patient`;
- `Doctor`;
- `Medicine`;
- `Appointment`;
- `Visit`;
- `Prescription`;
- `Invoice`; dan
- `Payment`.

## Object = Hasil Nyata dari Cetakan

Object adalah data nyata yang dibuat dari class.

Contoh:

```text
Class Doctor
├── object dr. Muhammad Fakih Nabal
└── object dr. Alia Fransiska Dewi Arum Trilestari
```

Kedua dokter tersebut memakai class `Doctor` yang sama.

Tetapi data keduanya berbeda.

Fakih adalah Dokter Umum.

Alia adalah dokter Obstetri dan Ginekologi.

**Bukti source:**

- Class `Doctor`: `clinic/models.py`, baris 109–114.
- Object Fakih dan Alia: `seed.py`, baris 15–16.
- Spesialisasi dokter: `seed.py`, baris 30–34.

## Attribute = Data Milik Object

Attribute adalah data yang dimiliki object.

Contoh attribute pada `Doctor`:

- `specialty` untuk spesialisasi;
- `fee` untuk tarif; dan
- `schedules` untuk jadwal.

Contoh attribute pada `User`:

- `email`;
- `name`;
- `role`;
- `phone`; dan
- `active`.

## Method = Fungsi Milik Class

Method adalah fungsi yang dimiliki class.

Contoh:

- `User.set_password()` untuk menyimpan password dengan aman;
- `User.check_password()` untuk memeriksa password; dan
- `Medicine.change_stock()` untuk mengubah stok dengan aturan tertentu.

---

# Empat Pilar OOP

### Abstraksi

**Apa itu?**

Abstraksi artinya kita memakai fungsi penting tanpa harus tahu semua proses rumit di belakangnya.

**Gampangnya**

Bayangkan mesin ATM.

Kita cukup menekan tombol tarik tunai.

Kita tidak perlu tahu cara mesin memeriksa saldo dan menghitung uang.

**Di Medika Husada**

Ada dua contoh yang kuat.

Pertama, `PaymentProcessor` memberi satu aturan sederhana:

```python
amounts(total)
```

Pemakai cukup tahu bahwa method tersebut menghitung:

- jumlah yang ditanggung; dan
- jumlah yang dibayar pasien.

Cara menghitungnya disembunyikan di class General atau BPJS.

Kedua, route farmasi cukup memanggil:

```python
PharmacyService.process(v, action, current_user)
```

Route tidak perlu menulis ulang seluruh proses resep, stok, dan perubahan status.

**Bukti source code**

File:

`clinic/services.py`

Class:

`PaymentProcessor`

Method:

`amounts()`

Baris:

`231–248`

Bukti tambahan:

- `PharmacyService.process()`: `clinic/services.py`, baris 203–228.
- Route yang memanggilnya: `clinic/routes.py`, baris 401–405.

Potongan kode:

```python
class PaymentProcessor(ABC):
    @abstractmethod
    def amounts(self, total):
        """Mengembalikan tanggungan dan jumlah pasien."""
```

**Kenapa ini termasuk pilar tersebut?**

Class ini hanya memberi tahu fungsi yang harus tersedia.

Class ini tidak menuliskan satu cara hitung untuk semua pembayaran.

Detail perhitungan diberikan kepada class lain.

Itulah abstraksi: bagian penting terlihat, detail rumit disembunyikan.

**Kenapa dipakai?**

Supaya cara memakai pembayaran tetap sederhana.

Service lain cukup memanggil `amounts(total)`.

**Kalau tidak dipakai?**

Detail perhitungan akan tersebar di banyak tempat.

Kode menjadi lebih panjang dan sulit dibaca.

**Kesimpulan**

> Abstraksi = pakai fungsi pentingnya, detail rumitnya disembunyikan.

---

### Enkapsulasi

**Apa itu?**

Enkapsulasi artinya data penting dijaga supaya tidak diubah sembarangan.

Perubahan dilakukan melalui method yang sudah mempunyai aturan.

**Gampangnya**

Stok obat seperti lemari obat.

Tidak semua orang boleh mengambil obat seenaknya.

Jumlah harus diperiksa dan pengambilan harus dicatat.

**Di Medika Husada**

Stok obat disimpan sebagai `_stock` pada class `Medicine`.

Stok dibaca melalui property `stock`.

Stok diubah melalui `change_stock()`.

Method tersebut:

- menolak jumlah kosong;
- mewajibkan alasan;
- mencegah stok menjadi negatif;
- mencatat siapa yang mengubah; dan
- membuat catatan `StockMovement`.

Password juga memakai pola yang sama.

Password tidak ditulis langsung.

Password disimpan lewat `User.set_password()` dan diperiksa lewat `User.check_password()`.

**Bukti source code**

File:

`clinic/models.py`

Class:

`Medicine`

Method:

`change_stock()`

Baris:

`208–231`

Bukti tambahan:

- `User._password_hash`: `clinic/models.py`, baris 65–76.
- `User.set_password()` dan `check_password()`: `clinic/models.py`, baris 78–86.
- Pemakaian stok saat resep siap: `clinic/services.py`, baris 218–223.

Potongan kode:

```python
if not delta or not reason.strip():
    raise ValueError('Jumlah dan alasan stok wajib diisi.')

if result.rowcount != 1:
    raise ValueError(f'Stok {self.name} tidak cukup.')
```

**Kenapa ini termasuk pilar tersebut?**

Data stok tidak hanya berupa angka bebas.

Aturan perubahan stok diletakkan bersama method `change_stock()`.

Halaman atau service tidak perlu membuat aturan stok sendiri-sendiri.

**Kenapa dipakai?**

Supaya stok tetap benar.

Setiap perubahan juga mempunyai jejak.

**Kalau tidak dipakai?**

Stok dapat menjadi minus.

Alasan perubahan dapat hilang.

Kita juga sulit mengetahui siapa yang mengubahnya.

**Catatan jujur**

Python tidak mempunyai private mutlak seperti beberapa bahasa lain.

Awalan garis bawah pada `_stock` dan `_password_hash` adalah tanda bahwa data tersebut sebaiknya tidak diubah langsung.

**Kesimpulan**

> Enkapsulasi = menjaga data supaya tidak diubah sembarangan.

---

### Pewarisan / Inheritance

**Apa itu?**

Inheritance berarti pewarisan.

Class anak menerima aturan dasar dari class induk.

**Gampangnya**

Bayangkan hubungan keluarga.

Anak menerima ciri dasar dari orang tuanya.

Tetapi setiap anak tetap dapat mempunyai perilaku yang berbeda.

**Di Medika Husada**

Inheritance domain yang paling jelas ada pada pembayaran.

`PaymentProcessor` adalah class induk.

`GeneralPayment` dan `BPJSPayment` adalah class anak.

```text
PaymentProcessor
├── GeneralPayment
└── BPJSPayment
```

Kedua class anak wajib mempunyai method `amounts(total)`.

**Bukti source code**

File:

`clinic/services.py`

Class induk:

`PaymentProcessor`

Class anak:

- `GeneralPayment`
- `BPJSPayment`

Method:

`amounts()`

Baris:

`231–248`

Potongan kode:

```python
class GeneralPayment(PaymentProcessor):
    def amounts(self, total):
        return 0, total

class BPJSPayment(PaymentProcessor):
    def amounts(self, total):
        return total, 0
```

**Kenapa ini termasuk pilar tersebut?**

Nama class induk ditulis di dalam kurung.

`GeneralPayment(PaymentProcessor)` berarti General adalah anak dari `PaymentProcessor`.

`BPJSPayment(PaymentProcessor)` berarti BPJS juga anak dari `PaymentProcessor`.

**Kenapa dipakai?**

Supaya semua strategi pembayaran mengikuti aturan method yang sama.

Aturan dasar tidak perlu dibuat dengan nama berbeda-beda.

**Kalau tidak dipakai?**

Kontrak yang sama dapat ditulis berulang.

Nama method dapat berbeda dan membingungkan.

**Apakah Doctor, Nurse, dan Admin mewarisi User?**

Tidak pada source aplikasi ini.

Source tidak menulis `class Doctor(User)`.

`Doctor` dan `Patient` adalah model yang terhubung ke `User` melalui `user_id`.

Buktinya:

- relasi pada `User`: `clinic/models.py`, baris 75–76;
- `Patient.user_id`: `clinic/models.py`, baris 89–106; dan
- `Doctor.user_id`: `clinic/models.py`, baris 109–114.

Admin, Perawat, Apoteker, dan Kasir juga bukan class terpisah.

Mereka adalah object `User` dengan nilai `role` yang berbeda.

**Inheritance framework**

Ada juga inheritance dari framework:

```python
class User(UserMixin, db.Model):
```

Ini ada pada `clinic/models.py`, baris 65.

`UserMixin` memberi fungsi login dasar.

`db.Model` memberi fungsi model database.

**Kesimpulan**

> Inheritance = class anak menerima aturan dasar dari class induk.

---

### Polimorfisme / Polymorphism

**Apa itu?**

Polimorfisme berarti nama method yang sama dapat memberi hasil berbeda.

Hasilnya tergantung object yang menjalankan.

**Gampangnya**

Kita memberi perintah “bersuara”.

Kucing menjawab “meong”.

Anjing menjawab “guk”.

Perintahnya sama, hasilnya berbeda.

**Di Medika Husada**

Method yang dipakai adalah:

```python
amounts(total)
```

Jika object-nya `GeneralPayment`:

- tanggungan = Rp0;
- pasien membayar seluruh total.

Jika object-nya `BPJSPayment`:

- tanggungan = seluruh total;
- pasien membayar Rp0.

`BillingService` memilih object yang sesuai lalu memanggil nama method yang sama.

**Bukti source code**

File:

`clinic/services.py`

Class:

- `GeneralPayment`
- `BPJSPayment`
- `BillingService`

Method:

- `amounts()`
- `invoice()`
- `pay()`

Baris:

- implementasi `amounts()`: `241–248`;
- pemilihan object dan pemanggilan method: `251–265`;
- pemakaian ulang saat pembayaran: `269–294`.

Potongan kode:

```python
processor = (
    BPJSPayment()
    if v.appointment.insurance
    else GeneralPayment()
)
coverage, payable = processor.amounts(total)
```

**Kenapa ini termasuk pilar tersebut?**

Variabel `processor` dapat berisi object General atau BPJS.

Keduanya dipanggil dengan method yang sama: `amounts(total)`.

Hasilnya berbeda sesuai object yang dipilih.

**Kenapa dipakai?**

`BillingService` cukup memakai satu nama method.

Cara hitung diserahkan kepada object pembayaran.

**Kalau tidak dipakai?**

Percabangan `if/else` dapat semakin panjang.

Setiap cara hitung baru harus ditambahkan langsung ke service.

**Catatan jujur**

Tunai, Transfer, QRIS, dan Debit belum memakai class polymorphic terpisah.

Pada `BillingService.pay()`, metode tersebut masih berupa teks dan percabangan.

Buktinya ada di `clinic/services.py`, baris 274–287.

Tidak ada class `CashPayment`, `TransferPayment`, atau `QRISPayment` pada aplikasi ini.

Jadi contoh polymorphism yang benar-benar ada adalah General dan BPJS.

**Kesimpulan**

> Polimorfisme = nama aksi sama, tetapi hasilnya dapat berbeda.

---

# Pemetaan ke Role Medika Husada

Role didefinisikan pada `clinic/models.py`, baris 9–15.

Akun contoh dibuat pada `seed.py`, baris 8–19.

Role tidak dipaksa mempunyai semua pilar.

Yang dijelaskan hanya pilar yang memang berkaitan.

## Admin — Komang

Komang adalah object `User` dengan `Role.ADMIN`.

**Bukti akun:** `seed.py`, baris 9.

Tugas yang terlihat di source:

- memverifikasi janji temu;
- mengatur antrean;
- mengelola pasien;
- mengelola pengguna; dan
- melihat laporan.

**Bukti proses verifikasi:**

- route: `clinic/routes.py`, baris 235–241;
- service: `AppointmentService.verify()`, `clinic/services.py`, baris 143–155.

**Pilar yang berkaitan:**

- Abstraksi: route menyerahkan proses kepada `AppointmentService`.
- Enkapsulasi: status appointment dan visit tidak diubah tanpa pemeriksaan.

## Perawat — Gea

Gea adalah object `User` dengan `Role.NURSE`.

**Bukti akun:** `seed.py`, baris 10.

Gea mengisi pemeriksaan awal seperti:

- tekanan darah;
- suhu;
- berat badan;
- tinggi badan;
- nadi; dan
- keluhan.

**Bukti source:**

- model data: `NursingAssessment`, `clinic/models.py`, baris 172–188;
- route: `clinic/routes.py`, baris 374–378;
- service: `WorkflowService.nurse()`, `clinic/services.py`, baris 168–179.

**Pilar yang berkaitan:**

- Abstraksi: route cukup memanggil `WorkflowService.nurse()`.
- Enkapsulasi: nilai pemeriksaan divalidasi dan status kunjungan dipindahkan lewat service.

## Dokter Umum — dr. Muhammad Fakih Nabal

Fakih adalah object `User` dengan role dokter dan mempunyai profil `Doctor`.

Fakih mempunyai spesialisasi `Dokter Umum`.

**Bukti akun dan spesialisasi:**

- akun: `seed.py`, baris 15;
- spesialisasi dan jadwal: `seed.py`, baris 30–34.

**Bukti proses pemeriksaan:**

- route: `clinic/routes.py`, baris 381–398;
- service: `WorkflowService.examine()`, `clinic/services.py`, baris 181–200;
- model hasil pemeriksaan: `DoctorExamination`, `clinic/models.py`, baris 191–205.

**Pilar yang berkaitan:**

- Class dan object: Fakih adalah satu object dokter.
- Abstraksi: proses pemeriksaan diserahkan kepada `WorkflowService`.

## Dokter Kandungan — dr. Alia Fransiska Dewi Arum Trilestari

Alia adalah object dokter yang berbeda dari Fakih.

Alia mempunyai spesialisasi `Obstetri dan Ginekologi`.

**Bukti akun dan spesialisasi:**

- akun: `seed.py`, baris 16;
- spesialisasi dan jadwal: `seed.py`, baris 30–34.

**Pilar yang berkaitan:**

- Class dan object: Alia dan Fakih memakai class `Doctor` yang sama, tetapi datanya berbeda.
- Abstraksi: pemeriksaan memakai service yang sama.

## Apoteker — Bintang

Bintang adalah object `User` dengan `Role.PHARMACIST`.

**Bukti akun:** `seed.py`, baris 11.

Bintang menerima resep, mengecek obat, menyiapkan obat, dan menyerahkan obat.

**Bukti source:**

- route: `clinic/routes.py`, baris 401–405;
- service: `PharmacyService.process()`, `clinic/services.py`, baris 203–228;
- perubahan stok: `Medicine.change_stock()`, `clinic/models.py`, baris 222–231.

**Pilar yang berkaitan:**

- Abstraksi: route memanggil service farmasi.
- Enkapsulasi: stok dikurangi melalui `change_stock()`.

## Kasir — Fatur

Fatur adalah object `User` dengan `Role.CASHIER`.

**Bukti akun:** `seed.py`, baris 12.

Kasir melihat tagihan dan memproses pembayaran.

**Bukti source:**

- route: `clinic/routes.py`, baris 408–422;
- service: `BillingService`, `clinic/services.py`, baris 251–294;
- model tagihan: `Invoice`, `clinic/models.py`, baris 314–324;
- model pembayaran: `Payment`, `clinic/models.py`, baris 336–343.

**Pilar yang berkaitan:**

- Abstraksi: kasir memakai `BillingService.pay()`.
- Inheritance: strategi General dan BPJS mewarisi `PaymentProcessor`.
- Polimorfisme: `amounts()` memberi hasil berbeda.

## Pasien

Contoh pasien pada seed adalah Budi Santoso, Ratna Permata, dan Siti Aminah.

**Bukti akun:** `seed.py`, baris 17–19.

Pasien dapat membuat janji dan melihat data miliknya sendiri.

**Bukti source:**

- pembuatan janji: `AppointmentService.book()`, `clinic/services.py`, baris 111–134;
- route booking: `clinic/routes.py`, baris 192–199;
- pembatasan data milik sendiri: `clinic/routes.py`, baris 44–70;
- model pasien: `Patient`, `clinic/models.py`, baris 89–106.

**Pilar yang berkaitan:**

- Abstraksi: pasien cukup mengisi form; service mengurus jadwal dan validasi.
- Enkapsulasi: route membatasi pasien agar hanya melihat data miliknya.
- Polimorfisme: pasien General dan BPJS mendapat hasil tagihan berbeda.

---

# Tabel Bukti Source

| Pilar | File | Class | Method | Baris | Bukti sederhana |
|---|---|---|---|---:|---|
| Abstraksi | `clinic/services.py` | `PaymentProcessor` | `amounts()` | 231–248 | Menyediakan aturan sederhana tanpa satu rumus tetap. |
| Abstraksi | `clinic/services.py` | `PharmacyService` | `process()` | 203–228 | Route tidak perlu mengetahui seluruh proses farmasi. |
| Enkapsulasi | `clinic/models.py` | `Medicine` | `change_stock()` | 208–231 | Stok dijaga dengan validasi dan pencatatan. |
| Enkapsulasi | `clinic/models.py` | `User` | `set_password()`, `check_password()` | 65–86 | Password disimpan dan diperiksa melalui method. |
| Pewarisan | `clinic/services.py` | `GeneralPayment` | `amounts()` | 239–242 | Mewarisi `PaymentProcessor`. |
| Pewarisan | `clinic/services.py` | `BPJSPayment` | `amounts()` | 245–248 | Mewarisi `PaymentProcessor`. |
| Polimorfisme | `clinic/services.py` | `BillingService` | `invoice()`, `pay()` | 251–294 | Memanggil `amounts()` pada object General atau BPJS. |

---

# File yang Harus Dibuka Saat Presentasi

## Abstraksi

Buka:

`clinic/services.py`

Lihat:

- baris 231–248;
- class `PaymentProcessor`;
- method `amounts()`.

Yang saya jelaskan:

> “PaymentProcessor hanya memberi aturan bahwa setiap strategi pembayaran harus punya `amounts()`. Detail cara menghitung diserahkan kepada class General dan BPJS. Ini adalah abstraksi.”

Jika ingin bukti tambahan, buka:

- `clinic/routes.py`, baris 401–405; dan
- `clinic/services.py`, baris 203–228.

Jelaskan bahwa route farmasi cukup memanggil `PharmacyService.process()`.

## Enkapsulasi

Buka:

`clinic/models.py`

Lihat:

- baris 208–231;
- class `Medicine`;
- attribute `_stock`;
- method `change_stock()`.

Yang saya jelaskan:

> “Stok tidak diubah sembarangan. Method ini memeriksa jumlah, alasan, dan stok yang tersedia. Perubahannya juga dicatat. Ini adalah enkapsulasi.”

## Pewarisan

Buka:

`clinic/services.py`

Lihat:

- baris 231–248;
- `PaymentProcessor`;
- `GeneralPayment(PaymentProcessor)`;
- `BPJSPayment(PaymentProcessor)`.

Yang saya jelaskan:

> “GeneralPayment dan BPJSPayment adalah class anak. Keduanya mewarisi aturan `amounts()` dari PaymentProcessor. Ini adalah inheritance.”

## Polimorfisme

Buka:

`clinic/services.py`

Lihat:

- baris 241–248 untuk dua hasil `amounts()`;
- baris 251–265 untuk pemilihan object dan pemanggilan method.

Yang saya jelaskan:

> “BillingService memanggil method yang sama, yaitu `amounts()`. Jika object-nya General, pasien membayar total. Jika object-nya BPJS, pasien membayar nol. Ini adalah polymorphism.”

## Class dan Object Dokter

Buka:

- `clinic/models.py`, baris 109–114; dan
- `seed.py`, baris 15–16 serta 30–34.

Yang saya jelaskan:

> “Doctor adalah class atau cetakan. Fakih dan Alia adalah dua object berbeda dari class Doctor. Spesialisasi dan jadwal mereka berbeda.”

---

# Jawaban Singkat Saat Dosen Bertanya

## Pertanyaan tentang Abstraksi

**Dosen:** Apa itu abstraksi?

**Jawaban:**

> “Abstraksi artinya kita memakai fungsi penting tanpa perlu tahu semua detail rumit di belakangnya.”

**Dosen:** Mana abstraksinya?

**Jawaban:**

> “Buka `clinic/services.py` baris 231. Ada `PaymentProcessor` dengan method `amounts()`. Class itu memberi aturan umum, sedangkan cara menghitungnya diserahkan ke General dan BPJS.”

## Pertanyaan tentang Enkapsulasi

**Dosen:** Apa itu enkapsulasi?

**Jawaban:**

> “Enkapsulasi artinya data penting dijaga supaya tidak diubah sembarangan.”

**Dosen:** Mana enkapsulasinya?

**Jawaban:**

> “Buka `clinic/models.py` baris 208. Stok Medicine disimpan sebagai `_stock` dan diubah lewat `change_stock()`. Method itu memeriksa stok dan mencatat perubahannya.”

## Pertanyaan tentang Pewarisan

**Dosen:** Apa itu inheritance?

**Jawaban:**

> “Inheritance adalah pewarisan. Class anak menerima aturan dasar dari class induk.”

**Dosen:** Mana inheritance-nya?

**Jawaban:**

> “Buka `clinic/services.py` baris 233 sampai 248. `GeneralPayment` dan `BPJSPayment` mewarisi `PaymentProcessor`.”

**Dosen:** Apakah Doctor mewarisi User?

**Jawaban:**

> “Tidak pada source ini. Doctor terhubung ke User melalui `user_id`. Inheritance domain yang nyata ada pada strategi pembayaran.”

## Pertanyaan tentang Polimorfisme

**Dosen:** Apa itu polymorphism?

**Jawaban:**

> “Polymorphism artinya nama method sama, tetapi hasilnya bisa berbeda sesuai object yang menjalankan.”

**Dosen:** Mana polymorphism-nya?

**Jawaban:**

> “Buka `clinic/services.py` baris 241 sampai 264. General dan BPJS sama-sama punya `amounts()`, tetapi hasilnya berbeda. BillingService memanggil nama method yang sama.”

## Pertanyaan Umum

**Dosen:** Apa beda class dan object?

**Jawaban:**

> “Class adalah cetakan. Object adalah hasil nyata dari cetakan. Doctor adalah class, sedangkan Fakih dan Alia adalah object.”

**Dosen:** Apa beda abstraksi dan enkapsulasi?

**Jawaban:**

> “Abstraksi menyembunyikan proses yang rumit. Enkapsulasi menjaga data agar tidak diubah sembarangan.”

**Dosen:** Apakah semua role memakai semua pilar?

**Jawaban:**

> “Tidak. Pilar dipakai sesuai kebutuhan. Contohnya enkapsulasi stok paling dekat dengan apoteker, sedangkan polymorphism pembayaran paling dekat dengan kasir dan pasien.”

**Dosen:** Apakah QRIS dan Tunai sudah polymorphic?

**Jawaban:**

> “Belum. Pada source sekarang, QRIS dan Tunai masih berupa pilihan teks. Polymorphism yang jelas ada pada GeneralPayment dan BPJSPayment.”

**Dosen:** Apa manfaat OOP untuk klinik?

**Jawaban:**

> “Kode menjadi lebih rapi. Data dan tugas setiap bagian lebih jelas. Aturan penting juga tidak perlu ditulis berulang.”

---

# Cheat Sheet Presentasi

## Arti Istilah

| Istilah | Arti paling mudah |
|---|---|
| Class | Cetakan. |
| Object | Hasil nyata dari cetakan. |
| Attribute | Data milik object. |
| Method | Fungsi milik class. |
| Service | Bagian yang mengurus satu kelompok pekerjaan. |
| Abstraksi | Pakai yang penting, sembunyikan detail rumit. |
| Enkapsulasi | Jaga data agar tidak diubah sembarangan. |
| Inheritance | Class anak menerima aturan dari class induk. |
| Polymorphism | Method sama, hasil dapat berbeda. |

## Empat Pilar dalam Empat Kalimat

1. **Abstraksi:** `PaymentProcessor` menunjukkan fungsi penting dan menyembunyikan cara hitung.
2. **Enkapsulasi:** `Medicine.change_stock()` menjaga perubahan stok.
3. **Inheritance:** `GeneralPayment` dan `BPJSPayment` mewarisi `PaymentProcessor`.
4. **Polymorphism:** `amounts()` memberi hasil berbeda untuk General dan BPJS.

## Urutan Presentasi yang Disarankan

1. Jelaskan OOP dengan contoh klinik.
2. Jelaskan class sebagai cetakan.
3. Jelaskan object dengan Fakih dan Alia.
4. Buka `PaymentProcessor` untuk abstraksi.
5. Buka `Medicine.change_stock()` untuk enkapsulasi.
6. Tunjukkan tanda kurung pada `GeneralPayment(PaymentProcessor)` untuk inheritance.
7. Tunjukkan dua hasil `amounts()` untuk polymorphism.
8. Jelaskan dengan jujur bahwa role bukan turunan `User` pada source ini.
9. Tutup dengan manfaat OOP untuk sistem klinik.

## Kalimat Hafalan

> **Abstraksi menyederhanakan. Enkapsulasi menjaga. Inheritance mewariskan. Polymorphism membedakan hasil.**

---

# Kesimpulan Audit

Empat pilar OOP ditemukan pada aplikasi Flask Medika Husada.

Kekuatan penerapannya berbeda-beda:

- Abstraksi terlihat pada `PaymentProcessor` dan service layer.
- Enkapsulasi terlihat pada password, stok obat, dan perpindahan status.
- Inheritance domain terlihat jelas pada strategi pembayaran.
- Polymorphism terlihat pada hasil `amounts()` untuk General dan BPJS.

Hal yang harus disampaikan dengan jujur:

- `Doctor` dan `Patient` tidak mewarisi `User`.
- Admin, Perawat, Apoteker, dan Kasir adalah role, bukan class anak.
- Tunai, Transfer, QRIS, dan Debit belum menjadi class polymorphic terpisah.
- `begitulah.py` berisi contoh PBO, tetapi tidak dipakai sebagai bukti aplikasi yang berjalan karena tidak diimpor oleh `app.py` atau package `clinic`.

Dokumen ini hanya menjelaskan source yang sudah ada.

Tidak ada perubahan model, service, route, database, workflow, login, role, UI, atau behavior aplikasi untuk membuat dokumentasi ini.
