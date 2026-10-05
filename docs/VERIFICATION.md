# Verifikasi lokal — 1 Oktober 2026

## Backend

Perintah: `.venv\Scripts\python -m pytest -q -W error`

Hasil: **21 passed in 101.43s**, tanpa warning.

Kasus mencakup:

- Workflow umum dan BPJS dari booking sampai payment/receipt.
- RBAC, pemilik rekam medis, dokter yang tidak terkait, dan isolasi catatan internal.
- Semua dashboard/halaman operasional, login, register, CSRF.
- Slot unik, dua request booking bersamaan, cancel dan reschedule sebelum screening, verifikasi ulang.
- Nomor antrean dan pencegahan verifikasi/pembayaran ganda.
- Stok tidak negatif, rollback seluruh resep ketika salah satu obat kurang, dan penolakan pengurangan stok berulang.
- Validasi tanda vital, pengingat yang tidak diduplikasi, dan mark notification as read.
- Manajemen dokter/jadwal/obat/pengguna serta penonaktifan akun.
- Persistensi data setelah aplikasi Flask dibuat ulang dengan file database yang sama.

## Browser

Microsoft Edge headless melalui Playwright.

`scripts/browser_check.py`: lulus login lima peran, navigasi mobile, modal receipt, pemilihan slot, tanpa JavaScript error, dan tanpa horizontal overflow pada viewport **375, 768, 1366, 1920 px**.

`scripts/browser_workflow.py`: lulus workflow melalui UI dengan lima browser context terpisah. Booking muncul otomatis di dashboard admin, status pasien diperbarui melalui polling, dokter membuat dua item resep, stok kedua obat berkurang sesuai jumlah, invoice Rp95.000 dibayar, dan kunjungan selesai. Menggunakan database temporer dan port 5001, sehingga tidak mengubah database demo di port 5000.

Screenshot aktual berada di `docs/screenshots/` dan ditautkan dari README.

## Runtime

- Instalasi `requirements.txt` berhasil.
- `pip check`: **No broken requirements found**.
- `seed.py` berhasil; dijalankan ulang tanpa duplikasi/reset data operasional.
- `compileall` berhasil.
- Server lokal berjalan di `http://127.0.0.1:5000`, debug dinonaktifkan.

Pengujian ini membuktikan fungsi lokal yang dicakup kasus di atas; bukan audit keamanan produksi atau integrasi BPJS/payment gateway.
