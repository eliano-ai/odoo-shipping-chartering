# Sprint 22 — vessel_bunker_management: Foundation & Master Data

**Modul disentuh:** `vessel_bunker_management` (baru)
**Depends on:** `fleet_fuel_log`, `vessel_chartering`, `vessel_voyage_operations` (semua hard dependency, beda pola dari `vessel_voyage_pnl`)

## Konteks
Modul keempat Layer 3 Finansial, sesuai `TECH_SPEC_vessel_bunker_management.md`. Berbeda dari 3 modul sebelumnya: dependency ke `fleet_fuel_log` & `vessel_voyage_operations` **wajib (hard)**, bukan soft — karena ROB reconciliation (fitur inti) tidak bermakna tanpa data konsumsi & noon report.

## Keputusan yang Sudah Diputuskan User (sebelum sprint dimulai)
- **Portal surveyor eksternal**: TIDAK di MVP — staff internal input hasil survey dari laporan PDF surveyor (bukan portal access langsung). `group_bunker_surveyor_portal` tetap disebut di tech spec §6 tapi implementasinya ditunda ke Fase 2.
- **Threshold ROB reconciliation**: global (`res.company`) + override per kapal (`fleet.vehicle`) — pola identik `budget_variance_threshold_pct`/`disbursement_variance_threshold_pct` yang sudah dipakai di `vessel_voyage_pnl`/`vessel_voyage_operations`.
- **BOD/BOR settlement**: scope MVP Time Charter murni (`contract_type='time'`) — relet BOD/BOR ditunda ke Fase 2.
- **Approval nominasi supplier**: role `group_bunker_manager` tunggal, tanpa approval matrix berjenjang.

## Fakta Environment (dicek langsung sebelum sprint dimulai)
- **Tidak ada konsep `stock.location` per kapal** di `fleet_fuel_log` maupun `fleet_model_sparepart` — keduanya cuma pakai lokasi stok generik (`stock.stock_location_stock`/`stock.stock_location_production`) untuk konsumsi. **Keputusan teknis** (bukan keputusan bisnis, jadi diputuskan langsung tanpa tanya user): modul ini akan membuat 1 `stock.location` per kapal (child dari lokasi "Vessels" baru, mirip pola 1-lokasi-per-warehouse standar Odoo), supaya ROB/stok bunker per kapal punya representasi stok yang benar. Field baru `fleet.vehicle.bunker_stock_location_id` (M2O `stock.location`, auto-create saat kapal pertama kali butuh — lihat Sprint 24).
- `stock` module sudah jadi dependency existing di 3 modul fleet lain (`fleet_fuel_log`, `fleet_maintenance_schedule`, `fleet_model_sparepart`) — tidak perlu instalasi tambahan di luar `-i` modul ini.

## Tasks

1. **Skeleton modul** — `__manifest__.py` dengan `depends: ['fleet', 'mail', 'purchase', 'stock', 'account', 'fleet_fuel_log', 'vessel_chartering', 'vessel_voyage_operations']` — **semua hard dependency**, tidak ada soft-check Python kecuali untuk portal surveyor (ditunda, jadi tidak relevan MVP ini). Folder standar (`models/`, `wizards/`, `views/`, `data/`, `security/`, `report/`, `tests/`)
2. Security groups: `group_bunker_user` (RWC inquiry/quote/delivery, no unlink confirmed, tidak resolve dispute), `group_bunker_manager` (full + resolve dispute + approve BOD/BOR + konfigurasi) — **PENTING: cross-check xmlid group existing** (`account.group_account_invoice` untuk Finance, `fleet.fleet_group_manager`/`vessel_voyage_operations.group_voyage_ops_user` untuk Operations, sesuai §6 tech spec), jangan asumsi nama. `group_bunker_surveyor_portal` disebut sebagai xmlid placeholder di security file (didefinisikan tapi belum dipakai di record rule manapun sampai Fase 2)
3. Master data model `vessel.pnl.cost.category`-**setara** untuk bunker: cukup 1 master baru `vessel.bunker.price.reference` (§3.8) — date, index_name (mops/platts/other), fuel_type_id (M2O `fleet.fuel.type`, **reuse existing, JANGAN bikin master baru** sesuai §8 keputusan desain), price_usd_mt, region. Views + menu Konfigurasi + seed data minimal (`noupdate="1"`): 2-3 baris harga referensi dummy untuk testing `price_vs_market_pct` nanti
4. Extend `fleet.vehicle`: `bunker_variance_threshold_pct` (Float, nullable/0=fallback global — untuk ROB reconciliation, field TERPISAH dari `budget_variance_threshold_pct` milik `vessel_voyage_pnl`, meski pola sama, karena modul beda & scope beda)
5. Extend `res.company`/`res.config.settings`: `default_bunker_variance_threshold_pct` (Float, default 8.0 — sesuai contoh §10.5 acceptance criteria "threshold < 8%"), `default_bdn_survey_tolerance_pct` (Float, default 0.5 — sesuai §2.3)
6. Menu root "Bunker Management" — **keputusan IA**: masuk app **Maritime** (konsisten pola `vessel_voyage_pnl`, bukan `fleet.menu_root` — modul ini juga lapisan finansial/operasional komersial, bukan asset fisik), `depends` tambahkan `maritime`, menu root sejajar Voyage P&L
7. Dummy data: tidak perlu di sprint ini (model inti belum ada) — cukup pastikan seed `vessel.bunker.price.reference` muncul

## Verifikasi

```bash
grep -n "'fleet_fuel_log'\|'vessel_chartering'\|'vessel_voyage_operations'" vessel_bunker_management/__manifest__.py && echo "OK - semua hard depend" || echo "SALAH - cek ulang depends"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -i vessel_bunker_management 2>&1 | grep -E "ERROR|CRITICAL|Module vessel_bunker_management loaded"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_bunker_management 2>&1 | grep -E "ERROR|CRITICAL"
```

## Definition of Done
- [ ] Install & upgrade bersih tanpa ERROR/CRITICAL, idempotent
- [ ] Semua dependency di manifest adalah hard depend (bukan soft-check) sesuai §7/§8 tech spec — beda pola dari `vessel_voyage_pnl`
- [ ] Master data `vessel.bunker.price.reference` muncul dengan seed dummy
- [ ] `fleet.fuel.type` dikonfirmasi ter-reuse langsung (tidak ada master fuel type baru dibuat)
- [ ] Menu root "Bunker Management" masuk app Maritime, sejajar Voyage P&L
- [ ] Pre-flight check lengkap dijalankan (grep pola Odoo 19 terlarang dari CLAUDE.md)
