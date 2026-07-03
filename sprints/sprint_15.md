# Sprint 15 — vessel_voyage_pnl: Foundation & Master Data

**Modul disentuh:** `vessel_voyage_pnl` (baru)
**Depends on:** `vessel_chartering` (selesai), `vessel_voyage_operations` (selesai)

## Konteks
Modul ketiga Layer 2/3 Komersial, sesuai `TECH_SPEC_vessel_voyage_pnl.md`. Payoff dari Analytic Plans (Vessel + Voyage) yang sudah dikunci sejak `vessel_chartering` — modul ini murni agregasi lintas-modul. Hard dependency ke `vessel_chartering` DAN `vessel_voyage_operations` (keduanya sumber data, tanpa keduanya modul ini tidak punya apapun untuk diagregasi).

## Keputusan yang Sudah Diputuskan User (sebelum sprint dimulai)
- Odoo edition: **Community** (lanjutan environment `shipping_dev` yang sama) — tech spec header bilang "Enterprise" tapi ini boilerplate, sama seperti 2 modul sebelumnya
- **`hr_payroll` dan `account_asset` TIDAK tersedia sama sekali** di environment ini (bukan cuma uninstalled — tidak ada di addons path, dikonfirmasi Enterprise-only). Konsekuensi: crew cost dan depresiasi **selalu** allocation_method=`manual` di MVP — bukan keputusan bisnis, murni keterbatasan environment. Field/model tetap dibangun sesuai spec (§3.8, §7), cuma sumber data otomatisnya tidak akan pernah terisi kecuali suatu saat modul itu di-install.
- **`spreadsheet_dashboard` SUDAH terinstall** — dashboard direksi (§5) bisa dibangun penuh sesuai spec, tidak perlu fallback pivot/graph.
- **Definisi TCE aktual**: exclude allocated cost (crew/maintenance/depresiasi/overhead) — `tce_actual_per_day = (total_revenue - total_direct_cost) / voyage_days`, konsisten dengan `vessel.voyage.estimate` di `vessel_chartering`.
- **Historical backfill**: MVP sertakan wizard/tombol bulk-generate P&L untuk voyage `completed` yang sudah ada (dari demo data `vessel_chartering`/`vessel_voyage_operations`) dan belum punya `pnl_id` — bukan cuma voyage baru ke depan. Task ini masuk Sprint 20 (setelah model inti Sprint 16-17 selesai).
- **Threshold variance budget**: configurable per kapal/kategori biaya, fallback ke default global `res.company` — pola sama seperti `disbursement_variance_threshold_pct` di `vessel_voyage_operations`. Field override ditaruh di `fleet.vehicle` (bukan per-kategori untuk MVP, supaya tidak terlalu granular — cukup per kapal).

## Tasks

1. **Skeleton modul** — `__manifest__.py` dengan `depends: ['fleet', 'mail', 'account', 'vessel_chartering', 'vessel_voyage_operations']` (soft-check `fleet_fuel_log`, `vessel_crew_management`, `fleet_maintenance_schedule` di kode Python — semua sudah terinstall di environment ini jadi bisa langsung dipakai, tapi tetap soft-check konsisten pola project), folder standar (`models/`, `wizards/`, `views/`, `data/`, `security/`, `report/`, `tests/`)
2. Security groups: `group_voyage_pnl_user` (Operations/Chartering, read-only P&L & vessel P&L), `group_voyage_pnl_finance` (RWC P&L generate/recompute/adjustment/lock, RWC budget), `group_voyage_pnl_manager` (full + konfigurasi kategori biaya & aturan alokasi) — **PENTING: cross-check xmlid Finance existing** (`account.group_account_invoice`, sesuai koreksi Sprint 13 vessel_voyage_operations) kalau butuh referensi group accounting standar, jangan asumsi nama
3. Master data model `vessel.pnl.cost.category` (§3.7) — name, category_group (revenue/direct_cost/allocated_cost), default_account_ids (M2M account.account), sequence, active + views + menu Konfigurasi + seed data (`noupdate="1"`): Freight Revenue, Demurrage, Despatch, Brokerage (revenue); Bunker, Port Cost, Cargo Handling, Insurance Voyage (direct_cost); Crew Cost, Maintenance, Depreciation, Overhead (allocated_cost); Other (bisa dipakai di grup manapun, biarkan Finance pilih saat dipakai)
4. Master data model `vessel.cost.allocation.rule` (§3.8) — cost_category_id (domain category_group=allocated_cost), allocation_method (per_voyage_day/per_calendar_day/equal_split/fixed_percentage/manual), fixed_percentage_value, active + views + menu + seed data: default `manual` untuk Crew Cost & Depreciation (karena hr_payroll/account_asset tidak ada), default `per_voyage_day` untuk Maintenance, default `fixed_percentage` untuk Overhead (value 5% sebagai starting point, Finance bisa ubah). Constraint: 1 rule aktif per cost_category_id
5. Extend `fleet.vehicle`: `budget_variance_threshold_pct` (Float, nullable/0=fallback global) — field baru untuk keputusan threshold per-kapal
6. Extend `res.company`/`res.config.settings`: `default_budget_variance_threshold_pct` (Float, default 20.0) — pola sama seperti `default_disbursement_variance_threshold_pct` Sprint 8 `vessel_voyage_operations`
7. Menu root "Voyage P&L" sejajar Maritime/Fleet (`parent="fleet.menu_root"` — **cek dulu apakah sebaiknya masuk app `maritime` juga**, karena ini modul komersial finansial, bukan asset fisik; secara IA lebih dekat ke Chartering/Voyage Operations daripada Fleet — kalau iya, `depends` tambahkan `maritime` dan reparent seperti pola restrukturisasi kemarin, ATAU biarkan Fleet dulu dan tanya user di akhir sprint kalau ragu), submenu Konfigurasi (2 master data di atas)
8. Dummy data: tidak perlu di sprint ini (model inti P&L belum ada) — cukup pastikan seed master data (task 3-4) muncul

## Verifikasi

```bash
grep -n "'hr_payroll'\|'account_asset'" vessel_voyage_pnl/__manifest__.py && echo "SALAH - jangan hard depend" || echo "OK - tidak di depends"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -i vessel_voyage_pnl 2>&1 | grep -E "ERROR|CRITICAL|Module vessel_voyage_pnl loaded"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_pnl 2>&1 | grep -E "ERROR|CRITICAL"
```

## Definition of Done
- [ ] Install & upgrade bersih tanpa ERROR/CRITICAL, idempotent
- [ ] `hr_payroll`/`account_asset` tidak ada di manifest `depends`
- [ ] Master data dummy muncul (12+ cost category, allocation rule per kategori allocated_cost)
- [ ] Constraint 1 rule aktif per cost_category_id terverifikasi
- [ ] Pre-flight check lengkap dijalankan (grep pola Odoo 19 terlarang, mail.thread/mail.activity.mixin kalau ada model yang pakai message_post/activity_schedule — belum ada di sprint ini tapi cek tetap dijalankan untuk konsistensi kebiasaan)
