# Sprint 4 — Laytime, SOF & Demurrage/Despatch Calculator

**Modul disentuh:** `vessel_chartering`
**Depends on:** Sprint 2 (`vessel.charter.contract`)

## Konteks
Bagian paling kompleks dari modul ini (§3.4, §3.5, §2.3 tech spec). Satu record laytime per port call (load/discharge), SOF lines kronologis, aturan **"once on demurrage, always on demurrage"** hardcoded untuk MVP (§8 keputusan desain). Empat acceptance criteria tech spec (§10.3, §10.4) menguji langsung logic sprint ini — jadikan acuan test.

## Tasks

1. Model `vessel.laytime.interruption.type` sudah ada dari Sprint 1 — pastikan field `is_counting` dipakai benar di compute laytime
2. Model `vessel.sof.line` (§3.5) — laytime_id, datetime_start/end, duration_hours (compute store), activity (Char), interruption_type_id (kosong=normal counting), is_counting (compute store dari interruption type), remarks. Constraint: datetime_end > datetime_start; overlap antar line → warning (bukan blokir, sesuai catatan tech spec "SOF nyata kadang paralel")
3. Model `vessel.laytime.calculation` (§3.4) — contract_id, port_call_type (load/discharge), port_id, nor_tendered, nor_accepted, laytime_commenced (compute dari nor_accepted+turn_time, editable override), laytime_completed, laytime_allowed_hours (default dari kontrak), sof_line_ids, state (draft→submitted→approved→invoiced)
4. **Compute `laytime_used_hours`** — implementasi presisi aturan §3.4:
   - Iterasi sof_line_ids terurut waktu
   - Line `is_counting=False` dikecualikan **kecuali** posisi waktu sudah melewati titik on-demurrage (once-on-demurrage rule)
   - Perhatikan `charter_terms_id.sundays_holidays_included` (SHINC/SHEX) — MVP: flag boolean saja, tanpa kalender libur nasional (itu Fase 2 tech spec, **jangan diimplementasi sekarang**)
5. Compute `balance_hours` (allowed − used), `time_on_demurrage_hours`, `demurrage_amount` ((time_on_demurrage/24) × demurrage_rate dari kontrak), `despatch_amount` ((balance positif/24) × despatch_rate dari kontrak)
6. Workflow state: draft → submitted → approved (hanya `group_chartering_manager`) → invoiced (di-set nanti oleh Sprint 6 saat invoice terbit)
7. Reversible laytime (`laytime_reversible=True` di kontrak): tetap 2 record laytime (load & discharge) tapi UI/compute kontrak menggabungkan untuk demurrage — lihat §3.4 catatan
8. Update field compute kontrak dari Sprint 2 yang tadinya return 0: `demurrage_amount_total`/`despatch_amount_total` sekarang agregasi nyata dari `laytime_ids` yang `approved`
9. Views: form laytime — header (NOR/commenced/completed), SOF lines sebagai **editable inline list** dengan running total durasi, panel ringkasan selalu terlihat (allowed vs used vs balance vs demurrage amount) — gunakan pattern serupa modul existing (`fleet_maintenance_schedule` punya line items serupa untuk referensi). Smart button "Laytime" di form kontrak dengan count asli
10. Dummy data: minimal 1 laytime calculation dengan SOF lines yang **mereplikasi test case tech spec §10.3/10.4** — SOF termasuk interupsi hujan (non-counting), hasil akhir balance −36 jam, demurrage_rate USD 10,000/day → demurrage_amount harus keluar USD 15,000 (bukti compute benar)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_chartering 2>&1 | grep -E "ERROR|CRITICAL"
```

**Wajib**: tulis unit test `TransactionCase` untuk compute laytime (acceptance criteria §10.9 tech spec) — minimal 3 test case:
1. SOF tanpa interupsi, laytime used = durasi total → balance & demurrage benar
2. SOF dengan interupsi non-counting (hujan) sebelum on-demurrage → dikecualikan dari used
3. SOF dengan interupsi non-counting **setelah** titik on-demurrage tercapai → tetap dihitung (once-on-demurrage rule), verifikasi demurrage_amount = USD 15,000 sesuai skenario dummy data

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --test-enable --test-tags vessel_chartering -u vessel_chartering 2>&1 | grep -E "FAIL|ERROR|OK"
```

## Definition of Done
- [ ] 3 unit test compute laytime lulus (termasuk skenario once-on-demurrage)
- [ ] Dummy data menghasilkan demurrage_amount USD 15,000 persis sesuai acceptance criteria §10.4
- [ ] `demurrage_amount_total`/`despatch_amount_total` di kontrak teragregasi benar dari laytime approved
- [ ] SOF line inline editable dengan running total di UI
- [ ] State laytime draft→submitted→approved berfungsi, approve hanya bisa oleh Manager
