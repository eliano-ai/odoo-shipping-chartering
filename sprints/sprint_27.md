# Sprint 27 — vessel_bunker_management: Cron Lengkap & Email

**Modul disentuh:** `vessel_bunker_management`
**Depends on:** Sprint 22-26 (semua model & workflow inti)

## Konteks
Melengkapi cron tersisa (§4.5 — `_cron_generate_rob_reconciliation` sudah Sprint 25) dan mail template (§4.6).

## Tasks

1. `_cron_quote_validity_reminder` (harian) — quote `validity_date` H-1 tanpa nominasi (`inquiry.state` belum `nominated`) → activity ke Bunker Staff (`group_bunker_user` members atau `inquiry.create_uid`, tentukan pendekatan paling masuk akal)
2. `_cron_rob_anomaly_alert` (harian) — reconciliation `is_anomaly=True` state masih `draft` > 2 hari → escalate activity ke Fleet Manager (`fleet.fleet_group_manager`)
3. `_cron_dispute_followup` (mingguan) — survey `dispute_state='open'` > 7 hari → reminder ke Bunker Manager (`group_bunker_manager`)
4. **Semua cron di atas WAJIB cross-check mixin sebelum implementasi** (pelajaran retro `vessel_voyage_pnl` Sprint 8-14 & 15-21 — `vessel.bunker.inquiry` sudah `mail.activity.mixin` dari Sprint 22, `vessel.bunker.rob.reconciliation` dari Sprint 25, `vessel.bunker.survey`/`vessel.bunker.delivery` **cek dulu** apakah perlu ditambah mixin untuk `_cron_dispute_followup` — kemungkinan besar `vessel.bunker.delivery` sudah `mail.thread` dari Sprint 24 tapi belum tentu `mail.activity.mixin`, tambahkan kalau perlu)
5. 4 email template (`mail.template`, `noupdate="1"`): inquiry terkirim ke supplier (trigger `action_send_inquiry`... **tapi cek ulang desain Sprint 23 task 5** — inquiry terkirim ke market secara umum, bukan per-quote karena quote belum ada saat itu; kemungkinan template ini lebih tepat trigger saat quote diinput mengonfirmasi harga ke internal, bukan email KE supplier — evaluasi ulang & dokumentasikan keputusan final), dispute terbuka (ke Bunker Manager & Finance, trigger saat `is_dispute=True`), ROB anomaly terdeteksi (ke Fleet Manager, trigger dari cron poin 2), BOD/BOR siap settle (ke Chartering Manager, trigger saat BOD/BOR `state='confirmed'`)
6. Wire email ke titik yang tepat (bukan cuma di cron — beberapa trigger di action langsung, sama pola `vessel_voyage_pnl` Sprint 20)
7. Security: pastikan semua model yang dipakai cron (`vessel.bunker.inquiry`, `vessel.bunker.rob.reconciliation`, `vessel.bunker.survey`) punya access CSV lengkap untuk cron jalan sebagai user teknis
8. Dummy data: pastikan ada minimal 1 skenario tiap cron bisa nemu sesuatu untuk diverifikasi (quote H-1 tanpa nominasi, reconciliation anomaly draft, dispute terbuka >7 hari — mungkin perlu manipulasi tanggal dummy data supaya "sudah lewat" relatif ke hari ini)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_bunker_management 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_bunker_management -u vessel_bunker_management 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

Manual via shell: jalankan tiap cron method langsung, cek activity/mail.mail ter-generate sesuai skenario dummy data.

## Definition of Done
- [ ] 3 cron baru (quote validity, ROB anomaly, dispute followup) terdaftar `active=true` interval benar, teruji manual via shell tanpa error
- [ ] 4 mail template terdaftar model target benar, diverifikasi via psql
- [ ] Semua model yang dipakai cron dikonfirmasi punya mixin yang benar SEBELUM cron dijalankan (bukan sesudah error)
- [ ] Idempotent, install bersih, tidak ada regresi Sprint 22-26
