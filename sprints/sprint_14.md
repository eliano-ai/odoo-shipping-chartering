# Sprint 14 — vessel_voyage_operations: Views Polish, OWL/Leaflet Dashboard & Acceptance Final

**Modul disentuh:** `vessel_voyage_operations`
**Depends on:** Sprint 8-13 (semua model & workflow)

## Konteks
Sprint penutup — sesuai §5 spec & §12.2 poin 10, dashboard peta dikerjakan **paling akhir** karena paling kompleks & tidak blocking modul lain. User eksplisit minta ikut spec penuh (bukan fallback list) — bangun OWL component asli dengan Leaflet.

## Keputusan Implementasi Dashboard (perlu keputusan teknis sebelum mulai — bukan pertanyaan bisnis, tapi catat di sini)
**Leaflet library harus di-vendor sebagai static asset lokal** (bukan CDN eksternal) — konsisten dengan environment Docker self-hosted, hindari dependency ke internet saat runtime produksi. Download Leaflet JS+CSS (versi stabil terbaru, cek lisensi BSD-2-Clause compatible dengan LGPL-3 modul), taruh di `static/lib/leaflet/`.

## Tasks

1. **Vendor Leaflet**: download `leaflet.js`+`leaflet.css` (+ marker icon assets) ke `vessel_voyage_operations/static/lib/leaflet/`, daftarkan di manifest `assets` (`web.assets_backend`)
2. **OWL Component** `static/src/js/dashboard_map.js` — component baca data `fleet.vehicle` (search `is_vessel=True`, ambil `current_position_lat/lng`, `name`, `charter_status`), render marker Leaflet per kapal, warna marker beda sesuai `charter_status` (available/on_voyage_charter/on_time_charter/chartered_in — 4 warna beda)
3. **QWeb template** `static/src/xml/dashboard_map.xml` — container div untuk map, popup per marker (nama kapal, status, posisi terakhir + timestamp noon report)
4. **SCSS** `static/src/scss/dashboard_map.scss` — styling container map (height, border, dsb) + custom marker icon warna
5. Register sebagai `ir.actions.client` (tag custom, misal `vessel_voyage_operations.fleet_map_dashboard`) — daftarkan component di action registry sesuai pola OWL client action Odoo 19 (rujuk skill `odoo-19` untuk pattern actions & OWL frontend components kalau perlu detail API)
6. Menu Laporan → Dashboard Posisi Armada, action ke client action di atas
7. **Laporan Delay Analysis** (sudah dibuat Sprint 13, cek lagi views/menu-nya lengkap sesuai §5: pivot delay type × kapal × durasi)
8. Polish semua views yang masih minim dari sprint sebelumnya — pastikan smart button di form voyage (Port Calls, Noon Reports, Cargo Documents, Delays, ke Kontrak Charter) semua count real bukan placeholder
9. **Jalankan seluruh 11 poin Kriteria Penerimaan §10 tech spec** satu per satu, catat hasil per poin di `SPRINT_REPORT.md` (pola sama seperti Sprint 7 `vessel_chartering`)
10. **Audit checklist §12.2 poin 12** — grep manual:
    - `grep -rn "display_name = fields" vessel_voyage_operations/` (harus 0)
    - `grep -rn "fields.Datetime.from_string" vessel_voyage_operations/` (harus 0)
    - `grep -rn "@api.depends()" vessel_voyage_operations/models/` (harus 0)
    - `grep -rn "decoration-secondary" vessel_voyage_operations/` (harus 0 — pelajaran retro Sprint 1-7)
    - Cek semua baris `ir.model.access.csv` prefix `vessel_voyage_operations_`
    - Install ulang dari database bersih dengan `--test-enable` untuk pastikan zero-install-error bareng 7 modul lain (5 fleet + `vessel_chartering` + `vessel_voyage_operations` sendiri)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_operations 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_voyage_operations -u vessel_voyage_operations 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

Manual (browser, karena OWL component tidak bisa diverifikasi via shell/curl): buka Dashboard Posisi Armada, cek marker muncul sesuai `current_position_lat/lng` dummy data, warna beda per `charter_status` (acceptance criteria §10.9).

## Definition of Done — Checklist Acceptance Criteria §10 Tech Spec (jalankan semua)
- [ ] §10.1 Install bersih Odoo 19 tanpa error, tanpa konflik `vessel_chartering` & 5 modul fleet existing
- [ ] §10.2 Voyage dari kontrak confirmed → vessel_id & analytic_account_id ter-copy otomatis
- [ ] §10.3 3 port call berurutan, ETA/ATA beda → tidak error, urutan benar
- [ ] §10.4 Nakhoda portal cuma lihat voyage kapal sendiri
- [ ] §10.5 Approve noon report → read-only, masuk total_distance_nm
- [ ] §10.6 Noon report rejected → histori tidak hilang, bisa resubmit
- [ ] §10.7 PDA 5 line + FDA +20% → variance benar, activity ke Finance
- [ ] §10.8 Selesaikan voyage tanpa atd salah satu port call → block dengan pesan jelas
- [ ] §10.9 Dashboard posisi armada tampilkan kapal sesuai noon report approved terakhir (**verifikasi manual browser**, bukan otomatis)
- [ ] §10.10 Semua unit test TransactionCase (total_distance_nm, variance_amount, duration_hours) lulus
- [ ] §10.11 Audit: no display_name custom field, no fields.Datetime.from_string, no @api.depends() kosong

**Kalau semua 11 poin lulus → MVP `vessel_voyage_operations` selesai.**
