(function () {
  const KEY = 'medika-husada-front-v3';
  const labels = {
    patient: 'Pasien', admin: 'Admin', nurse: 'Perawat', doctor: 'Dokter', pharmacist: 'Apoteker',
    PENDING: 'Menunggu verifikasi', RESCHEDULED: 'Jadwal diubah · menunggu verifikasi', VERIFIED: 'Terverifikasi',
    CHECKED_IN: 'Sudah hadir', CANCELLED: 'Dibatalkan', REJECTED: 'Ditolak',
    WAITING_VERIFICATION: 'Menunggu verifikasi ulang', WAITING_NURSE: 'Menunggu pemeriksaan perawat',
    WAITING_DOCTOR: 'Menunggu dokter', WITH_DOCTOR: 'Pemeriksaan dokter', WAITING_PHARMACY: 'Resep diterima apotek',
    PHARMACY_PROCESSING: 'Obat sedang disiapkan', MEDICINE_READY: 'Obat siap diambil',
    WAITING_PAYMENT: 'Menunggu pembayaran', COMPLETED: 'Pelayanan selesai',
    NEW: 'Resep baru', PROCESSING: 'Sedang diracik', READY: 'Siap diambil', DISPENSED: 'Sudah diserahkan', OUT_OF_STOCK: 'Stok tidak cukup',
    UNPAID: 'Belum dibayar', PAID: 'Lunas', BPJS_COVERED: 'Ditanggung BPJS'
  };

  const clone = value => JSON.parse(JSON.stringify(value));
  const maxId = list => list.reduce((max, item) => Math.max(max, Number(item.id) || 0), 0);
  const localISO = (date = new Date()) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const required = (value, label) => {
    const clean = String(value ?? '').trim();
    if (!clean) throw new Error(`${label} wajib diisi.`);
    return clean;
  };
  const number = (value, label, min = 0, max = Number.MAX_SAFE_INTEGER) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < min || parsed > max) throw new Error(`${label} harus antara ${min} dan ${max}.`);
    return parsed;
  };

  let state;
  try {
    state = JSON.parse(localStorage.getItem(KEY));
    if (!state || state.meta?.version !== window.ClinicSeed.version) state = null;
  } catch (_) { state = null; }
  if (!state) state = window.ClinicSeed.build();

  const api = {
    labels,
    get state() { return state; },
    save() { localStorage.setItem(KEY, JSON.stringify(state)); },
    reset() { state = window.ClinicSeed.build(); this.save(); },
    today: localISO,
    user(id) { return state.users.find(item => item.id === Number(id)); },
    patient(id) { return state.patients.find(item => item.id === Number(id)); },
    patientByUser(userId) { return state.patients.find(item => item.userId === Number(userId)); },
    doctor(id) { return state.doctors.find(item => item.id === Number(id)); },
    doctorByUser(userId) { return state.doctors.find(item => item.userId === Number(userId)); },
    appointment(id) { return state.appointments.find(item => item.id === Number(id)); },
    visit(id) { return state.visits.find(item => item.id === Number(id)); },
    medicine(id) { return state.medicines.find(item => item.id === Number(id)); },
    currentUser() { return state.session ? this.user(state.session.userId) : null; },
    patientName(patientId) { const p = this.patient(patientId); return this.user(p?.userId)?.name || 'Pasien'; },
    doctorName(doctorId) { const d = this.doctor(doctorId); return this.user(d?.userId)?.name || 'Dokter'; },
    currentPatient() { const user = this.currentUser(); return user ? this.patientByUser(user.id) : null; },
    currentDoctor() { const user = this.currentUser(); return user ? this.doctorByUser(user.id) : null; },
    login(email, password) {
      const user = state.users.find(item => item.email.toLowerCase() === String(email).trim().toLowerCase());
      if (!user || user.password !== password || !user.active) throw new Error('Email atau password tidak valid, atau akun nonaktif.');
      state.session = { userId: user.id, loggedAt: new Date().toISOString() };
      this.save();
      return user;
    },
    logout() { state.session = null; this.save(); },
    switchRole(role) {
      const user = state.users.find(item => item.role === role && item.active);
      if (!user) throw new Error('Tidak ada akun aktif untuk peran tersebut.');
      state.session = { userId: user.id, loggedAt: new Date().toISOString() };
      this.save();
      return user;
    },
    register(data) {
      const email = required(data.email, 'Email').toLowerCase();
      if (!email.includes('@') || state.users.some(item => item.email.toLowerCase() === email)) throw new Error('Email tidak valid atau sudah digunakan.');
      if (String(data.password).length < 8) throw new Error('Password minimal 8 karakter.');
      if (data.password !== data.confirm) throw new Error('Konfirmasi password tidak cocok.');
      const nik = required(data.nik, 'NIK');
      if (!/^\d{16}$/.test(nik) || state.patients.some(item => item.nik === nik)) throw new Error('NIK harus 16 digit dan belum terdaftar.');
      const userId = maxId(state.users) + 1;
      const patientId = maxId(state.patients) + 1;
      state.users.push({ id: userId, name: required(data.name, 'Nama'), email, password: data.password, phone: required(data.phone, 'Telepon'), role: 'patient', active: true });
      state.patients.push({ id: patientId, userId, mr: `KMH-${new Date().getFullYear()}-${String(patientId).padStart(5, '0')}`, nik, birthDate: required(data.birthDate, 'Tanggal lahir'), gender: data.gender || 'Perempuan', address: required(data.address, 'Alamat'), bpjs: data.bpjs || '', bpjsActive: Boolean(data.bpjs), allergies: '', history: '', surgery: '', medication: '', emergency: '' });
      state.session = { userId, loggedAt: new Date().toISOString() };
      this.notify(userId, 'Selamat datang di Medika Husada. Lengkapi profil kesehatan Anda.');
      this.save();
    },
    notify(userId, message) {
      state.notifications.unshift({ id: maxId(state.notifications) + 1, userId, message, read: false, createdAt: new Date().toISOString() });
    },
    readNotifications() {
      const user = this.currentUser();
      state.notifications.filter(item => item.userId === user?.id).forEach(item => { item.read = true; });
      this.save();
    },
    scopedAppointments() {
      const user = this.currentUser();
      if (!user) return [];
      if (user.role === 'patient') return state.appointments.filter(item => item.patientId === this.currentPatient()?.id);
      if (user.role === 'doctor') return state.appointments.filter(item => item.doctorId === this.currentDoctor()?.id);
      return state.appointments;
    },
    scopedVisits() {
      const allowed = new Set(this.scopedAppointments().map(item => item.id));
      return state.visits.filter(item => allowed.has(item.appointmentId));
    },
    slots(doctorId, date, excludeAppointmentId = null) {
      const doctor = this.doctor(doctorId);
      if (!doctor || !date) return [];
      const selected = new Date(`${date}T12:00:00`);
      const weekday = (selected.getDay() + 6) % 7;
      const schedule = doctor.schedules.find(item => item.weekday === weekday);
      if (!schedule) return [];
      const occupied = new Set(state.appointments.filter(item => item.doctorId === Number(doctorId) && item.date === date && item.id !== Number(excludeAppointmentId) && !['CANCELLED', 'REJECTED'].includes(item.status)).map(item => item.time));
      const [startH, startM] = schedule.start.split(':').map(Number);
      const [endH, endM] = schedule.end.split(':').map(Number);
      let cursor = startH * 60 + startM;
      const end = endH * 60 + endM;
      const result = [];
      while (cursor < end && result.length < schedule.quota) {
        const time = `${String(Math.floor(cursor / 60)).padStart(2, '0')}:${String(cursor % 60).padStart(2, '0')}`;
        result.push({ time, available: !occupied.has(time) && date >= localISO() });
        cursor += schedule.interval;
      }
      return result;
    },
    book(data, editId = null) {
      const actor = this.currentUser();
      const patientId = actor.role === 'patient' ? this.currentPatient().id : Number(data.patientId);
      const patient = this.patient(patientId);
      const doctor = this.doctor(data.doctorId);
      if (!patient || !doctor) throw new Error('Pasien atau dokter tidak valid.');
      if (data.insurance === 'bpjs' && !patient.bpjsActive) throw new Error('Pasien belum memiliki BPJS aktif.');
      if (!this.slots(doctor.id, data.date, editId).some(slot => slot.time === data.time && slot.available)) throw new Error('Slot tidak tersedia. Pilih waktu lain.');
      let appointment = editId ? this.appointment(editId) : null;
      if (appointment && !['PENDING', 'RESCHEDULED', 'VERIFIED'].includes(appointment.status)) throw new Error('Janji yang sudah diperiksa tidak dapat diubah.');
      if (!appointment) {
        appointment = { id: maxId(state.appointments) + 1, visitId: null };
        state.appointments.push(appointment);
      }
      Object.assign(appointment, { patientId, doctorId: doctor.id, date: required(data.date, 'Tanggal'), time: required(data.time, 'Waktu'), complaint: required(data.complaint, 'Keluhan'), notes: data.notes || '', insurance: data.insurance === 'bpjs', status: editId ? 'RESCHEDULED' : 'PENDING' });
      if (appointment.visitId) {
        const visit = this.visit(appointment.visitId);
        Object.assign(visit, { status: 'WAITING_VERIFICATION', queue: '—', queueState: 'WAITING' });
      }
      this.notify(this.user(patient.userId).id, editId ? 'Janji diperbarui dan menunggu verifikasi.' : 'Janji berhasil dibuat. Menunggu verifikasi admin.');
      this.notify(1, `Janji ${editId ? 'diubah' : 'baru'} untuk ${this.patientName(patientId)} menunggu verifikasi.`);
      this.save();
      return appointment;
    },
    verifyAppointment(id) {
      const appointment = this.appointment(id);
      if (!appointment || !['PENDING', 'RESCHEDULED'].includes(appointment.status)) throw new Error('Janji sudah diproses.');
      appointment.status = 'VERIFIED';
      const key = `${appointment.doctorId}:${appointment.date}`;
      state.meta.queueCounters[key] = (state.meta.queueCounters[key] || 0) + 1;
      const queue = `D${appointment.doctorId}-${String(state.meta.queueCounters[key]).padStart(3, '0')}`;
      let visit = appointment.visitId ? this.visit(appointment.visitId) : null;
      if (!visit) {
        visit = { id: maxId(state.visits) + 1, appointmentId: appointment.id, queue, queueState: 'WAITING', status: 'WAITING_NURSE', nursing: null, examination: null, prescription: null, invoice: null, referral: null };
        state.visits.push(visit);
        appointment.visitId = visit.id;
      } else Object.assign(visit, { queue, queueState: 'WAITING', status: 'WAITING_NURSE' });
      this.notify(this.patient(appointment.patientId).userId, `Appointment terverifikasi. Antrean ${queue}.`);
      this.save();
    },
    cancelAppointment(id, rejected = false) {
      const appointment = this.appointment(id);
      if (!appointment || !['PENDING', 'RESCHEDULED', 'VERIFIED'].includes(appointment.status)) throw new Error('Janji sudah diperiksa, selesai, atau dibatalkan.');
      appointment.status = rejected ? 'REJECTED' : 'CANCELLED';
      if (appointment.visitId) this.visit(appointment.visitId).status = 'CANCELLED';
      this.notify(this.patient(appointment.patientId).userId, rejected ? 'Janji ditolak oleh admin.' : 'Janji dibatalkan.');
      this.save();
    },
    queue(id, action) {
      const visit = this.visit(id);
      if (!visit) return;
      visit.queueState = action === 'call' ? 'CALLED' : action === 'skip' ? 'SKIPPED' : 'WAITING';
      this.save();
    },
    nursing(id, data) {
      const visit = this.visit(id);
      if (!visit || visit.status !== 'WAITING_NURSE') throw new Error('Status kunjungan sudah berubah.');
      const ranges = { systolic: [40, 300], diastolic: [20, 200], temperature: [30, 45], weight: [1, 500], height: [30, 250], pulse: [20, 250], respiration: [1, 100], spo2: [1, 100], pain: [0, 10] };
      const nursing = {};
      Object.entries(ranges).forEach(([key, range]) => { nursing[key] = number(data[key], key, range[0], range[1]); });
      nursing.complaint = required(data.complaint, 'Keluhan');
      nursing.notes = data.notes || '';
      visit.nursing = nursing;
      visit.status = 'WAITING_DOCTOR';
      this.appointment(visit.appointmentId).status = 'CHECKED_IN';
      this.notify(this.patient(this.appointment(visit.appointmentId).patientId).userId, labels.WAITING_DOCTOR);
      this.save();
    },
    startExam(id) {
      const visit = this.visit(id);
      if (!visit || visit.status !== 'WAITING_DOCTOR') throw new Error('Pasien belum siap atau sudah diperiksa.');
      visit.status = 'WITH_DOCTOR';
      this.save();
    },
    buildInvoice(visit) {
      if (visit.invoice) return visit.invoice;
      const appointment = this.appointment(visit.appointmentId);
      const doctor = this.doctor(appointment.doctorId);
      const items = [{ description: 'Konsultasi dokter', category: 'consultation', quantity: 1, price: doctor.fee }];
      if (visit.examination?.treatmentFee) items.push({ description: visit.examination.treatment || 'Tindakan', category: 'treatment', quantity: 1, price: visit.examination.treatmentFee });
      visit.prescription?.items.forEach(item => items.push({ description: this.medicine(item.medicineId).name, category: 'medicine', quantity: item.quantity, price: item.price }));
      const subtotal = items.reduce((sum, item) => sum + item.quantity * item.price, 0);
      visit.invoice = { number: `INV-${appointment.date.replaceAll('-', '')}-${String(visit.id).padStart(5, '0')}`, subtotal, discount: 0, coverage: appointment.insurance ? subtotal : 0, payable: appointment.insurance ? 0 : subtotal, status: 'UNPAID', method: '', items };
      return visit.invoice;
    },
    examine(id, data) {
      const visit = this.visit(id);
      if (!visit || visit.status !== 'WITH_DOCTOR') throw new Error('Pemeriksaan belum dimulai atau sudah selesai.');
      visit.examination = {
        anamnesis: required(data.anamnesis, 'Anamnesis'), physical: required(data.physical, 'Pemeriksaan fisik'),
        assessment: data.assessment || '', diagnosis: required(data.diagnosis, 'Diagnosis'), secondary: data.secondary || '',
        icd10: data.icd10 || '', treatment: data.treatment || '', treatmentFee: number(data.treatmentFee || 0, 'Biaya tindakan', 0, 100000000),
        notes: data.notes || '', recommendation: data.recommendation || '', followup: data.followup || '', laboratory: data.laboratory || ''
      };
      if (data.medicineId) {
        const medicine = this.medicine(data.medicineId);
        if (!medicine) throw new Error('Obat tidak valid.');
        visit.prescription = { status: 'NEW', items: [{ medicineId: medicine.id, quantity: number(data.quantity, 'Jumlah obat', 1, 10000), price: medicine.price, dosage: required(data.dosage, 'Dosis'), frequency: required(data.frequency, 'Frekuensi'), duration: required(data.duration, 'Durasi'), timing: data.timing || 'Sesudah makan', instruction: data.instruction || '' }] };
        visit.status = 'WAITING_PHARMACY';
      } else {
        visit.status = 'WAITING_PAYMENT';
        this.buildInvoice(visit);
      }
      const patient = this.patient(this.appointment(visit.appointmentId).patientId);
      this.notify(patient.userId, labels[visit.status]);
      this.save();
    },
    pharmacy(id, action) {
      const visit = this.visit(id);
      if (!visit?.prescription) throw new Error('Resep tidak ditemukan.');
      if (action === 'start' && visit.status === 'WAITING_PHARMACY') { visit.status = 'PHARMACY_PROCESSING'; visit.prescription.status = 'PROCESSING'; }
      else if (action === 'ready' && visit.status === 'PHARMACY_PROCESSING') {
        visit.prescription.items.forEach(item => {
          const medicine = this.medicine(item.medicineId);
          if (medicine.stock < item.quantity) throw new Error(`Stok ${medicine.name} tidak cukup.`);
        });
        visit.prescription.items.forEach(item => {
          const medicine = this.medicine(item.medicineId); medicine.stock -= item.quantity;
          state.stockMovements.unshift({ id: maxId(state.stockMovements) + 1, medicineId: medicine.id, quantity: -item.quantity, reason: 'Penyerahan resep', createdAt: new Date().toISOString() });
        });
        visit.status = 'MEDICINE_READY'; visit.prescription.status = 'READY';
      } else if (action === 'handover' && visit.status === 'MEDICINE_READY') { visit.status = 'WAITING_PAYMENT'; visit.prescription.status = 'DISPENSED'; this.buildInvoice(visit); }
      else if (action === 'shortage' && ['WAITING_PHARMACY', 'PHARMACY_PROCESSING'].includes(visit.status)) { visit.prescription.status = 'OUT_OF_STOCK'; this.notify(1, `Stok tidak cukup untuk resep kunjungan #${visit.id}.`); }
      else throw new Error('Aksi farmasi tidak sesuai status saat ini.');
      const patient = this.patient(this.appointment(visit.appointmentId).patientId);
      this.notify(patient.userId, action === 'shortage' ? 'Apotek melaporkan stok tidak cukup.' : labels[visit.status]);
      this.save();
    },
    pay(id, data) {
      const visit = this.visit(id);
      if (!visit?.invoice || visit.status !== 'WAITING_PAYMENT') throw new Error('Invoice belum tersedia atau sudah dibayar.');
      const appointment = this.appointment(visit.appointmentId);
      const discount = number(data.discount || 0, 'Diskon', 0, visit.invoice.subtotal);
      visit.invoice.discount = discount;
      visit.invoice.coverage = appointment.insurance ? visit.invoice.subtotal - discount : 0;
      visit.invoice.payable = appointment.insurance ? 0 : visit.invoice.subtotal - discount;
      visit.invoice.method = appointment.insurance ? 'BPJS' : required(data.method, 'Metode pembayaran');
      visit.invoice.status = appointment.insurance ? 'BPJS_COVERED' : 'PAID';
      visit.invoice.paidAt = new Date().toISOString();
      visit.status = 'COMPLETED'; appointment.status = 'COMPLETED';
      this.notify(this.patient(appointment.patientId).userId, labels.COMPLETED);
      this.save();
    },
    stock(id, delta, reason) {
      const medicine = this.medicine(id);
      delta = number(delta, 'Perubahan stok', -1000000, 1000000);
      if (!medicine || medicine.stock + delta < 0) throw new Error('Stok tidak cukup.');
      medicine.stock += delta;
      state.stockMovements.unshift({ id: maxId(state.stockMovements) + 1, medicineId: medicine.id, quantity: delta, reason: required(reason, 'Alasan'), createdAt: new Date().toISOString() });
      this.save();
    },
    referral(id, data) {
      const visit = this.visit(id);
      if (!visit?.examination) throw new Error('Pemeriksaan dokter belum tersedia.');
      visit.referral = { number: `RUJ-${localISO().replaceAll('-', '')}-${String(id).padStart(5, '0')}`, hospital: required(data.hospital, 'Rumah sakit'), specialist: required(data.specialist, 'Spesialis'), reason: required(data.reason, 'Alasan'), notes: data.notes || '', createdAt: new Date().toISOString() };
      this.save();
    },
    updateProfile(data) {
      const patient = this.currentPatient();
      const user = this.currentUser();
      if (!patient || !user) return;
      user.name = required(data.name, 'Nama'); user.phone = required(data.phone, 'Telepon');
      Object.assign(patient, { nik: required(data.nik, 'NIK'), birthDate: required(data.birthDate, 'Tanggal lahir'), gender: data.gender, address: required(data.address, 'Alamat'), bpjs: data.bpjs || '', bpjsActive: Boolean(data.bpjs), allergies: data.allergies || '', history: data.history || '', surgery: data.surgery || '', medication: data.medication || '', emergency: data.emergency || '' });
      this.save();
    }
  };

  api.save();
  window.Clinic = api;
})();
