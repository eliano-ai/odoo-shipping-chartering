# Sprint 8 — vessel_voyage_operations: Foundation & Master Data

**Modul disentuh:** `vessel_voyage_operations` (baru)

## Konteks
Modul kedua Layer 2 Komersial, sesuai `TECH_SPEC_vessel_voyage_operations.md`. Hard dependency ke `vessel_chartering` (sudah terinstall). Soft dependency `fleet_fuel_log` (cek via `ir.module.module`, jangan taruh di manifest `depends`). Sprint ini murni fondasi: skeleton, master data, security dasar, extend `res.partner`.

## Keputusan yang Sudah Diputuskan User (sebelum sprint dimulai)
- Odoo edition: **Community** (lanjutan environment `shipping_dev` yang sama)
- Noon report frequency: **fixed 24 jam** (tidak configurable per voyage)
- Portal Nakhoda: **form web simple**, bukan PWA offline-first
- Variance threshold PDA/FDA: **configurable per port/klien** (bukan cuma 1 setting global) — field baru di `res.partner`, dengan fallback ke default global di `res.company`
- Dashboard posisi armada: **full OWL/Leaflet map widget** sesuai spec asli (bukan fallback list) — dikerjakan Sprint 14
- Open question §11.2 (record rule portal): **resolved** — `vessel.seafarer` tidak punya `user_id` langsung, tapi punya `employee_id` → `hr.employee.user_id` (field standar Odoo). Record rule portal pakai path `seafarer_id.employee_id.user_id`, tidak perlu tambah field baru di `vessel_crew_management`.
- Open question §11.4 (CII data export): MVP **tidak** bikin report khusus — noon report list view standar (dengan export XLSX bawaan Odoo) sudah cukup untuk kalkulasi manual di Excel. Tidak ada task tambahan untuk ini.

## Tasks

1. Skeleton modul `vessel_voyage_operations/` — `__manifest__.py` dengan `depends: ['fleet', 'mail', 'portal', 'vessel_chartering']` (soft-check `fleet_fuel_log` di kode Python, **bukan** di manifest depends), folder standar (`models/`, `views/`, `security/`, `data/`, `wizards/`, `static/src/`, `report/`, `tests/`)
2. Security groups: `group_voyage_ops_portal` (Nakhoda), `group_voyage_ops_user` (Operations), `group_voyage_ops_manager` — `security/vessel_voyage_operations_groups.xml`
3. Master data model `vessel.delay.type` (name, active) + views + menu Konfigurasi + seed data (`noupdate="1"`): Weather, Port Congestion, Breakdown, Waiting Cargo, Waiting Berth, Waiting Instruction, Other
4. Master data model `vessel.clearance.document.type` (name, `default_required` Boolean — dipakai auto-generate clearance line Sprint 3, active) + views + menu + seed: SPB/Port Clearance, Imigrasi, Karantina, Bea Cukai, Lainnya (semua `default_required=True` kecuali Lainnya)
5. Master data model `vessel.disbursement.item.type` (name, active) + views + menu + seed: Pilotage, Towage, Mooring/Unmooring, Port Dues, Light Dues, Agency Fee, Garbage Disposal, Lainnya
6. Extend `res.partner`: `is_port_agent` (Boolean, help jelasin beda dari `is_port`), `disbursement_variance_threshold_pct` (Float, nullable/0=pakai default global, help jelasin fallback) — view list "Agen Pelabuhan" terfilter `is_port_agent=True`
7. Extend `res.company`/`res.config.settings`: `default_disbursement_variance_threshold_pct` (Float, default 15.0) — pola sama seperti `despatch_as_credit_note` di `vessel_chartering` Sprint 6
8. `ir.sequence` untuk voyage: format `VOY/%(year)s/` (dipakai Sprint 9, tapi seed sequence-nya sekarang biar konsisten pola modul sebelumnya)
9. Menu root "Voyage Operations" sejajar Chartering/Dokumen Legal/Fuel (`parent="fleet.menu_root"`), submenu Konfigurasi (3 master data di atas + Agen Pelabuhan)
10. Dummy data: 3 delay type sudah dari seed (cukup), 3-4 agen pelabuhan (`res.partner` dengan `is_port_agent=True`, beberapa dengan threshold override beberapa tanpa)

## Verifikasi

```bash
# Cek fleet_fuel_log TIDAK di manifest depends (harus soft-check di Python)
grep -n "'fleet_fuel_log'" vessel_voyage_operations/__manifest__.py && echo "SALAH - jangan hard depend" || echo "OK - tidak di depends"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -i vessel_voyage_operations 2>&1 | grep -E "ERROR|CRITICAL|Module vessel_voyage_operations loaded"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_operations 2>&1 | grep -E "ERROR|CRITICAL"
```

## Definition of Done
- [ ] Install & upgrade bersih tanpa ERROR/CRITICAL, idempotent (re-run `-u`, tidak duplikat)
- [ ] `fleet_fuel_log` tidak ada di manifest `depends`
- [ ] Semua master data dummy muncul (3 model × seed + demo agen pelabuhan)
- [ ] Field `is_port_agent` beda jelas secara UI dari `is_port` (sudah ada dari `vessel_chartering`)
- [ ] Tidak ada `decoration-secondary`, tidak ada `<group string=/expand=>` di search view (pelajaran dari retro Sprint 1-7 kemarin — grep dulu sebelum install)
