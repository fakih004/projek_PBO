(function () {
  const C = window.Clinic;
  const V = window.ClinicViews;
  const root = document.querySelector('#app');
  const toastRegion = document.querySelector('#toast-region');

  const parseRoute = () => {
    const raw = location.hash.slice(1) || '/';
    const [path, queryString = ''] = raw.split('?');
    return { path: path || '/', query: new URLSearchParams(queryString) };
  };

  const access = {
    '/dashboard': ['admin','nurse','doctor','pharmacist','patient'],
    '/appointments': ['admin','patient'], '/booking': ['admin','patient'],
    '/patients': ['admin'], '/patient': ['admin'], '/doctors': ['admin'],
    '/visits': ['admin','nurse','doctor','pharmacist','patient'],
    '/visit': ['admin','nurse','doctor','pharmacist','patient'],
    '/medicines': ['admin','pharmacist'], '/reports': ['admin'], '/users': ['admin'],
    '/referrals': ['admin','doctor','patient'], '/profile': ['patient'],
    '/receipt': ['admin','patient'], '/prescription': ['doctor','pharmacist','patient']
  };

  function toast(message, error = false) {
    const node = document.createElement('div');
    node.className = `toast ${error ? 'error' : 'success'}`;
    node.innerHTML = `<span>${V.esc(message)}</span><button aria-label="Tutup">×</button>`;
    node.querySelector('button').onclick = () => node.remove();
    toastRegion.append(node);
    setTimeout(() => node.remove(), 6000);
  }

  function confirmAction(message) {
    const dialog = document.querySelector('#confirm-dialog');
    document.querySelector('#confirm-message').textContent = message;
    return new Promise(resolve => {
      const finish = answer => { dialog.close(); resolve(answer); };
      dialog.querySelector('[data-dialog-confirm]').onclick = () => finish(true);
      dialog.querySelector('[data-dialog-cancel]').onclick = () => finish(false);
      dialog.oncancel = event => { event.preventDefault(); finish(false); };
      dialog.showModal();
    });
  }

  function forbidden() {
    return V.workspace(`<section class="card empty forbidden"><span class="error-code">403</span><h1>Akses tidak diizinkan</h1><p>Halaman ini tidak tersedia untuk peran ${V.esc(C.labels[C.currentUser().role])}.</p><a class="button" href="#/dashboard">Kembali ke dashboard</a></section>`);
  }

  function routeView(route) {
    const user = C.currentUser();
    if (!user) {
      if (route.path === '/login') return V.auth(false);
      if (route.path === '/register') return V.auth(true);
      if (route.path === '/' || route.path.startsWith('/#')) return V.landing();
      location.hash = '#/login';
      return V.auth(false);
    }
    if (['/','/login','/register'].includes(route.path) || route.path.startsWith('/#')) {
      if (route.path === '/') {
        location.hash = '#/dashboard';
        return '';
      }
      location.hash = '#/dashboard';
      return '';
    }
    if (access[route.path] && !access[route.path].includes(user.role)) return forbidden();
    const id = Number(route.query.get('id'));
    switch (route.path) {
      case '/dashboard': return V.dashboard();
      case '/appointments': return V.appointments();
      case '/booking': return V.booking(Number(route.query.get('edit')) || null, Number(route.query.get('patient')) || null);
      case '/patients': return V.patients();
      case '/patient': return V.patientDetail(id);
      case '/visits': return V.visits();
      case '/visit': return canSeeVisit(id) ? V.visit(id) : forbidden();
      case '/doctors': return V.doctors();
      case '/medicines': return V.medicines();
      case '/reports': return V.reports();
      case '/users': return V.users();
      case '/referrals': return V.referrals();
      case '/profile': return V.profile();
      case '/receipt': return canSeeVisit(id) ? V.receipt(id) : forbidden();
      case '/prescription': return canSeeVisit(id) ? V.prescriptionPrint(id) : forbidden();
      default: return V.notFound();
    }
  }

  function canSeeVisit(id) {
    return C.scopedVisits().some(item => item.id === Number(id));
  }

  function render() {
    const route = parseRoute();
    try {
      root.innerHTML = routeView(route);
    } catch (error) {
      console.error(error);
      root.innerHTML = C.currentUser()
        ? V.workspace(`<section class="card empty"><span class="error-code">!</span><h1>Tampilan gagal dimuat</h1><p>${V.esc(error.message || 'Kesalahan frontend tidak dikenal.')}</p><a class="button" href="#/dashboard">Kembali ke dashboard</a></section>`)
        : V.publicShell(`<section class="card empty"><h1>Tampilan gagal dimuat</h1><p>${V.esc(error.message || 'Kesalahan frontend tidak dikenal.')}</p></section>`);
    }
    const workspace = Boolean(root.querySelector('#wrapper'));
    document.body.className = `font-nunito ${workspace ? 'workspace' : ''}`;
    document.title = `${pageTitle(route.path)} · Medika Husada`;
    hydrate(route);
    if (route.path.startsWith('/#')) requestAnimationFrame(() => document.querySelector(`#${CSS.escape(route.path.slice(2))}`)?.scrollIntoView({ behavior: 'smooth' }));
  }

  function pageTitle(path) {
    const names = { '/': 'Klinik Pratama', '/login': 'Masuk', '/register': 'Daftar Pasien', '/dashboard': 'Dashboard', '/appointments': 'Janji Temu', '/booking': 'Buat Janji', '/patients': 'Pasien', '/patient': 'Detail Pasien', '/visits': 'Kunjungan', '/visit': 'Detail Kunjungan', '/doctors': 'Dokter', '/medicines': 'Farmasi', '/reports': 'Laporan', '/users': 'Pengguna', '/referrals': 'Rujukan', '/profile': 'Profil', '/receipt': 'Bukti Pelayanan', '/prescription': 'Resep' };
    return names[path] || 'Medika Husada';
  }

  function hydrate(route) {
    if (route.path === '/booking') updateSlots().catch(error => toast(error.message, true));
    const nursing = document.querySelector('[data-form="nursing"]');
    nursing?.querySelectorAll('[name="weight"],[name="height"]').forEach(input => input.addEventListener('input', updateBmi));
    document.querySelectorAll('[data-table-search]').forEach(input => input.addEventListener('input', filterTable));
  }

  function formData(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  async function updateSlots() {
    const form = document.querySelector('[data-form="booking"]');
    if (!form) return;
    const doctorId = form.elements.doctorId.value;
    const date = form.elements.date.value;
    const current = form.elements.time.value;
    const editId = Number(form.dataset.editId) || null;
    const container = form.querySelector('[data-slots]');
    container.innerHTML = '<p class="slot-empty">Memuat slot dari serverâ€¦</p>';
    const slots = await C.slots(doctorId, date, editId);
    form.querySelector('[data-slot-label]').textContent = date ? new Date(`${date}T12:00:00`).toLocaleDateString('id-ID', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) : 'Pilih tanggal';
    container.innerHTML = slots.length ? slots.map(slot => `<button type="button" class="slot ${slot.time === current ? 'selected' : ''}" data-slot="${slot.time}" ${slot.available || slot.time === current ? '' : 'disabled'}>${slot.time}</button>`).join('') : '<p class="slot-empty">Tidak ada praktik pada tanggal ini. Pilih tanggal lain.</p>';
  }

  function updateBmi() {
    const form = document.querySelector('[data-form="nursing"]');
    const weight = Number(form.elements.weight.value), height = Number(form.elements.height.value);
    form.querySelector('[data-bmi]').textContent = weight > 0 && height > 0 ? `BMI ${(weight / ((height / 100) ** 2)).toFixed(1)}` : 'BMI —';
  }

  function filterTable(event) {
    const needle = event.target.value.toLowerCase();
    event.target.closest('.card').querySelectorAll('[data-search-table] tbody tr').forEach(row => { row.hidden = !row.textContent.toLowerCase().includes(needle); });
  }

  async function submitForm(form) {
    const data = formData(form);
    const kind = form.dataset.form;
    try {
      if (kind === 'login') {
        await C.login(data.email, data.password); location.hash = '#/dashboard'; render(); toast('Berhasil masuk.');
      } else if (kind === 'register') {
        await C.register(data); location.hash = '#/dashboard'; render(); toast('Akun pasien berhasil dibuat.');
      } else if (kind === 'booking') {
        const appointment = await C.book(data, Number(form.dataset.editId) || null); location.hash = '#/appointments'; render(); toast(`Janji #${appointment.id} tersimpan dan menunggu verifikasi.`);
      } else if (kind === 'nursing') {
        await C.nursing(form.dataset.id, data); render(); toast('Pemeriksaan awal disimpan dan pasien dikirim ke dokter.');
      } else if (kind === 'examination') {
        await C.examine(form.dataset.id, data); render(); toast('Pemeriksaan dokter selesai.');
      } else if (kind === 'referral') {
        await C.referral(form.dataset.id, data); render(); toast('Surat rujukan diterbitkan.');
      } else if (kind === 'payment') {
        if (!await confirmAction('Konfirmasi pembayaran? Transaksi selesai tidak dapat dibayar ulang.')) return;
        await C.pay(form.dataset.id, data); render(); toast('Pembayaran berhasil dikonfirmasi.');
      } else if (kind === 'stock') {
        await C.stock(form.dataset.id, data.delta, data.reason); render(); toast('Stok berhasil diperbarui.');
      } else if (kind === 'profile') {
        await C.updateProfile(data); render(); toast('Profil berhasil disimpan.');
      }
    } catch (error) { toast(error.message || 'Perubahan gagal disimpan.', true); }
  }

  async function handleAction(button) {
    const action = button.dataset.action;
    const id = Number(button.dataset.id);
    try {
      if (action === 'logout') { C.logout(); location.hash = '#/login'; render(); return; }
      if (action === 'read-notifications') { await C.readNotifications(); render(); toast('Semua notifikasi ditandai dibaca.'); return; }
      if (action === 'reset-demo') {
        if (!await confirmAction('Reset seluruh perubahan dan kembalikan data demo awal?')) return;
        await C.reset(); render(); toast(C.remote ? 'Data server berhasil dimuat ulang.' : 'Data demo berhasil direset.'); return;
      }
      if (action === 'verify-appointment') {
        if (!await confirmAction('Verifikasi janji dan buat nomor antrean?')) return;
        await C.verifyAppointment(id); render(); toast('Janji terverifikasi dan antrean dibuat.');
      } else if (action === 'reject-appointment') {
        if (!await confirmAction('Tolak janji temu ini?')) return;
        await C.cancelAppointment(id, true); render(); toast('Janji ditolak.');
      } else if (action === 'cancel-appointment') {
        if (!await confirmAction('Batalkan janji dan lepaskan slot?')) return;
        await C.cancelAppointment(id); render(); toast('Janji dibatalkan.');
      } else if (action === 'queue') {
        await C.queue(id, button.dataset.value); render(); toast('Status antrean diperbarui.');
      } else if (action === 'start-exam') {
        if (!await confirmAction('Mulai pemeriksaan pasien ini?')) return;
        await C.startExam(id); render(); toast('Pemeriksaan dimulai.');
      } else if (action === 'pharmacy') {
        const names = { start: 'Mulai meracik resep?', ready: 'Tandai obat siap dan kurangi stok?', handover: 'Serahkan obat dan buat invoice?', shortage: 'Laporkan stok tidak cukup?' };
        if (!await confirmAction(names[button.dataset.value])) return;
        await C.pharmacy(id, button.dataset.value); render(); toast('Status farmasi diperbarui.');
      } else if (action === 'export-report') exportReport();
      else if (action === 'print') window.print();
    } catch (error) { toast(error.message || 'Tindakan gagal.', true); }
  }

  function exportReport() {
    const rows = [['Invoice','Pasien','Tanggal','Metode','Dibayar']];
    C.state.visits.filter(item => item.invoice && item.invoice.status !== 'UNPAID').forEach(visit => {
      const appointment = C.appointment(visit.appointmentId);
      rows.push([visit.invoice.number, C.patientName(appointment.patientId), appointment.date, visit.invoice.method, visit.invoice.payable]);
    });
    const csv = rows.map(row => row.map(value => `"${String(value).replaceAll('"','""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = `laporan-medika-${C.today()}.csv`; link.click(); URL.revokeObjectURL(url);
    toast('Laporan CSV berhasil dibuat.');
  }

  document.addEventListener('submit', event => {
    const form = event.target.closest('[data-form]');
    if (!form) return;
    event.preventDefault();
    submitForm(form);
  });

  document.addEventListener('change', async event => {
    if (event.target.matches('[data-role-switch]')) {
      try { const user = await C.switchRole(event.target.value); location.hash = '#/dashboard'; render(); toast(`Mode demo: ${user.name}`); } catch (error) { toast(error.message, true); }
    }
    if (event.target.matches('[data-form="booking"] [name="doctorId"], [data-form="booking"] [name="date"]')) {
      const form = event.target.closest('form'); form.elements.time.value = ''; updateSlots().catch(error => toast(error.message, true));
    }
    if (event.target.matches('[data-user-active]')) {
      const user = C.user(event.target.dataset.userActive);
      try { await C.setUserActive?.(user.id, event.target.checked) ?? C.save(); render(); toast(`Akun ${user.name} ${event.target.checked ? 'diaktifkan' : 'dinonaktifkan'}.`); }
      catch (error) { event.target.checked = user.active; toast(error.message, true); }
    }
  });

  document.addEventListener('click', async event => {
    const action = event.target.closest('[data-action]');
    if (action) { event.preventDefault(); handleAction(action); return; }
    const quick = event.target.closest('[data-quick-login]');
    if (quick) {
      try { const user = await C.switchRole(quick.dataset.quickLogin); location.hash = '#/dashboard'; render(); toast(`Masuk sebagai ${user.name}.`); }
      catch (error) { toast(error.message, true); }
      return;
    }
    const slot = event.target.closest('[data-slot]');
    if (slot) { const form = slot.closest('form'); form.querySelectorAll('[data-slot]').forEach(item => item.classList.remove('selected')); slot.classList.add('selected'); form.elements.time.value = slot.dataset.slot; return; }
    const password = event.target.closest('[data-password]');
    if (password) { const input = password.parentElement.querySelector('input'); input.type = input.type === 'password' ? 'text' : 'password'; password.textContent = input.type === 'password' ? 'Lihat' : 'Sembunyikan'; return; }
    if (event.target.closest('[data-menu-toggle]')) { document.querySelector('#left-sidebar')?.classList.toggle('open'); return; }
    if (event.target.closest('[data-menu-close]')) { document.querySelector('#left-sidebar')?.classList.remove('open'); return; }
    if (event.target.closest('[data-public-menu]')) { document.querySelector('#public-menu')?.classList.toggle('open'); return; }
    if (event.target.closest('[data-notification-toggle]')) { const panel = document.querySelector('[data-notification-panel]'); panel.hidden = !panel.hidden; return; }
    const sidebar = document.querySelector('#left-sidebar');
    if (sidebar?.classList.contains('open') && !sidebar.contains(event.target) && !event.target.closest('[data-menu-toggle]')) sidebar.classList.remove('open');
  });

  window.addEventListener('hashchange', render);
  async function boot() {
    try { await C.ready?.(); }
    catch (error) { toast(error.message, true); }
    const demoRole = new URLSearchParams(location.search).get('demo');
    if (['admin','nurse','doctor','pharmacist','patient'].includes(demoRole)) {
      try {
        await C.switchRole(demoRole);
        if (!location.hash || location.hash === '#/') location.hash = '#/dashboard';
      } catch (error) { toast(error.message, true); }
    }
    if (!location.hash) location.hash = '#/';
    render();
  }
  boot();
})();
