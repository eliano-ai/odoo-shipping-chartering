# Sprint 25 — vessel_bunker_management: ROB Reconciliation (Inti Anti-Fraud)

**Modul disentuh:** `vessel_bunker_management`
**Depends on:** Sprint 24 (BDN/delivery dengan `qty_confirmed_mt`)

## Konteks
Bagian paling kompleks tech spec (§2.4, §3.6, §4.3) — menyilangkan supply (BDN), consumption (`fleet_fuel_log`), dan ROB aktual (noon report) dalam satu rekonsiliasi. Ikuti saran §12.2 poin 7: pecah compute jadi method terpisah per komponen, supaya mudah di-unit-test satu-satu (pola sama seperti `_compute_allocated_cost` modular di `vessel_voyage_pnl` Sprint 17).

## Tasks

1. Model `vessel.bunker.rob.reconciliation` (§3.6) — `voyage_id`, `noon_report_start_id`/`noon_report_end_id` (M2O `vessel.noon.report`, approved, constraint `end.report_datetime > start.report_datetime`, keduanya milik `voyage_id` yang sama), `fuel_type` (Selection fo/do), `previous_rob`/`actual_rob` (related dari noon report `rob_fo`/`rob_do` — **cek dulu field real di `vessel.noon.report`**, jangan asumsi nama persis), `total_supply` (compute, method terpisah `_compute_total_supply`), `total_consumption` (compute, method terpisah `_compute_total_consumption`), `expected_rob` (compute, method terpisah `_compute_expected_rob`), `variance`/`variance_pct` (compute store), `threshold_pct` (default dari `res.company.default_bunker_variance_threshold_pct` **atau** override `fleet.vehicle.bunker_variance_threshold_pct` Sprint 22 — pola threshold-with-override), `is_anomaly` (compute store), `state` (draft/reviewed/flagged), `review_notes`
2. `_compute_total_supply` — sum `qty_confirmed_mt` dari `vessel.bunker.delivery` (state=confirmed) berdasar `fuel_type` yang match, dalam rentang `delivery_datetime` antara T1-T2, untuk `voyage_id` yang sama (via `inquiry_id.voyage_id`)
3. `_compute_total_consumption` — sum dari `fleet.fuel.log` (state approved/posted) berdasar `fuel_type_id` yang match `fuel_type` field ini, dan `trip_id`/analytic voyage yang sesuai dalam rentang waktu T1-T2 — **cek dulu bridge yang sudah dipakai `vessel_voyage_pnl` Sprint 16** (`voyage.fleet_trip_id`) untuk pola query yang konsisten, reuse pendekatan yang sama
4. `_compute_expected_rob` — `previous_rob + total_supply - total_consumption`. **Unit test SEGERA setelah tiap method selesai** (bukan sekaligus di akhir) — 3 method compute terpisah = 3 test case minimal
5. Tombol **"Review"** (draft→reviewed, Operations) dan **"Flag untuk Investigasi"** (→flagged, kalau `is_anomaly=True` dan Operations menganggap perlu tindak lanjut serius, bukan sekadar noise)
6. `_cron_generate_rob_reconciliation` (§4.3, §4.5, harian) — auto-create record untuk pasangan noon report approved berurutan pada voyage `sailing`/`at_port` yang belum punya reconciliation. **Cross-check dulu apakah `vessel.noon.report` sudah punya mail.thread/mail.activity.mixin** sebelum reconciliation model ini manggil `activity_schedule` (perlu `mail.activity.mixin` di `vessel.bunker.rob.reconciliation` sendiri, bukan di noon report — pastikan `_inherit` benar SEBELUM implementasi cron ini, bukan sesudah)
7. Extend `vessel.voyage`: `bunker_delivery_ids` (One2many via `inquiry_id.voyage_id`), `rob_reconciliation_ids` (One2many), `rob_anomaly_count` (compute, smart button)
8. Extend `fleet.vehicle`: `rob_reconciliation_ids` (One2many, melalui voyage — cek pendekatan: mungkin perlu related/compute karena bukan direct FK)
9. Security access untuk `vessel.bunker.rob.reconciliation`
10. Views: form dengan panel ringkas selalu terlihat (previous ROB → supply → consumption → expected vs actual, indikator warna hijau/kuning/merah sesuai `variance_pct` vs `threshold_pct`), list filter "Anomaly Alert" (`is_anomaly=True`)
11. Dummy data: replikasi **persis** §10.5 acceptance criteria — previous ROB 200 MT, supply 495 MT (dari delivery Sprint 24), consumption 150 MT (perlu demo fuel log baru kalau belum cukup) → expected ROB 545 MT, noon report aktual 500 MT → variance −45 MT, `is_anomaly=True` (threshold default 8%, variance_pct = 45/545 ≈ 8.26% > 8%)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_bunker_management 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_bunker_management -u vessel_bunker_management 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

Cross-check §10.5 SAAT INI — jangan tunda ke sprint terakhir (pelajaran retro `vessel_voyage_pnl`: cross-check acceptance criteria yang kompleks di sprint yang sama, bukan ditunda).

## Definition of Done
- [ ] §10.5 acceptance criteria terpenuhi persis (200+495-150=545 expected, actual 500, variance -45, is_anomaly=True di threshold 8%)
- [ ] 3 compute method (`_compute_total_supply`/`_compute_total_consumption`/`_compute_expected_rob`) masing-masing punya unit test terpisah
- [ ] Cron `_cron_generate_rob_reconciliation` jalan tanpa error via shell manual, idempotent (tidak duplikat reconciliation untuk pasangan noon report yang sama)
- [ ] Threshold override per-kapal bekerja (beda hasil dibanding pakai default global)
- [ ] Idempotent, install bersih, tidak ada regresi Sprint 22-24
