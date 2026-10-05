# ==============================================================================
# SISTEM INFORMASI MANAJEMEN KLINIK MEDIKA HUSADA (SIM-KLINIK)
# Berbasis Python Object-Oriented Programming (OOP - 4 Pilar) + Web UI Flask & Tailwind/CSS
# ==============================================================================
# STRUKTUR FOLDER & ARTIFAK PROYEK:
# Proyek ini dirancang mandiri (single-file runnable atau modular bundle)
# Jalankan langsung dengan: python app.py
# Kebutuhan library minimal: pip install flask
# Database otomatis dibuat via SQLite (medika_husada.db)
# ==============================================================================

import os
import sys
import json
import sqlite3
from datetime import datetime
from abc import ABC, abstractmethod
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify, flash

# ==============================================================================
# BAGIAN 1: IMPLEMENTASI 4 PILAR OOP (PBO)
# ==============================================================================
"""
1. ABSTRACTION:
   - Kelas abstrak `Pengguna` mendefinisikan interface umum untuk login dan otorisasi peran via `@abstractmethod get_role_dashboard()`.
   - Kelas abstrak `LayananKlinik` mendefinisikan kontrak kalkulasi tarif tindakan / obat.

2. INHERITANCE:
   - Kelas `Pasien`, `AdminKasir`, `Perawat`, `Dokter`, dan `Apoteker` mewarisi kelas `Pengguna`.
   - Menggunakan mekanisme reusable properties (username, password, nama_lengkap, role).

3. ENCAPSULATION:
   - Variabel private/protected seperti `__password`, `__saldo_resep`, `_nomor_bpjs` diakses
     hanya melalui getter/setter atau method verifikasi internal.

4. POLYMORPHISM:
   - Method `get_role_dashboard()` dan `hitung_biaya_akhir()` diimplementasikan
     berbeda sesuai jenis user atau tipe pembayaran (Pasien BPJS vs Umum).
"""

# --- 1. ABSTRACTION & INHERITANCE: BASE USER ---
class Pengguna(ABC):
    def __init__(self, id_user, username, password, nama_lengkap, no_telp, role):
        self._id_user = id_user
        self._username = username
        self.__password = password  # Encapsulation (Private)
        self.nama_lengkap = nama_lengkap
        self.no_telp = no_telp
        self.role = role

    # Encapsulation: Getter & Verifier
    def verify_password(self, input_password):
        return self.__password == input_password

    def get_username(self):
        return self._username

    def get_id(self):
        return self._id_user

    @abstractmethod
    def get_role_dashboard(self):
        """Metode abstrak yang wajib dioverride oleh turunan (Abstraction & Polymorphism)"""
        pass


class Pasien(Pengguna):
    def __init__(self, id_user, username, password, nama_lengkap, no_telp, no_rm, nik, no_bpjs="", gol_darah="O"):
        super().__init__(id_user, username, password, nama_lengkap, no_telp, role="pasien")
        self._no_rm = no_rm
        self._nik = nik
        self.__no_bpjs = no_bpjs.strip() if no_bpjs else ""
        self.gol_darah = gol_darah

    @property
    def is_bpjs(self):
        return bool(self.__no_bpjs)

    @property
    def no_bpjs(self):
        return self.__no_bpjs

    def get_no_rm(self):
        return self._no_rm

    def get_role_dashboard(self):
        return "/pasien/dashboard"


class AdminKasir(Pengguna):
    """Admin merangkap Kasir sesuai spesifikasi permintaan pengguna"""
    def __init__(self, id_user, username, password, nama_lengkap, no_telp, kode_petugas):
        super().__init__(id_user, username, password, nama_lengkap, no_telp, role="admin_kasir")
        self.kode_petugas = kode_petugas

    def get_role_dashboard(self):
        return "/admin/dashboard"


class Perawat(Pengguna):
    def __init__(self, id_user, username, password, nama_lengkap, no_telp, no_str):
        super().__init__(id_user, username, password, nama_lengkap, no_telp, role="perawat")
        self.no_str = no_str

    def get_role_dashboard(self):
        return "/perawat/dashboard"


class Dokter(Pengguna):
    def __init__(self, id_user, username, password, nama_lengkap, no_telp, spesialisasi, ruangan, no_sip):
        super().__init__(id_user, username, password, nama_lengkap, no_telp, role="dokter")
        self.spesialisasi = spesialisasi
        self.ruangan = ruangan
        self.no_sip = no_sip

    def get_role_dashboard(self):
        return "/dokter/dashboard"


class Apoteker(Pengguna):
    def __init__(self, id_user, username, password, nama_lengkap, no_telp, sipa):
        super().__init__(id_user, username, password, nama_lengkap, no_telp, role="apoteker")
        self.sipa = sipa

    def get_role_dashboard(self):
        return "/apoteker/dashboard"


# --- ENKAPSULASI MODEL MEDIS & KUNJUNGAN ---
class Obat:
    def __init__(self, id_obat, kode, nama_obat, harga, stok, aturan_pakai, deskripsi=""):
        self.id_obat = id_obat
        self.kode = kode
        self.nama_obat = nama_obat
        self.__harga = harga
        self.__stok = stok
        self.aturan_pakai = aturan_pakai
        self.deskripsi = deskripsi

    @property
    def harga(self):
        return self.__harga

    @property
    def stok(self):
        return self.__stok

    def kurangi_stok(self, qty):
        if self.__stok >= qty:
            self.__stok -= qty
            return True
        return False


class KunjunganAntrean:
    """Mengelola siklus status:
    1. 'Menunggu Verifikasi Jadwal' (Admin)
    2. 'Menunggu Triase Perawat' (Perawat)
    3. 'Menunggu Dokter' (Dokter)
    4. 'Menunggu Obat' (Apoteker meracik)
    5. 'Pengambilan Obat & Pembayaran' (Kasir)
    6. 'Selesai' (Struk lunas, Semoga Lekas Sembuh)
    7. 'Dibatalkan'
    """
    def __init__(self, id_kunjungan, no_antrean, id_pasien, id_dokter, tanggal_kunjungan, jam_kunjungan, keluhan, status="Menunggu Verifikasi Jadwal"):
        self.id_kunjungan = id_kunjungan
        self.no_antrean = no_antrean
        self.id_pasien = id_pasien
        self.id_dokter = id_dokter
        self.tanggal_kunjungan = tanggal_kunjungan
        self.jam_kunjungan = jam_kunjungan
        self.keluhan = keluhan
        self.__status = status

    @property
    def status(self):
        return self.__status

    def set_status(self, status_baru):
        self.__status = status_baru


# --- POLYMORPHISM DALAM PERHITUNGAN STRUK BIAYA ---
class PerhitunganStruk(ABC):
    @abstractmethod
    def kalkulasi(self, total_tindakan, total_obat):
        pass


class StrukUmum(PerhitunganStruk):
    def kalkulasi(self, total_tindakan, total_obat):
        subtotal = total_tindakan + total_obat
        biaya_admin = 15000
        total_bayar = subtotal + biaya_admin
        return {
            "biaya_tindakan": total_tindakan,
            "biaya_obat": total_obat,
            "biaya_admin": biaya_admin,
            "potongan_bpjs": 0,
            "total_akhir": total_bayar,
            "keterangan": "Pasien Umum (Bayar Penuh)"
        }


class StrukBPJS(PerhitunganStruk):
    def kalkulasi(self, total_tindakan, total_obat):
        subtotal = total_tindakan + total_obat + 15000
        return {
            "biaya_tindakan": total_tindakan,
            "biaya_obat": total_obat,
            "biaya_admin": 15000,
            "potongan_bpjs": subtotal,
            "total_akhir": 0, # Gratis karena ditanggung BPJS Kesehatan
            "keterangan": "Dijamin Penuh oleh BPJS Kesehatan (Gratis)"
        }


# ==============================================================================
# BAGIAN 2: DATABASE INITIALIZER (SQLITE)
# ==============================================================================
DB_PATH = "medika_husada.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabel Users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        nama_lengkap TEXT NOT NULL,
        no_telp TEXT,
        role TEXT NOT NULL,
        no_rm TEXT,
        nik TEXT,
        no_bpjs TEXT,
        gol_darah TEXT,
        spesialisasi TEXT,
        ruangan TEXT,
        no_str TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Tabel Dokter
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        nama_dokter TEXT NOT NULL,
        spesialisasi TEXT NOT NULL,
        tipe_dokter TEXT NOT NULL, -- 'Umum' atau 'Kandungan'
        hari_praktek TEXT NOT NULL,
        jam_praktek TEXT NOT NULL,
        ruangan TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # Tabel Obat / Farmasi
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kode TEXT UNIQUE NOT NULL,
        nama_obat TEXT NOT NULL,
        harga REAL NOT NULL,
        stok INTEGER NOT NULL,
        aturan_pakai TEXT NOT NULL,
        deskripsi TEXT
    )
    """)

    # Tabel Kunjungan & Antrean
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        no_antrean TEXT NOT NULL,
        pasien_id INTEGER NOT NULL,
        dokter_id INTEGER NOT NULL,
        tanggal_kunjungan TEXT NOT NULL,
        jam_kunjungan TEXT NOT NULL,
        keluhan TEXT NOT NULL,
        status TEXT NOT NULL, -- 'Menunggu Verifikasi', 'Menunggu Triase', 'Menunggu Dokter', 'Menunggu Obat', 'Pengambilan Obat & Pembayaran', 'Selesai', 'Dibatalkan'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (pasien_id) REFERENCES users(id),
        FOREIGN KEY (dokter_id) REFERENCES doctors(id)
    )
    """)

    # Tabel Pemeriksaan Triase Perawat & EMR Dokter
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medical_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id INTEGER UNIQUE NOT NULL,
        -- Triase Perawat (Pemeriksaan Awal Sederhana)
        tensi_darah TEXT,
        suhu_tubuh REAL,
        nadi INTEGER,
        respirasi INTEGER,
        berat_badan REAL,
        catatan_perawat TEXT,
        perawat_id INTEGER,
        -- Pemeriksaan Dokter (SOAP Lanjut)
        subjektif_dokter TEXT,
        objektif_dokter TEXT,
        diagnosa_primer TEXT,
        icd10_code TEXT,
        diagnosa_sekunder TEXT,
        tindakan_terapi TEXT,
        dokter_id INTEGER,
        biaya_tindakan REAL DEFAULT 50000,
        FOREIGN KEY (visit_id) REFERENCES visits(id)
    )
    """)

    # Tabel Resep Obat Kunjungan
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prescriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id INTEGER NOT NULL,
        medicine_id INTEGER NOT NULL,
        jumlah INTEGER NOT NULL,
        aturan_pakai TEXT NOT NULL,
        catatan_resep TEXT,
        status_racik TEXT DEFAULT 'Menunggu Racik', -- 'Menunggu Racik', 'Selesai Diracik'
        FOREIGN KEY (visit_id) REFERENCES visits(id),
        FOREIGN KEY (medicine_id) REFERENCES medicines(id)
    )
    """)

    # Tabel Pembayaran & Struk Kasir
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS billing (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id INTEGER UNIQUE NOT NULL,
        no_struk TEXT NOT NULL,
        total_tindakan REAL NOT NULL,
        total_obat REAL NOT NULL,
        biaya_admin REAL NOT NULL,
        potongan_bpjs REAL NOT NULL,
        total_akhir REAL NOT NULL,
        metode_bayar TEXT NOT NULL, -- 'BPJS PBI/Non-PBI', 'Tunai', 'QRIS', 'Transfer'
        status_bayar TEXT NOT NULL, -- 'Lunas', 'Menunggu Pembayaran'
        waktu_bayar TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        kasir_id INTEGER,
        FOREIGN KEY (visit_id) REFERENCES visits(id)
    )
    """)

    # Tabel Rujukan Digital Rumah Sakit Mitra
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS digital_referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id INTEGER UNIQUE NOT NULL,
        no_surat_rujukan TEXT UNIQUE NOT NULL,
        rumah_sakit_tujuan TEXT NOT NULL,
        poli_tujuan TEXT NOT NULL,
        alasan_rujukan TEXT NOT NULL,
        catatan_tambahan TEXT,
        tanggal_rujukan TEXT NOT NULL,
        status_rujukan TEXT DEFAULT 'Aktif / Terkirim Digital',
        FOREIGN KEY (visit_id) REFERENCES visits(id)
    )
    """)

    # --- SEEDING DATA AWAL (Jadwal Dokter Sesuai Permintaan & Data Master) ---
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        # Default Admin & Kasir (digabung sesuai permintaan)
        cursor.execute("""
        INSERT INTO users (username, password, nama_lengkap, no_telp, role)
        VALUES ('admin', 'admin123', 'Siti Rahmawati, S.Ak', '081234567890', 'admin_kasir')
        """)

        # Default Perawat
        cursor.execute("""
        INSERT INTO users (username, password, nama_lengkap, no_telp, role, no_str)
        VALUES ('perawat', 'perawat123', 'Ns. Dian Lestari, S.Kep', '081298765432', 'perawat', 'STR-3273-9821')
        """)

        # Default Dokter Umum: Muhammad fakih nabal
        cursor.execute("""
        INSERT INTO users (username, password, nama_lengkap, no_telp, role, spesialisasi, ruangan)
        VALUES ('dr_fakih', 'dokter123', 'dr. Muhammad Fakih Nabal', '081345678901', 'dokter', 'Dokter Umum', 'Poli Umum (R.01)')
        """)
        doc1_user_id = cursor.lastrowid

        # Default Dokter Kandungan: Alia Fransiska Dewi Arum Trilestari
        cursor.execute("""
        INSERT INTO users (username, password, nama_lengkap, no_telp, role, spesialisasi, ruangan)
        VALUES ('dr_alia', 'dokter123', 'dr. Alia Fransiska Dewi Arum Trilestari, Sp.OG', '081398765432', 'dokter', 'Spesialis Obstetri & Ginekologi (Kandungan)', 'Poli Kandungan & KIA (R.02)')
        """)
        doc2_user_id = cursor.lastrowid

        # Default Apoteker
        cursor.execute("""
        INSERT INTO users (username, password, nama_lengkap, no_telp, role)
        VALUES ('apoteker', 'apoteker123', 'apt. Rahmat Hidayat, S.Farm', '081355554444', 'apoteker')
        """)

        # Default Pasien Contoh (Budi Santoso & Ibu Ratna)
        cursor.execute("""
        INSERT INTO users (username, password, nama_lengkap, no_telp, role, no_rm, nik, no_bpjs, gol_darah)
        VALUES ('pasien', 'pasien123', 'Bpk. Budi Santoso', '08122334455', 'pasien', 'KMH-2024-001', '3273201987654002', '0001827635411', 'O+')
        """)

        cursor.execute("""
        INSERT INTO users (username, password, nama_lengkap, no_telp, role, no_rm, nik, no_bpjs, gol_darah)
        VALUES ('siti', 'siti123', 'Ibu Siti Aminah', '08127788990', 'pasien', 'KMH-2024-002', '3273201991054001', '', 'B+')
        """)

        # Data Master Jadwal Dokter
        cursor.execute("""
        INSERT INTO doctors (user_id, nama_dokter, spesialisasi, tipe_dokter, hari_praktek, jam_praktek, ruangan)
        VALUES (?, 'dr. Muhammad Fakih Nabal', 'Dokter Umum', 'Umum', 'Senin - Sabtu', '08:00 - 14:00 WIB', 'Poli Umum (R.01)')
        """, (doc1_user_id,))

        cursor.execute("""
        INSERT INTO doctors (user_id, nama_dokter, spesialisasi, tipe_dokter, hari_praktek, jam_praktek, ruangan)
        VALUES (?, 'dr. Alia Fransiska Dewi Arum Trilestari, Sp.OG', 'Spesialis Obstetri & Ginekologi (Kandungan)', 'Kandungan', 'Senin, Rabu, Jumat', '14:30 - 20:00 WIB', 'Poli Kandungan & KIA (R.02)')
        """, (doc2_user_id,))

        # Data Master Obat & Panduan Minum
        obat_list = [
            ('OBT-001', 'Paracetamol 500mg', 12000, 250, 'Diminum sesudah makan 1 tablet 3 kali sehari bila demam', 'Antipiretik & Analgesik untuk pereda demam dan sakit kepala'),
            ('OBT-002', 'Amoxicillin 500mg', 25000, 180, 'Diminum sesudah makan 1 kaplet 3 kali sehari wajib dihabiskan', 'Antibiotik spektrum luas'),
            ('OBT-003', 'Asam Folat 1mg (Folavit)', 35000, 140, 'Diminum sesudah makan 1 tablet 1 kali sehari pagi hari', 'Nutrisi prenatal & perkembangan janin'),
            ('OBT-004', 'Kalsium Laktat (Calcifar)', 28000, 160, 'Diminum sesudah makan 1 tablet 2 kali sehari pagi & malam', 'Suplemen kalsium ibu hamil dan kesehatan tulang'),
            ('OBT-005', 'Antasida Doen Chewable', 10000, 300, 'Dikunyah sebelum makan 1-2 tablet 3 kali sehari bila perih lambung', 'Pereda asam lambung dan nyeri ulu hati'),
            ('OBT-006', 'Cetirizine 10mg', 18000, 120, 'Diminum malam hari menjelang tidur 1 tablet 1 kali sehari', 'Antihistamin pereda alergi dan gatal')
        ]
        cursor.executemany("""
        INSERT INTO medicines (kode, nama_obat, harga, stok, aturan_pakai, deskripsi)
        VALUES (?, ?, ?, ?, ?, ?)
        """, obat_list)

    conn.commit()
    conn.close()

# Inisialisasi DB saat start
init_db()

print(">> Database Medika Husada siap dengan skema relasional & akun default.")
