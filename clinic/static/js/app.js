/* UI only: every clinical change is persisted by authenticated Python endpoints. */
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const toast = (message, error = false) => {
  const node = document.createElement('div'); node.className = `toast ${error ? 'error' : 'success'}`;
  const text = document.createElement('span'); text.textContent = message;
  const close = document.createElement('button'); close.textContent = '×'; close.setAttribute('aria-label', 'Tutup notifikasi');
  close.onclick = () => node.remove(); node.append(text, close); document.querySelector('#toasts').append(node);
  setTimeout(() => node.remove(), 10000);
};
document.querySelectorAll('[data-dismiss]').forEach(b => b.onclick = () => b.parentElement.remove());
document.querySelector('#menu-toggle')?.addEventListener('click', e => {
  const opened = document.querySelector('#left-sidebar').classList.toggle('open');
  e.currentTarget.setAttribute('aria-expanded', String(opened));
});
document.querySelector('#left-sidebar .sidebar-close')?.addEventListener('click', () => {
  document.querySelector('#left-sidebar').classList.remove('open');
  document.querySelector('#menu-toggle')?.setAttribute('aria-expanded', 'false');
});
document.querySelector('#public-menu-toggle')?.addEventListener('click', e => {
  const opened = document.querySelector('#public-menu').classList.toggle('open');
  e.currentTarget.setAttribute('aria-expanded', String(opened));
});
document.addEventListener('click', e => {
  const sidebar = document.querySelector('#left-sidebar');
  if (sidebar?.classList.contains('open') && !sidebar.contains(e.target) && !e.target.closest('#menu-toggle')) {
    sidebar.classList.remove('open'); document.querySelector('#menu-toggle')?.setAttribute('aria-expanded', 'false');
  }
  const publicMenu = document.querySelector('#public-menu');
  if (publicMenu?.classList.contains('open') && !publicMenu.contains(e.target) && !e.target.closest('#public-menu-toggle')) {
    publicMenu.classList.remove('open'); document.querySelector('#public-menu-toggle')?.setAttribute('aria-expanded', 'false');
  }
  if (e.target.closest('[data-password]')) {
    const button = e.target.closest('[data-password]'), input = button.parentElement.querySelector('input');
    input.type = input.type === 'password' ? 'text' : 'password'; button.textContent = input.type === 'password' ? 'Lihat' : 'Sembunyikan';
  }
  if (e.target.closest('[data-print]')) window.print();
  if (e.target.closest('[data-remove-medicine]')) e.target.closest('.prescription-row').remove();
  const receipt = e.target.closest('[data-receipt]');
  if (receipt) { e.preventDefault(); document.querySelector('#receipt-frame').src = receipt.href + '?embedded=1'; document.querySelector('#receipt-dialog').showModal(); }
  if (e.target.closest('[data-close-dialog]')) e.target.closest('dialog').close();
});
document.querySelectorAll('[data-bpjs-toggle]').forEach(toggle => toggle.addEventListener('change', () => {
  const field = toggle.closest('form').querySelector('[data-bpjs-field]'); field.hidden = !toggle.checked;
  field.querySelector('input').required = toggle.checked;
}));
document.querySelector('#add-medicine')?.addEventListener('click', () => {
  document.querySelector('#prescription-items').append(document.querySelector('#medicine-template').content.cloneNode(true));
});
const confirmAction = message => new Promise(resolve => {
  const dialog = document.querySelector('#confirm-dialog'); document.querySelector('#confirm-message').textContent = message;
  const done = answer => { dialog.oncancel = null; dialog.close(); resolve(answer); };
  document.querySelector('#confirm-yes').onclick = () => done(true);
  document.querySelector('#confirm-cancel').onclick = () => done(false);
  dialog.oncancel = e => { e.preventDefault(); done(false); }; dialog.showModal();
});
async function refreshDashboard() {
  const target = document.querySelector('#live-dashboard'); if (!target) return;
  if (document.querySelector('dialog[open]') || target.contains(document.activeElement)) return;
  const response = await fetch(target.dataset.pollUrl, { headers: { 'Accept': 'text/html' } });
  if (!response.ok || response.redirected) throw new Error('Sesi berakhir atau koneksi terganggu. Silakan masuk kembali.');
  const html = await response.text();
  if (target.innerHTML !== html) target.innerHTML = html;
}
document.addEventListener('submit', async e => {
  const form = e.target; if ((form.getAttribute('method') || 'get').toLowerCase() !== 'post' || form.dataset.submitting) return;
  e.preventDefault();
  if (form.dataset.confirm && !(await confirmAction(form.dataset.confirm))) return;
  form.dataset.submitting = '1'; const data = new FormData(form);
  const buttons = [...form.querySelectorAll('button[type="submit"],button:not([type])')];
  const labels = buttons.map(b => b.textContent); buttons.forEach(b => { b.disabled = true; b.textContent = 'Menyimpan…'; });
  if (!form.hasAttribute('data-ajax')) { HTMLFormElement.prototype.submit.call(form); return; }
  try {
    const response = await fetch(form.action, { method: 'POST', body: data, headers: { 'X-Requested-With': 'fetch', 'X-CSRFToken': csrf } });
    if (response.redirected) throw new Error('Sesi berakhir. Silakan masuk kembali.');
    const result = await response.json(); if (!response.ok) throw new Error(result.message || 'Perubahan gagal disimpan.');
    toast(result.message); await refreshDashboard();
  } catch (err) { toast(err.message || 'Koneksi terganggu. Coba lagi.', true); }
  finally { delete form.dataset.submitting; buttons.forEach((b, i) => { b.disabled = false; b.textContent = labels[i]; }); }
});
const booking = document.querySelector('.booking-form');
if (booking) {
  let controller;
  const loadSlots = async () => {
    controller?.abort(); controller = new AbortController();
    const date = booking.querySelector('[name=date]').value, doctor = booking.querySelector('[name=doctor_id]').value;
    const container = document.querySelector('#slots'); container.textContent = 'Memuat slot…';
    document.querySelector('#booking-time').value = ''; document.querySelector('#booking-submit').disabled = true;
    if (!date) return;
    const formatted = new Date(`${date}T12:00:00`).toLocaleDateString('id-ID', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    document.querySelector('#booking-date-label').textContent = formatted;
    try {
      const response = await fetch(`/api/slots?doctor_id=${encodeURIComponent(doctor)}&date=${encodeURIComponent(date)}`, { signal: controller.signal });
      if (!response.ok) throw new Error('Tidak dapat memuat jadwal.');
      const data = await response.json(); container.replaceChildren();
      if (!data.slots.length) container.textContent = 'Tidak ada praktik pada tanggal ini. Silakan pilih tanggal lain.';
      data.slots.forEach(slot => {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'slot'; button.textContent = slot.time;
        button.disabled = !slot.available; button.title = slot.available ? 'Pilih slot ini' : 'Slot penuh atau sudah lewat';
        button.onclick = () => { container.querySelectorAll('.slot').forEach(b => b.classList.remove('selected')); button.classList.add('selected'); document.querySelector('#booking-time').value = slot.time; document.querySelector('#booking-submit').disabled = false; };
        container.append(button);
      });
    } catch (err) { if (err.name !== 'AbortError') { container.textContent = 'Gagal memuat jadwal. Ubah tanggal untuk mencoba kembali.'; toast(err.message, true); } }
  };
  booking.querySelector('[name=date]').addEventListener('change', loadSlots); booking.querySelector('[name=doctor_id]').addEventListener('change', loadSlots); loadSlots();
}
document.querySelectorAll('[name=weight],[name=height]').forEach(input => input.addEventListener('input', () => {
  const weight = Number(document.querySelector('[name=weight]').value), height = Number(document.querySelector('[name=height]').value);
  document.querySelector('#bmi-preview').textContent = weight > 0 && height > 0 ? `BMI ${(weight / (height / 100) ** 2).toFixed(1)}` : 'BMI —';
}));
let latestNotification = null, pollingFailed = false;
async function poll() {
  if (document.hidden || !document.querySelector('#notification-toggle')) return;
  try {
    const response = await fetch('/api/notifications'); if (!response.ok || response.redirected) throw new Error('Koneksi atau sesi terputus.');
    const data = await response.json(); document.querySelector('#notification-count').textContent = data.unread;
    const list = document.querySelector('#notification-list'); list.replaceChildren();
    if (!data.items.length) list.textContent = 'Belum ada notifikasi.';
    data.items.forEach(n => {
      const item = document.createElement('div'); item.className = `notification-item ${n.read ? '' : 'unread'}`; item.textContent = n.message;
      const time = document.createElement('small'); time.textContent = new Date(n.time).toLocaleString('id-ID'); item.append(time); list.append(item);
    });
    if (latestNotification !== null) data.items.filter(n => n.id > latestNotification).reverse().forEach(n => toast(n.message));
    latestNotification = Math.max(latestNotification || 0, ...data.items.map(n => n.id));
    await refreshDashboard(); pollingFailed = false;
  } catch (err) { if (!pollingFailed) toast('Pembaruan otomatis tertunda. Periksa koneksi atau masuk kembali.', true); pollingFailed = true; }
}
document.querySelector('#notification-toggle')?.addEventListener('click', e => {
  const panel = document.querySelector('#notification-panel'); panel.hidden = !panel.hidden; e.currentTarget.setAttribute('aria-expanded', String(!panel.hidden));
});
document.querySelector('#read-notifications')?.addEventListener('click', async () => {
  try { const response = await fetch('/api/notifications/read', { method: 'POST', headers: { 'X-CSRFToken': csrf } }); if (!response.ok || response.redirected) throw new Error(); await poll(); }
  catch { toast('Tidak dapat menandai notifikasi. Coba lagi.', true); }
});
poll(); setInterval(poll, 5000);
