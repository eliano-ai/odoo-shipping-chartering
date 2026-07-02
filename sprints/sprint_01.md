# Sprint 1 — Module Foundation & Master Data

**Modul disentuh:** `vessel_chartering` (baru)

## Konteks
Fondasi modul baru: skeleton, security groups, seluruh master data (§3.6, §3.9 tech spec), analytic plans (§2.5), dan extend `fleet.vehicle` (§3.10). Model kontrak inti (`vessel.charter.contract`) belum dibuat di sprint ini — itu Sprint 2.

## Tasks

1. Buat skeleton modul `vessel_chartering/` — `__manifest__.py` (depends: `fleet`, `account`, `analytic`, `mail`; license LGPL-3, category sesuai pola modul lain), `__init__.py`, folder `models/`, `views/`, `security/`, `data/`, `wizard/`
2. Security groups: `group_chartering_user`, `group_chartering_manager` (lihat §6 tech spec) — `security/vessel_chartering_security.xml` + `security/ir.model.access.csv` (prefix modul wajib di semua xmlid)
3. Model master `vessel.cargo.type` (name, is_dangerous, default_stowage_factor, active) + views (list/form) + menu di bawah Konfigurasi
4. Model master `vessel.charter.terms` (name, loading_terms, sundays_holidays_included, laytime_reversible_default, notes) + views + menu
5. Model master `vessel.laytime.interruption.type` (name, is_counting, active) + views + menu + data seed XML `noupdate="1"` (Hujan, Shifting, Equipment Breakdown Shore, Equipment Breakdown Vessel, Waiting Berth, Force Majeure — sesuai §3.6)
6. Extend `res.partner`: field `is_port` (Boolean), `unlocode` (Char) — view form tambahan tab/field, filtered list view "Ports" (`is_port=True`)
7. Setup 2 Analytic Plans (§2.5): `PLAN_VESSEL`, `PLAN_VOYAGE` — data XML idempotent (cek existing dulu sebelum create, jangan duplikat kalau modul di-upgrade)
8. Extend `fleet.vehicle`: `analytic_account_id` (auto-create di plan Vessel saat `is_vessel=True`, via `create`/`write` override atau compute+store), `charter_contract_ids` (placeholder One2many, target model belum ada — buat setelah Sprint 2, atau declare sekarang dengan comodel string forward-reference), `charter_status` (Selection, compute — logic lengkap nanti Sprint 2), `gt`, `dwt` (Float — **cek dulu apakah field ini sudah ada dari `fleet_document_id` sebelum nambah, hindari duplikat**)
9. Menu root "Chartering" sejajar Fleet lain (`parent="fleet.menu_root"`), submenu "Konfigurasi" (Tipe Cargo, Charter Terms, Tipe Interupsi Laytime, Pelabuhan)
10. Dummy/master data (`data/vessel_chartering_demo.xml`, didaftarkan di key `demo` manifest): minimal 3 cargo type (Batubara, Nikel, General Cargo), 2 charter terms (misal "FIOST 8000/8000 SHINC", "CQD SHEX"), 5 port (`res.partner` dengan `is_port=True`: Tanjung Priok, Balikpapan, Tarahan, Satui, Singapore) dengan `unlocode` benar

## Verifikasi

```bash
# Cek dulu field gt/dwt tidak duplikat dengan fleet_document_id
grep -rn "'gt'\|'dwt'" fleet_document_id/models/*.py fleet_fuel_log/models/*.py

# Install bersih
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -i vessel_chartering 2>&1 | grep -E "ERROR|CRITICAL|Module vessel_chartering loaded"

# Cek analytic plan idempotent — install ulang tidak boleh duplikat account
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_chartering 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec db psql -U odoo -d shipping_dev -c \
  "SELECT name FROM ir_module_module WHERE name='vessel_chartering';"
```

## Definition of Done
- [ ] Install bersih tanpa ERROR/CRITICAL
- [ ] Update (`-u`) kedua kali tidak duplikat analytic account
- [ ] Semua master data dummy muncul di UI (cargo type, charter terms, interruption type, port)
- [ ] Tidak ada field `gt`/`dwt` duplikat dengan modul existing
- [ ] Menu "Chartering" muncul sejajar Fleet/Dokumen Legal/Fuel/Maintenance/Spareparts/Crew Management
