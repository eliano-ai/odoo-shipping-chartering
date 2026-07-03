# Sprint 11 — vessel_voyage_operations: Noon Report & Approval Workflow

**Modul disentuh:** `vessel_voyage_operations`
**Depends on:** Sprint 9 (`vessel.voyage`)

## Konteks
Input harian Nakhoda (§2.3, §3.4) — sumber data utama CII masa depan, approval workflow dengan validasi soft (§4.2). **Frekuensi fixed 24 jam** (sudah diputuskan user, bukan configurable).

## Tasks

1. Model `vessel.noon.report` — semua field §3.4: `voyage_id` (required, cascade), `report_datetime`, `report_type` (noon_at_sea/noon_in_port/arrival/departure/sosp_eosp), `latitude`/`longitude` (digits=(10,6)), `course_deg`, `speed_knots`, `distance_run_nm`, `distance_to_go_nm`, ROB (`rob_fo`/`rob_do`/`rob_fw`/`rob_lube_oil`), cuaca (`wind_force_bft` 0-12, `sea_state`, `rpm`, `slip_pct`), approval (`state`, `approved_by`, `approved_date`, `rejection_reason`), `source` (portal/manual/email_parsed — MVP cuma portal & manual dipakai aktif, `email_parsed` sekadar ada di selection untuk future-proof, **jangan implementasi logicnya**)
2. Constraint: `latitude` -90..90, `longitude` -180..180; unique `voyage_id`+`report_datetime` (cegah duplikat input)
3. Workflow (§4.2): `draft`→`submitted` (Nakhoda action_submit)→`approved`/`rejected` (Operations, wajib `rejection_reason` kalau reject). **Approved/rejected read-only** — override `write()` untuk block edit kalau state in (approved, rejected), kecuali field administratif tertentu jika ada (untuk MVP: block total, re-submit = record baru)
4. Validasi warning saat approve (bukan blokir): (a) gap dengan noon report approved sebelumnya >30 jam → message_post warning; (b) `rob_fo`/`rob_do` naik dari laporan sebelumnya tanpa event bunkering tercatat di `port_call_ids` (`call_purpose='bunkering'` dengan ATB/ATD di rentang waktu terkait) → message_post warning
5. Update `vessel.voyage._compute_total_distance_nm`: sum `distance_run_nm` dari `noon_report_ids` yang approved — ganti dari placeholder Sprint 9
6. Update `fleet.vehicle._compute_current_position`: ambil `latitude`/`longitude` dari noon report approved terakhir milik `current_voyage_id` — ganti dari placeholder Sprint 9
7. Security access `vessel.noon.report`: portal Nakhoda cuma create/write punya sendiri (record rule ditunda ke Sprint 13 — Sprint ini pakai access dasar group_voyage_ops_user/manager dulu, portal group ditambah access CSV tapi record rule-nya nanti)
8. Views: form noon report (layout 1 halaman ringkas sesuai §5 — header, section Posisi&Kecepatan, section ROB, section Cuaca&Performa, read-only total setelah approved), tab "Noon Reports" di form voyage (smart button + list), menu Operasional → Noon Reports (filter Pending Approval)
9. **Unit test** `TransactionCase`: (a) `total_distance_nm` compute benar dari beberapa noon report approved, (b) noon report rejected → record lama tetap ada, Nakhoda bisa buat baru (histori tidak hilang), (c) constraint lat/long range, (d) constraint unique voyage+datetime
10. Dummy data: 4-5 noon report untuk voyage dummy yang `sailing`, variasi state (approved mayoritas, 1 rejected+1 baru sebagai re-submit contoh)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_operations 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_voyage_operations -u vessel_voyage_operations 2>&1 | grep -E "FAIL|ERROR|OK|tests when loading"
```

## Definition of Done
- [ ] Approve noon report → record read-only, muncul di `total_distance_nm` voyage (acceptance criteria §10.5)
- [ ] Reject → Nakhoda bisa buat record baru, record lama tetap tersimpan sebagai histori tidak terhapus (acceptance criteria §10.6)
- [ ] Semua unit test pass
- [ ] Warning gap>30h dan ROB naik tanpa bunkering terverifikasi manual (tidak block, cuma message_post)
- [ ] Idempotent
