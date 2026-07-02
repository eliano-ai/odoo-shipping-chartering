# Sprint 3 — Voyage Estimate

**Modul disentuh:** `vessel_chartering`
**Depends on:** Sprint 2 (`vessel.charter.contract`)

## Konteks
Pre-fixture estimate (§3.3) — alat bantu keputusan sebelum kontrak dikonfirmasi, multi-revisi per kontrak, termasuk kalkulasi bunker dual-currency dan TCE (Time Charter Equivalent).

## Tasks

1. Model `vessel.voyage.estimate` — semua field §3.3: identitas (contract_id, name revisi EST-001/EST-002), jarak & kecepatan (distance_nm, speed_knots, sea_days compute-editable-override, port_days_load/discharge, total_voyage_days compute), bunker section (fo/do consumption sea&port, fo/do price USD, usd_rate default dari `res.currency.rate` hari ini tapi editable, bunker_cost_usd & bunker_cost_idr compute), cost lain (port_cost_estimate, other_cost_estimate, charter_in_cost untuk skenario relet), hasil (revenue_estimate dari kontrak, voyage_result, tce_per_day), state (draft/selected)
2. Business rule: hanya 1 estimate per kontrak yang boleh `state='selected'` — constraint atau otomatis un-select yang lain saat satu dipilih
3. Compute `usd_rate` default: ambil dari `res.currency.rate` untuk currency USD tanggal hari ini (fallback ke rate terakhir jika tidak ada rate hari ini)
4. Views: form estimate (grouped by section sesuai field di atas), list view dengan kolom ringkas (name, total_voyage_days, revenue_estimate, voyage_result, tce_per_day, state), smart button "Estimates" di form kontrak (isi count asli, bukan 0 lagi)
5. Tombol "Buat Estimate Baru" dari form kontrak — auto-fill `revenue_estimate` dari kontrak terkait, auto-increment nomor revisi
6. Tombol "Pilih sebagai Baseline" (set state='selected', un-select lainnya)
7. Dummy data: 2 estimate untuk salah satu kontrak voyage charter dummy dari Sprint 2 (1 revisi awal, 1 revisi revisi dengan bunker price lebih tinggi — ilustrasi kenapa perlu multi-revisi)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_chartering 2>&1 | grep -E "ERROR|CRITICAL"
```

Manual check via UI (screenshot atau describe hasil): buka salah satu kontrak dummy, klik smart button Estimates, pastikan 2 revisi muncul, `tce_per_day` masuk akal (revenue - cost, dibagi voyage days).

## Definition of Done
- [ ] Model & compute sesuai §3.3, tidak ada `@api.depends` kosong
- [ ] `usd_rate` default terisi otomatis dari `res.currency.rate`, tetap editable manual
- [ ] Hanya 1 estimate per kontrak berstatus `selected` pada satu waktu
- [ ] Smart button di form kontrak menampilkan count & list estimate yang benar
- [ ] Dummy data 2 revisi ter-load, angka TCE masuk akal (bukan 0 atau negatif tak wajar)
