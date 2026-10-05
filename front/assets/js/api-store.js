(function () {
  const Local = window.Clinic;
  const BASE = String(window.MEDIKA_API_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');
  const TOKEN_KEY = 'medika-husada-api-token';
  const demoAccounts = {
    admin: ['admin@medikahusada.local', 'Admin123!'],
    nurse: ['perawat@medikahusada.local', 'Perawat123!'],
    doctor: ['fakih@medikahusada.local', 'Dokter123!'],
    pharmacist: ['apoteker@medikahusada.local', 'Apoteker123!'],
    patient: ['pasien@medikahusada.local', 'Pasien123!']
  };
  let token = sessionStorage.getItem(TOKEN_KEY) || '';
  let state = window.ClinicSeed.build();
  let publicSlots = {};

  const messageOf = payload => {
    if (typeof payload?.detail === 'string') return payload.detail;
    if (Array.isArray(payload?.detail) && payload.detail[0]?.msg) return payload.detail[0].msg;
    return payload?.message || 'Permintaan ke server gagal.';
  };

  async function request(path, options = {}) {
    const headers = { Accept: 'application/json', ...(options.headers || {}) };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (options.body && typeof options.body !== 'string') {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }
    let response;
    try {
      response = await fetch(`${BASE}${path}`, { ...options, headers });
    } catch (_) {
      throw new Error('Backend tidak tersambung. Jalankan FastAPI pada port 8000.');
    }
    const payload = response.status === 204 ? {} : await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status === 401) {
        token = '';
        sessionStorage.removeItem(TOKEN_KEY);
      }
      throw new Error(messageOf(payload));
    }
    return payload;
  }

  function apply(payload) {
    if (payload?.state) state = payload.state;
    else if (payload?.meta && payload?.users) state = payload;
    return payload;
  }

  function applyPublic(payload) {
    if (!payload?.doctors || !payload?.users) return;
    const fresh = window.ClinicSeed.build();
    fresh.session = null;
    fresh.users = payload.users;
    fresh.doctors = payload.doctors;
    fresh.appointments = [];
    fresh.visits = [];
    fresh.notifications = [];
    state = fresh;
    publicSlots = payload.slots || {};
  }

  const api = {
    remote: true,
    labels: Local.labels,
    get state() { return state; },
    get apiUrl() { return BASE; },
    today: Local.today,
    user(id) { return state.users.find(item => item.id === Number(id)); },
    patient(id) { return state.patients.find(item => item.id === Number(id)); },
    patientByUser(userId) { return state.patients.find(item => item.userId === Number(userId)); },
    doctor(id) { return state.doctors.find(item => item.id === Number(id)); },
    doctorByUser(userId) { return state.doctors.find(item => item.userId === Number(userId)); },
    appointment(id) { return state.appointments.find(item => item.id === Number(id)); },
    visit(id) { return state.visits.find(item => item.id === Number(id)); },
    medicine(id) { return state.medicines.find(item => item.id === Number(id)); },
    currentUser() { return state.session ? this.user(state.session.userId) : null; },
    currentPatient() { const user = this.currentUser(); return user ? this.patientByUser(user.id) : null; },
    currentDoctor() { const user = this.currentUser(); return user ? this.doctorByUser(user.id) : null; },
    patientName(patientId) { const patient = this.patient(patientId); return this.user(patient?.userId)?.name || 'Pasien'; },
    doctorName(doctorId) { const doctor = this.doctor(doctorId); return this.user(doctor?.userId)?.name || 'Dokter'; },
    scopedAppointments() { return state.appointments; },
    scopedVisits() { return state.visits; },
    async ready() {
      try {
        if (!token) {
          applyPublic(await request('/public'));
          return;
        }
        apply(await request('/state'));
      }
      catch (error) {
        if (!token) state = window.ClinicSeed.build();
        else throw error;
      }
    },
    async refresh() { return apply(await request('/state')); },
    async login(email, password) {
      const result = await request('/auth/login', { method: 'POST', body: { email, password } });
      token = result.accessToken;
      sessionStorage.setItem(TOKEN_KEY, token);
      apply(result);
      return this.currentUser();
    },
    logout() {
      token = '';
      sessionStorage.removeItem(TOKEN_KEY);
      state = window.ClinicSeed.build();
      state.session = null;
    },
    async switchRole(role) {
      const account = demoAccounts[role];
      if (!account) throw new Error('Peran demo tidak tersedia.');
      return this.login(account[0], account[1]);
    },
    async register(data) {
      const result = await request('/auth/register', { method: 'POST', body: data });
      token = result.accessToken;
      sessionStorage.setItem(TOKEN_KEY, token);
      apply(result);
      return this.currentUser();
    },
    async reset() { return this.refresh(); },
    slots(doctorId, date, excludeAppointmentId = null) {
      if (!doctorId || !date) return [];
      if (!this.currentUser()) {
        return date === this.today() ? (publicSlots[String(doctorId)] || []) : [];
      }
      const query = new URLSearchParams({ doctor_id: doctorId, date });
      if (excludeAppointmentId) query.set('exclude_id', excludeAppointmentId);
      return request(`/slots?${query}`).then(result => result.items);
    },
    async book(data, editId = null) {
      const body = {
        patientId: data.patientId ? Number(data.patientId) : null,
        doctorId: Number(data.doctorId),
        date: data.date,
        time: data.time,
        complaint: data.complaint,
        notes: data.notes || '',
        insurance: data.insurance || 'general'
      };
      const result = apply(await request(editId ? `/appointments/${editId}` : '/appointments', {
        method: editId ? 'PUT' : 'POST', body
      }));
      return this.appointment(result.appointmentId || editId);
    },
    async verifyAppointment(id) { return apply(await request(`/appointments/${id}/verify`, { method: 'POST' })); },
    async cancelAppointment(id, rejected = false) {
      return apply(await request(`/appointments/${id}/${rejected ? 'reject' : 'cancel'}`, { method: 'POST' }));
    },
    async queue(id, action) { return apply(await request(`/visits/${id}/queue/${action}`, { method: 'POST' })); },
    async nursing(id, data) {
      const body = { ...data };
      ['systolic','diastolic','temperature','weight','height','pulse','respiration','spo2','pain'].forEach(key => { body[key] = Number(body[key]); });
      return apply(await request(`/visits/${id}/nursing`, { method: 'POST', body }));
    },
    async startExam(id) { return apply(await request(`/visits/${id}/start`, { method: 'POST' })); },
    async examine(id, data) {
      const body = {
        anamnesis: data.anamnesis,
        physical: data.physical,
        assessment: data.assessment || '',
        diagnosis: data.diagnosis,
        secondary: data.secondary || '',
        icd10: data.icd10 || '',
        treatment: data.treatment || '',
        treatmentFee: Number(data.treatmentFee || 0),
        notes: data.notes || '',
        recommendation: data.recommendation || '',
        followup: data.followup || '',
        laboratory: data.laboratory || '',
        items: data.medicineId ? [{
          medicineId: Number(data.medicineId), quantity: Number(data.quantity), dosage: data.dosage,
          frequency: data.frequency, duration: data.duration, timing: data.timing,
          instruction: data.instruction || ''
        }] : []
      };
      return apply(await request(`/visits/${id}/examination`, { method: 'POST', body }));
    },
    async pharmacy(id, action) { return apply(await request(`/visits/${id}/pharmacy/${action}`, { method: 'POST' })); },
    async pay(id, data) {
      return apply(await request(`/visits/${id}/payment`, {
        method: 'POST', body: { method: data.method || 'Tunai', discount: Number(data.discount || 0) }
      }));
    },
    async stock(id, delta, reason) {
      return apply(await request(`/medicines/${id}/stock`, {
        method: 'PATCH', body: { delta: Number(delta), reason }
      }));
    },
    async referral(id, data) { return apply(await request(`/visits/${id}/referral`, { method: 'POST', body: data })); },
    async updateProfile(data) { return apply(await request('/profile', { method: 'PUT', body: data })); },
    async readNotifications() { return apply(await request('/notifications/read', { method: 'POST' })); },
    async setUserActive(id, active) {
      return apply(await request(`/admin/users/${id}`, { method: 'PATCH', body: { active } }));
    },
    reportUrl() { return `${BASE}/reports.csv`; }
  };

  window.Clinic = api;
})();

