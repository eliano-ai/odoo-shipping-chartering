# Sprint 5 — Time Charter: Hire Statement & Off-hire

**Modul disentuh:** `vessel_chartering`
**Depends on:** Sprint 2 (`vessel.charter.contract`)

## Konteks
Sisi Time Charter dari kontrak (§3.7, §3.8) — hire statement per periode penagihan, off-hire event yang mengurangi net hire days. Acceptance criteria §10.6 tech spec jadi acuan test: hire statement 15 hari dengan off-hire 12 jam → net hire days = 14.5.

## Tasks

1. Model `vessel.offhire.event` (§3.8) — contract_id, datetime_start/end, duration_hours (compute store), reason (breakdown/drydock/crew/deficiency/other), description, fuel_deduction (Monetary — biaya bunker selama off-hire ditanggung owner)
2. Model `vessel.hire.statement.line` (§3.7) — contract_id, period_start/end, days_in_period (compute), offhire_hours (compute — agregasi dari `offhire_ids` yang beririsan periode ini, perhatikan overlap partial periode), net_hire_days (compute = days_in_period − offhire_hours/24), hire_amount (compute = net_hire_days × hire_rate dari kontrak), cve_amount (compute, pro-rata bulanan dari `cve_rate` kontrak), bunker_adjustment (Monetary, manual input — BOD/BOR fase ini manual sesuai §3.7), total_amount (compute), invoice_id (placeholder, diisi Sprint 6), state (draft/invoiced/paid — related dari invoice, invoiced/paid baru bisa terisi setelah Sprint 6)
3. Update `total_offhire_hours` di kontrak (§3.2 Field Time Charter) — compute dari `offhire_ids`
4. Tombol "Generate Hire Statement" di form kontrak — buat `vessel.hire.statement.line` periode berikutnya otomatis berdasarkan `hire_payment_term` (15_days_advance / monthly_advance / monthly_arrears), cegah generate duplikat periode yang sama
5. Views: tab "Hire & Off-hire" di form kontrak (hanya visible untuk `contract_type='time'`) — list inline hire statement lines + off-hire events, smart button "Hire Statements" dengan count asli
6. Dummy data: 1 time charter contract dengan 1 hire statement periode 15 hari + 1 off-hire event 12 jam dalam periode itu — **hasil net_hire_days harus persis 14.5** (replikasi acceptance criteria §10.6)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_chartering 2>&1 | grep -E "ERROR|CRITICAL"
```

Unit test tambahan (`TransactionCase`):
1. Hire statement 15 hari, off-hire 12 jam dalam periode → net_hire_days = 14.5 (persis acceptance criteria §10.6)
2. Off-hire yang overlap sebagian periode (mulai sebelum period_start atau berakhir sesudah period_end) → hanya porsi yang overlap yang dihitung

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --test-enable --test-tags vessel_chartering -u vessel_chartering 2>&1 | grep -E "FAIL|ERROR|OK"
```

## Definition of Done
- [ ] net_hire_days = 14.5 pada dummy data (persis acceptance criteria §10.6)
- [ ] Generate Hire Statement tidak membuat duplikat periode
- [ ] Off-hire partial-overlap dihitung proporsional, bukan all-or-nothing
- [ ] Tab Hire & Off-hire hanya muncul untuk contract_type=time
