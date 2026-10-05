(function () {
  const iso = (offset = 0) => {
    const date = new Date();
    date.setDate(date.getDate() + offset);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  };

  const schedules = (doctorId, start, end) => Array.from({ length: 6 }, (_, weekday) => ({
    id: doctorId * 10 + weekday,
    doctorId,
    weekday,
    start,
    end,
    interval: 30,
    quota: 12
  }));

  window.ClinicSeed = {
    version: 3,
    build() {
      const today = iso();
      const historyDay = iso(-7);
      return {
        meta: { version: this.version, createdAt: new Date().toISOString(), queueCounters: { [`1:${today}`]: 3, [`2:${today}`]: 1 } },
        session: null,
        users: [
          { id: 1, name: 'Siti Rahmawati', email: 'admin@medikahusada.local', password: 'Admin123!', phone: '081234567890', role: 'admin', active: true },
          { id: 2, name: 'Ns. Dian Lestari', email: 'perawat@medikahusada.local', password: 'Perawat123!', phone: '081234567891', role: 'nurse', active: true },
          { id: 3, name: 'apt. Rahmat Hidayat', email: 'apoteker@medikahusada.local', password: 'Apoteker123!', phone: '081234567892', role: 'pharmacist', active: true },
          { id: 4, name: 'dr. Muhammad Fakih Nabal', email: 'fakih@medikahusada.local', password: 'Dokter123!', phone: '081234567893', role: 'doctor', active: true },
          { id: 5, name: 'dr. Alia Fransiska Dewi Arum Trilestari', email: 'alia@medikahusada.local', password: 'Dokter123!', phone: '081234567894', role: 'doctor', active: true },
          { id: 6, name: 'Budi Santoso', email: 'pasien@medikahusada.local', password: 'Pasien123!', phone: '081234567895', role: 'patient', active: true },
          { id: 7, name: 'Ratna Permata', email: 'ratna@medikahusada.local', password: 'Pasien123!', phone: '081234567896', role: 'patient', active: true },
          { id: 8, name: 'Siti Aminah', email: 'siti@medikahusada.local', password: 'Pasien123!', phone: '081234567897', role: 'patient', active: true }
        ],
        patients: [
          { id: 1, userId: 6, mr: 'KMH-2026-00001', nik: '3273201990000006', birthDate: '1990-05-12', gender: 'Laki-laki', address: 'Jl. Melati No. 12', bpjs: '', bpjsActive: false, allergies: 'Tidak diketahui', history: 'Tidak tercatat', surgery: '', medication: '', emergency: 'Ibu Budi · 081200000001' },
          { id: 2, userId: 7, mr: 'KMH-2026-00002', nik: '3273201990000007', birthDate: '1990-05-12', gender: 'Perempuan', address: 'Jl. Cempaka No. 8', bpjs: '0001234567890', bpjsActive: true, allergies: 'Penisilin', history: 'Asma ringan', surgery: '', medication: 'Inhaler bila diperlukan', emergency: 'Bapak Ratna · 081200000002' },
          { id: 3, userId: 8, mr: 'KMH-2026-00003', nik: '3273201990000008', birthDate: '1994-11-02', gender: 'Perempuan', address: 'Jl. Kenanga No. 4', bpjs: '', bpjsActive: false, allergies: '', history: '', surgery: '', medication: '', emergency: 'Andi · 081200000003' }
        ],
        doctors: [
          { id: 1, userId: 4, specialty: 'Dokter Umum', fee: 75000, avatar: 'assets/hospital/assets/images/xs/avatar1.jpg', schedules: schedules(1, '08:00', '14:00') },
          { id: 2, userId: 5, specialty: 'Obstetri dan Ginekologi', fee: 150000, avatar: 'assets/hospital/assets/images/xs/avatar2.jpg', schedules: schedules(2, '14:00', '20:00') }
        ],
        appointments: [
          { id: 1, patientId: 1, doctorId: 1, date: today, time: '08:00', complaint: 'Demam dan batuk sejak dua hari.', notes: '', insurance: false, status: 'VERIFIED', visitId: 1 },
          { id: 2, patientId: 2, doctorId: 2, date: today, time: '14:00', complaint: 'Kontrol kesehatan berkala.', notes: 'Membawa hasil pemeriksaan sebelumnya.', insurance: true, status: 'PENDING', visitId: null },
          { id: 3, patientId: 3, doctorId: 1, date: today, time: '08:30', complaint: 'Pusing dan cepat lelah.', notes: '', insurance: false, status: 'CHECKED_IN', visitId: 2 },
          { id: 4, patientId: 2, doctorId: 1, date: today, time: '09:00', complaint: 'Batuk alergi belum membaik.', notes: '', insurance: true, status: 'CHECKED_IN', visitId: 3 },
          { id: 5, patientId: 1, doctorId: 2, date: today, time: '14:30', complaint: 'Konsultasi hasil laboratorium.', notes: '', insurance: false, status: 'CHECKED_IN', visitId: 4 },
          { id: 6, patientId: 1, doctorId: 1, date: historyDay, time: '08:00', complaint: 'Kontrol kesehatan rutin.', notes: '', insurance: false, status: 'COMPLETED', visitId: 5 }
        ],
        visits: [
          { id: 1, appointmentId: 1, queue: 'D1-001', queueState: 'WAITING', status: 'WAITING_NURSE', nursing: null, examination: null, prescription: null, invoice: null, referral: null },
          { id: 2, appointmentId: 3, queue: 'D1-002', queueState: 'CALLED', status: 'WAITING_DOCTOR', nursing: { systolic: 118, diastolic: 78, temperature: 36.8, weight: 54, height: 158, pulse: 76, respiration: 18, spo2: 99, pain: 2, complaint: 'Pusing dan cepat lelah.', notes: 'Pasien sadar penuh.' }, examination: null, prescription: null, invoice: null, referral: null },
          { id: 3, appointmentId: 4, queue: 'D1-003', queueState: 'WAITING', status: 'WAITING_PHARMACY', nursing: { systolic: 116, diastolic: 76, temperature: 36.5, weight: 58, height: 160, pulse: 74, respiration: 17, spo2: 99, pain: 1, complaint: 'Batuk alergi.', notes: '' }, examination: { anamnesis: 'Batuk memburuk saat malam.', physical: 'Kondisi umum baik.', assessment: 'Alergi saluran napas.', diagnosis: 'Rinitis alergi', secondary: '', icd10: 'J30.9', treatment: 'Konsultasi', treatmentFee: 0, notes: 'Pantau pemicu alergi.', recommendation: 'Hindari debu dan cukup istirahat.', followup: 'Kontrol 7 hari bila belum membaik.', laboratory: '' }, prescription: { status: 'NEW', items: [{ medicineId: 4, quantity: 10, price: 2500, dosage: '1 tablet', frequency: '1 kali sehari', duration: '10 hari', timing: 'Sesudah makan', instruction: 'Diminum malam hari.' }] }, invoice: null, referral: null },
          { id: 4, appointmentId: 5, queue: 'D2-001', queueState: 'WAITING', status: 'WAITING_PAYMENT', nursing: { systolic: 120, diastolic: 80, temperature: 36.6, weight: 65, height: 170, pulse: 75, respiration: 18, spo2: 98, pain: 0, complaint: 'Konsultasi hasil laboratorium.', notes: '' }, examination: { anamnesis: 'Evaluasi hasil laboratorium.', physical: 'Kondisi umum baik.', assessment: 'Hasil dalam batas normal.', diagnosis: 'Pemeriksaan kesehatan umum', secondary: '', icd10: 'Z00.0', treatment: 'Interpretasi hasil laboratorium', treatmentFee: 25000, notes: '', recommendation: 'Pertahankan pola hidup sehat.', followup: 'Kontrol sesuai kebutuhan.', laboratory: 'Dalam batas rujukan.' }, prescription: null, invoice: { number: `INV-${today.replaceAll('-', '')}-00004`, subtotal: 175000, discount: 0, coverage: 0, payable: 175000, status: 'UNPAID', method: '', items: [{ description: 'Konsultasi dokter', category: 'consultation', quantity: 1, price: 150000 }, { description: 'Interpretasi hasil laboratorium', category: 'treatment', quantity: 1, price: 25000 }] }, referral: null },
          { id: 5, appointmentId: 6, queue: 'DEMO-001', queueState: 'WAITING', status: 'COMPLETED', nursing: { systolic: 120, diastolic: 80, temperature: 36.5, weight: 65, height: 170, pulse: 75, respiration: 18, spo2: 98, pain: 0, complaint: 'Kontrol kesehatan rutin.', notes: '' }, examination: { anamnesis: 'Kontrol rutin.', physical: 'Kondisi umum baik.', assessment: '', diagnosis: 'Pemeriksaan kesehatan umum', secondary: '', icd10: 'Z00.0', treatment: 'Konsultasi', treatmentFee: 0, notes: '', recommendation: 'Pola hidup sehat.', followup: 'Kontrol sesuai kebutuhan.', laboratory: '' }, prescription: { status: 'DISPENSED', items: [{ medicineId: 1, quantity: 2, price: 1000, dosage: '1 tablet', frequency: 'Sesuai kebutuhan', duration: 'Maksimal 3 hari', timing: 'Sesudah makan', instruction: 'Data resep demo.' }] }, invoice: { number: `INV-${historyDay.replaceAll('-', '')}-00005`, subtotal: 77000, discount: 0, coverage: 0, payable: 77000, status: 'PAID', method: 'Tunai', paidAt: new Date().toISOString(), items: [{ description: 'Konsultasi dokter', category: 'consultation', quantity: 1, price: 75000 }, { description: 'Paracetamol 500 mg', category: 'medicine', quantity: 2, price: 1000 }] }, referral: null }
        ],
        medicines: [
          { id: 1, name: 'Paracetamol 500 mg', category: 'Analgesik', unit: 'tablet', stock: 198, price: 1000, minimum: 20, expiry: iso(360) },
          { id: 2, name: 'Amoxicillin 500 mg', category: 'Antibiotik', unit: 'kapsul', stock: 120, price: 1800, minimum: 20, expiry: iso(300) },
          { id: 3, name: 'Omeprazole 20 mg', category: 'Lambung', unit: 'kapsul', stock: 80, price: 2200, minimum: 15, expiry: iso(260) },
          { id: 4, name: 'Cetirizine 10 mg', category: 'Antihistamin', unit: 'tablet', stock: 90, price: 2500, minimum: 20, expiry: iso(330) },
          { id: 5, name: 'Vitamin B Complex', category: 'Vitamin', unit: 'tablet', stock: 15, price: 1600, minimum: 20, expiry: iso(420) },
          { id: 6, name: 'Asam Folat', category: 'Vitamin', unit: 'tablet', stock: 150, price: 1200, minimum: 20, expiry: iso(500) },
          { id: 7, name: 'Ibuprofen 400 mg', category: 'Analgesik', unit: 'tablet', stock: 12, price: 2400, minimum: 20, expiry: iso(270) }
        ],
        stockMovements: [
          { id: 1, medicineId: 1, quantity: -2, reason: 'Penyerahan resep', createdAt: new Date(Date.now() - 7 * 86400000).toISOString() },
          { id: 2, medicineId: 5, quantity: 15, reason: 'Stok awal demo', createdAt: new Date(Date.now() - 3 * 86400000).toISOString() }
        ],
        notifications: [
          { id: 1, userId: 6, message: 'Appointment terverifikasi. Antrean D1-001.', read: false, createdAt: new Date().toISOString() },
          { id: 2, userId: 7, message: 'Janji berhasil dibuat. Menunggu verifikasi admin.', read: false, createdAt: new Date().toISOString() },
          { id: 3, userId: 1, message: 'Ada janji baru yang menunggu verifikasi.', read: false, createdAt: new Date().toISOString() }
        ]
      };
    }
  };
})();
