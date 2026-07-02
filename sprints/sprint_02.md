# Sprint 2 — Core Charter Contract Model & State Machine

**Modul disentuh:** `vessel_chartering`
**Depends on:** Sprint 1 (master data, analytic plans, security groups)

## Konteks
Jantung modul: `vessel.charter.contract` (§3.2 tech spec) — satu model untuk voyage/time/COA, direction out/in. State machine §4.1 (draft→negotiation→confirmed→in_progress→completed→closed, +cancelled). Laytime/hire/invoicing belum diisi logic-nya (field placeholder One2many boleh, business logic-nya Sprint 4-6).

## Tasks

1. Model `vessel.charter.contract` — semua field §3.2: Field Umum, Field Voyage Charter, Field Time Charter, Field COA, Field Compute/Monitoring (`freight_amount_estimate`, `freight_amount_final`, `demurrage_amount_total`/`despatch_amount_total` boleh return 0 dulu — diisi Sprint 4/6, `invoiced_amount`/`residual_amount` boleh return 0 — diisi Sprint 6)
2. `ir.sequence` untuk `name`: format `CHO/%(year)s/%(seq)s` (out) dan `CHI/%(year)s/%(seq)s` (in) — dua sequence terpisah, pilih berdasar `direction` saat create
3. Constraint: `_check_dates` (date_end ≥ date_start), `_check_vessel_overlap` (warning via `mail.activity`/log, bukan blokir — sesuai §3.2 kecuali overlap penuh dengan kontrak `in_progress`), `_check_rates` (freight_rate/hire_rate > 0 saat confirm), constraint COA tidak boleh punya laytime/hire lines langsung
4. State machine method: `action_send_negotiation`, `action_confirm` (validasi rate>0, vessel&partner terisi kecuali COA, laycan valid, **auto-create analytic account plan Voyage**, cek overlap, post chatter), `action_start` (voyage: manual set in_progress; TC: isi delivery_date), `action_complete` (voyage: syarat bl_qty terisi — untuk saat ini skip syarat "semua laytime approved" karena laytime belum ada, TODO comment; TC: isi redelivery_date), `action_close`, `action_cancel` (wizard alasan)
5. Wizard `vessel.charter.cancel.wizard` — field `reason` (Text, required), dipanggil dari `action_cancel`
6. Update extend `fleet.vehicle` dari Sprint 1: `charter_contract_ids` (One2many nyata sekarang), `active_charter_id` (compute, kontrak in_progress saat ini), `charter_status` (compute penuh: available/on_voyage_charter/on_time_charter/chartered_in)
7. Model COA: `shipment_ids` (One2many self, `coa_id` inverse), `qty_shipped`/`qty_remaining` (compute dari child state ≥ completed — untuk saat ini state completed belum reachable penuh, compute tetap ditulis benar untuk dipakai nanti)
8. Views: form kontrak dengan notebook pages (Info Utama, Komersial, COA — Estimate/Laytime/Hire&Offhire/Invoicing kosongkan dulu jadi placeholder "Coming in Sprint N"), statusbar dengan tombol state, smart buttons (Estimates/Laytime/Invoices — badge count 0 dulu, link disable atau ke action kosong), list view (group by state), kanban by state, calendar by laycan
9. Menu: Fixtures/Kontrak → Semua Kontrak, Charter Out (domain direction=out), Charter In (domain direction=in), COA (domain contract_type=coa)
10. Dummy data: 3 kontrak voyage charter (2 out coal batubara, 1 in), 1 kontrak time charter (out), 1 COA dengan 2 shipment child — variasi state (draft, confirmed, in_progress)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_chartering 2>&1 | grep -E "ERROR|CRITICAL"

# Cek analytic account ter-generate saat confirm (spot check via psql setelah demo data load)
MSYS_NO_PATHCONV=1 docker compose exec db psql -U odoo -d shipping_dev -c \
  "SELECT name, plan_id FROM account_analytic_account WHERE plan_id IN (SELECT id FROM account_analytic_plan WHERE name IN ('Vessel','Voyage'));"
```

## Definition of Done
- [ ] Semua field §3.2 ada dan tipe data sesuai tabel tech spec
- [ ] State machine jalan penuh draft→negotiation→confirmed→in_progress→completed→closed untuk minimal 1 dummy record
- [ ] Cancel wizard berfungsi, wajib isi alasan
- [ ] Analytic account plan Voyage auto-terbentuk saat confirm; plan Vessel auto-terbentuk saat vessel is_vessel=True
- [ ] COA qty_remaining terhitung benar dari child shipment (acceptance criteria §10.8 tech spec)
- [ ] Constraint overlap kapal berfungsi (warning, bukan block, kecuali overlap in_progress penuh)
