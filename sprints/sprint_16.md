# Sprint 16 — vessel_voyage_pnl: Core P&L Model (Revenue & Direct Cost)

**Modul disentuh:** `vessel_voyage_pnl`
**Depends on:** Sprint 15 (foundation, master data)

## Konteks
Model inti `vessel.voyage.pnl` (§3.2) + `vessel.voyage.pnl.line` (§3.3) — bagian revenue & direct cost dulu (paling sederhana, sumbernya jelas dari `vessel_chartering`/`vessel_voyage_operations`), allocated cost menyusul Sprint 17 (paling kompleks, sesuai saran urutan §12.2 poin 3 tech spec: jangan sekaligus).

## Tasks

1. Model `vessel.voyage.pnl` — field §3.2 bagian Umum + Revenue + Direct Cost: `voyage_id` (M2O `vessel.voyage`, required unique, domain state=completed), `contract_id`/`vessel_id`/`analytic_account_id` (related dari voyage_id, store), `estimate_id` (M2O `vessel.voyage.estimate`, auto-set dari estimate `selected` milik contract_id), `voyage_days` (compute store, dari `date_arrival_final - date_departure`), field revenue (`freight_revenue`/`demurrage_revenue`/`despatch_cost`/`brokerage_cost`/`other_revenue`/`total_revenue`, semua compute+store kecuali `other_revenue` manual), field direct cost (`bunker_cost`/`port_cost`/`cargo_handling_cost`/`insurance_voyage_cost`/`other_direct_cost`/`total_direct_cost`), `state` (draft/computed/locked), `currency_id` (default company currency)
2. Model `vessel.voyage.pnl.line` — §3.3: `pnl_id`, `cost_category_id`, `category_group` (related), `source_model`/`source_res_id` (traceability generik), `description`, `amount` (positif revenue, negatif cost — konvensi tanda konsisten), `is_allocated`, `allocation_rule_id`, `is_manual_adjustment`
3. **Compute Revenue** (§2.2) — `_compute_revenue()`: query `account.move.line` dengan `analytic_distribution` mengandung `analytic_account_id` (plan Voyage) milik voyage ini, filter by product category — `freight_revenue` dari invoice terkait `vessel_chartering.product_freight_revenue`, `demurrage_revenue`/`despatch_cost` dari `vessel_chartering.product_demurrage` (pisahkan sign positif/negatif), `brokerage_cost` = `brokerage_pct × freight_amount_final` dari `contract_id`. Buat `line_ids` per item dengan traceability ke `account.move.line` id asal. **Tulis unit test SEGERA setelah compute ini selesai** (jangan lanjut ke direct cost dulu) — pakai data dari `_create_freight_invoice`/`_create_demurrage_invoice` pola `vessel_chartering` test
4. **Compute Direct Cost** (§2.2) — `_compute_direct_cost()`: `bunker_cost` dari `fleet_fuel_log` (query `account.move.line` linked ke `fleet.vehicle.trip` = `voyage.fleet_trip_id` kalau ada bridge, atau fallback filter analytic voyage langsung — **cek dulu struktur real `fleet_fuel_log`'s account.move.line linkage sebelum implementasi, jangan asumsi**), `port_cost` dari `vessel.port.disbursement` type=fda state=confirmed per `port_call_id.voyage_id`, `cargo_handling_cost`/`insurance_voyage_cost` dari `account.move.line` yang dikategorikan manual via mapping `vessel.pnl.cost.category.default_account_ids`. Tulis unit test segera setelah ini juga, terpisah dari test revenue
5. Tombol **"Generate P&L"** di form `vessel.voyage` (extend model, smart button `pnl_id`) — muncul saat `state=completed` dan belum punya `pnl_id`, create `vessel.voyage.pnl` state draft, panggil `_compute_revenue()` + `_compute_direct_cost()`, set `state='computed'`. Tombol **"Recompute"** — aktif saat state in (draft, computed), replace `line_ids` non-manual (adjustment manual dipertahankan)
6. Extend `fleet.vehicle`: `voyage_pnl_ids` (One2many), `vessel_pnl_ids` (placeholder kosong, diisi Sprint 18)
7. Security access untuk `vessel.voyage.pnl` & `vessel.voyage.pnl.line`
8. Views: form P&L (header ringkasan revenue/cost, notebook Revenue Detail/Direct Cost Detail dengan `line_ids` inline read-only), list, smart button di form voyage ke P&L, menu Voyage P&L → Semua Voyage P&L
9. Dummy data: generate P&L untuk 1-2 voyage completed yang sudah ada demo data lengkap (freight invoice + demurrage/port disbursement) — pilih yang datanya paling representatif dari `vessel_chartering`/`vessel_voyage_operations` demo

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_pnl 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_voyage_pnl -u vessel_voyage_pnl 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

Cross-check acceptance criteria §10.2 tech spec SAAT INI (jangan tunda): voyage completed dengan freight invoice posted + demurrage approved → `total_revenue` harus persis sesuai rate × qty + demurrage.

## Definition of Done
- [ ] §10.2 acceptance criteria terpenuhi & diverifikasi (freight + demurrage → total_revenue benar)
- [ ] §10.3 acceptance criteria terpenuhi & diverifikasi (bunker cost dari fleet_fuel_log muncul dengan traceability line_ids)
- [ ] Line traceability (`source_model`/`source_res_id`) bisa dipakai untuk drill-down manual (cek via psql, tombol "Lihat Sumber" boleh menyusul sprint views polish)
- [ ] Idempotent, install bersih
- [ ] Pre-flight lengkap dijalankan (termasuk check mail.thread/mail.activity.mixin kalau ada model baru yang pakai message_post/activity_schedule di sprint ini)
