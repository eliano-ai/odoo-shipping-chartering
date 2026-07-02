# Sprint 7 — Cron, Notifikasi, Integrasi Soft, Laporan & Acceptance Final

**Modul disentuh:** `vessel_chartering`
**Depends on:** Sprint 1-6 (semua)

## Konteks
Penutup MVP: proactive notification (§4.3, §4.4), integrasi soft ke modul lain (§7), laporan (§5 bagian Laporan), lalu jalankan **seluruh 10 acceptance criteria §10 tech spec** sebagai gate akhir sebelum modul dianggap MVP-complete.

## Tasks

1. Cron `_cron_laycan_alert` (harian) — kontrak confirmed dengan laycan H-7/H-3/H-0 tanpa NOR → `activity_schedule` ke Operations + email
2. Cron `_cron_hire_due` (harian) — TC hire statement line berikutnya jatuh tempo H-5 → activity ke Finance
3. Cron `_cron_coa_progress` (mingguan) — COA `qty_remaining > 0` dengan sisa periode < 60 hari → warning under-lifting ke Chartering Manager
4. Cron `_cron_demurrage_exposure` (harian) — laytime draft/submitted dengan balance negatif → update field exposure (tambahkan field `demurrage_exposure` di kontrak jika belum ada) untuk dashboard
5. Email template (pola sama seperti modul existing — `mail.thread` + template XML): fixture confirmed (internal), laycan reminder, demurrage approved (opsional ke partner), hire due
6. Integrasi soft ke `fleet_document_id`: warning (bukan block) saat `action_confirm` fixture jika kapal punya dokumen expired/segera expired — reuse `fleet.vehicle.document` state compute yang sudah ada, jangan duplikasi logic
7. Integrasi soft ke `vessel_crew_management`: warning saat `action_start` voyage jika manning (crew aktif di kapal) kosong — reuse `active_crew_count` dari `fleet.vehicle` extend yang sudah ada di modul itu
8. Laporan: Fixture Pipeline (kanban/graph by state & bulan laycan), Demurrage Exposure (pivot: kontrak × status laytime), Analisa Voyage Estimate (list estimate vs actual dasar)
9. Review security record rules — multi-company (`company_id` required di semua model transaksional), pastikan `group_chartering_user` tidak bisa unlink & tidak lihat nilai total COA (sesuai §6)
10. **Jalankan seluruh checklist acceptance criteria §10 tech spec** satu per satu, catat hasil per poin di `SPRINT_REPORT.md`

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_chartering 2>&1 | grep -E "ERROR|CRITICAL"

# Full test suite modul ini
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --test-enable --test-tags vessel_chartering -u vessel_chartering 2>&1 | grep -E "FAIL|ERROR|OK"

# Audit checklist Odoo 19 (acceptance criteria §10.10)
grep -rn "display_name" vessel_chartering/models/*.py | grep -v "compute="  # tidak boleh dipakai sbg field custom
grep -rn "fields.Datetime.from_string" vessel_chartering/  # tidak boleh dipakai
grep -rn "@api.depends()" vessel_chartering/models/*.py  # tidak boleh kosong
```

## Definition of Done — Checklist Acceptance Criteria (§10 tech spec, jalankan semua)
- [ ] §10.1 Install bersih Odoo 19 Enterprise-compat (kita: Community) tanpa error, tanpa konflik 5 modul existing
- [ ] §10.2 Voyage charter out USD confirm → analytic account plan Voyage & plan Vessel terbentuk
- [ ] §10.3 SOF dengan interupsi hujan → laytime used benar termasuk once-on-demurrage (3 test case)
- [ ] §10.4 Laytime approved balance −36 jam, rate USD 10,000/day → demurrage invoice USD 15,000 + analytic 2 plan
- [ ] §10.5 Invoice IDR fixed rate 16.250 → amount & kurs benar
- [ ] §10.6 Hire statement 15 hari, off-hire 12 jam → net hire days = 14.5
- [ ] §10.7 Charter-in → vendor bill draft dengan expense account & analytic benar
- [ ] §10.8 COA 3 shipment child → qty_remaining benar
- [ ] §10.9 Semua unit test TransactionCase compute laytime lulus
- [ ] §10.10 Audit: tidak ada display_name sebagai field custom, tidak ada fields.Datetime.from_string, tidak ada @api.depends() kosong
