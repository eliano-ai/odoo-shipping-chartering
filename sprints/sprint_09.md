# Sprint 9 — vessel_voyage_operations: Core Voyage Model & State Machine

**Modul disentuh:** `vessel_voyage_operations`
**Depends on:** Sprint 8 (foundation, sequence VOY)

## Konteks
Model `vessel.voyage` (§3.2) — jantung modul, 1-ke-1/1-ke-banyak terhadap `vessel.charter.contract`. Hard dependency ke `vessel_chartering` dipakai penuh di sini.

## Tasks

1. Model `vessel.voyage` — semua field §3.2: `name` (via `ir.sequence` VOY), `charter_contract_id` (required saat state≥fixed, domain state in confirmed/in_progress), `vessel_id` (related dari kontrak, store), `tug_id` (related), `analytic_account_id` (related dari kontrak, store — **jangan duplikasi**, 1 sumber kebenaran), `fleet_trip_id` (Many2one `fleet.vehicle.trip`, **optional field, tidak wajib modul `fleet_fuel_log` ada** — declare field biasa, tapi sembunyikan di view via check module installed), `date_departure`/`date_arrival_final`, `origin_port_id`/`final_port_id` (domain `is_port=True`), `total_distance_nm` (compute, placeholder 0 dulu — diisi Sprint 11 saat noon report ada), `total_delay_hours` (compute, placeholder 0 dulu — Sprint 13), `state`
2. Constraint `_check_dates`: `date_arrival_final >= date_departure`
3. Constraint: satu `charter_contract_id` hanya boleh 1 voyage aktif (state not in completed/cancelled) **kecuali** `contract_type='time'` yang boleh >1 voyage berurutan tidak overlap tanggal — logic serupa `_check_vessel_overlap` di `vessel_chartering`, adaptasi untuk voyage
4. State machine (§4.1): `action_fix` (draft→fixed, wajib pilih charter_contract_id, auto-copy vessel_id & analytic_account_id), `action_depart` (fixed→sailing, isi date_departure & origin_port_id), `action_arrive_port`/`action_depart_port` (toggle sailing↔at_port — untuk sprint ini implementasikan sebagai method dasar, logic penuh terhubung port_call_ids di Sprint 10), `action_complete` (at_port/sailing→completed, validasi minimal 1 cargo document type=bl jika voyage charter — **placeholder validasi dulu, cargo_document_ids belum ada sampai Sprint 12, skip validasi itu sementara dengan TODO comment**), `action_cancel` (wizard alasan, hanya dari draft/fixed)
5. Wizard `vessel.voyage.cancel.wizard` — sama pola seperti `vessel.charter.cancel.wizard`
6. Extend `fleet.vehicle`: `voyage_ids` (One2many), `current_voyage_id` (compute, state in sailing/at_port), `current_position_lat`/`current_position_lng` (Float, compute — placeholder return False/0 dulu, diisi Sprint 11 setelah noon report ada)
7. Extend `vessel.charter.contract` (dari `vessel_chartering`): `voyage_ids` (One2many, inverse `charter_contract_id`), `voyage_count` (compute) — smart button baru di form kontrak `vessel_chartering` (edit file existing modul lain — **hati-hati, ini legitimate cross-module extend, bukan modifikasi source modul lain langsung**)
8. Security access untuk `vessel.voyage` & wizard cancel (3 groups dari Sprint 8)
9. Views: form voyage (notebook placeholder untuk Port Rotation/Noon Reports/Cargo Documents/Delay Log — isi nanti sprint berikutnya), list, kanban by state, menu Voyages (Semua Voyage, Sedang Berlayar, Selesai)
10. Dummy data: 2-3 voyage dari kontrak dummy `vessel_chartering` yang sudah ada (pilih yang `confirmed`/`in_progress`), variasi state (fixed, sailing, completed)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_operations,vessel_chartering 2>&1 | grep -E "ERROR|CRITICAL"
```

Manual via shell: buat voyage dari kontrak confirmed, cek `vessel_id`/`analytic_account_id` ter-copy otomatis (acceptance criteria §10.2 tech spec voyage_operations).

## Definition of Done
- [ ] `vessel.voyage` full state machine jalan end-to-end (draft→fixed→sailing→completed), diverifikasi via shell
- [ ] `analytic_account_id` di voyage = `analytic_account_id` di kontrak (related, bukan duplikasi record baru)
- [ ] Smart button `voyage_count` muncul di form `vessel.charter.contract` existing tanpa merusak apapun yang sudah ada
- [ ] Constraint 1-voyage-aktif-per-kontrak (kecuali time charter) diverifikasi
- [ ] Idempotent, install bersih dua modul bareng tanpa circular dependency error
