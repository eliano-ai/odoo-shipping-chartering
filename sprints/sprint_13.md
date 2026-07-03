# Sprint 13 — vessel_voyage_operations: Cargo Document, Delay Log, Portal Security, Cron & Email

**Modul disentuh:** `vessel_voyage_operations`
**Depends on:** Sprint 9-11 (voyage, port call, noon report)

## Konteks
Melengkapi model pendukung terakhir (§3.8-3.9), lalu tutup keseluruhan security (terutama **record rule portal Nakhoda** yang sempat ditunda Sprint 11), cron (§4.5), dan email template (§4.6).

## Tasks

1. Model `vessel.cargo.document` — §3.8: `voyage_id` (required, cascade), `port_call_id` (opsional), `document_type` (bl/manifest/mate_receipt/cargo_damage_report/other), `document_number`, `document_date`, `qty_mt`, `attachment_ids`, `notes` (Html, khusus detail kerusakan untuk cargo_damage_report)
2. Model `vessel.voyage.delay` — §3.9: `voyage_id` (required, cascade), `port_call_id` (opsional — delay bisa di laut), `delay_type_id`, `datetime_start`/`datetime_end`, `duration_hours` (compute store), `description`, `impacts_laytime` (Boolean, **informasional saja, tidak ada logic otomatis** — sesuai keputusan desain §8 spec, delay TIDAK auto-sync ke SOF laytime `vessel_chartering`)
3. Update `vessel.voyage._compute_total_delay_hours`: sum `duration_hours` dari `delay_event_ids` — ganti placeholder Sprint 9
4. Update `action_complete` di voyage: sekarang validasi minimal 1 `cargo_document_ids` type=`bl` **kalau** `charter_contract_id.contract_type == 'voyage'` — ganti placeholder/skip Sprint 9
5. **Record rule portal Nakhoda** (§6, resolve open question §11.2): domain `[('voyage_id.vessel_id', 'in', user_assigned_vessel_ids)]` — implementasikan `user_assigned_vessel_ids` via related path `seafarer_id.employee_id.user_id` di `vessel.crew.assignment` (state=`on_board`). Buat record rule untuk `vessel.voyage` DAN `vessel.noon.report` (yang tertunda dari Sprint 11) dengan pola sama. **Jangan pakai placeholder domain kosong** — path `employee_id.user_id` sudah dikonfirmasi ada di `vessel_crew_management`
6. Security lengkap sisanya sesuai tabel §6: `group_voyage_ops_user` RWC voyage/port call/cargo document/delay + approve noon report; `group_voyage_ops_manager` full + override state; Finance read-only voyage & disbursement
7. Cron (§4.5) — 4 job: `_cron_noon_report_missing_alert` (harian, voyage sailing/at_port tanpa noon report approved 30 jam terakhir → activity Operations), `_cron_eta_reminder` (harian, port call eta H-2/H-0 tanpa ata → activity Operations), `_cron_clearance_pending_alert` (harian, clearance pending/submitted >2 hari sejak atb → activity Operations), `_cron_disbursement_variance_review` (mingguan, FDA confirmed dengan `reviewed=False` → reminder Finance)
8. Email template (§4.6) — 4 template: voyage fixed (internal), ETA reminder ke agen, noon report rejected (ke Nakhoda), variance PDA/FDA tinggi (ke Finance & Chartering Manager) — wired ke action terkait, pola sama seperti `vessel_chartering`
9. Views: tab "Cargo Documents" & "Delay Log" di form voyage, menu Operasional → Cargo Documents, menu Laporan → Delay Analysis (pivot: delay type × kapal × durasi)
10. **Unit test**: `duration_hours` compute delay, record rule portal (Nakhoda A tidak bisa lihat voyage kapal Nakhoda B — pakai 2 seafarer+assignment dummy dalam test)
11. Dummy data: 2-3 cargo document (termasuk 1 type=bl untuk salah satu voyage supaya `action_complete` bisa lulus), 2-3 delay event beda kategori

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_operations 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_voyage_operations -u vessel_voyage_operations 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

## Definition of Done
- [ ] Record rule portal terverifikasi: Nakhoda cuma lihat voyage kapal sendiri, tidak lihat punya orang lain (acceptance criteria §10.4) — test 2 user berbeda
- [ ] `action_complete` sekarang benar-benar block tanpa cargo document type=bl untuk voyage charter
- [ ] 4 cron jalan tanpa error (test manual via shell, sama pola seperti `vessel_chartering` Sprint 7)
- [ ] 4 email template terkirim di titik yang tepat
- [ ] Semua unit test pass, tidak ada regresi Sprint 8-12
