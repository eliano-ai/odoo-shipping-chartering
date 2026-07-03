# Sprint 10 — vessel_voyage_operations: Port Call & Clearance Checklist

**Modul disentuh:** `vessel_voyage_operations`
**Depends on:** Sprint 9 (`vessel.voyage`)

## Konteks
Port rotation multi-port (§2.2, §3.3) + clearance checklist otomatis (§2.4, §3.7, §4.3).

## Tasks

1. Model `vessel.port.call` — semua field §3.3: `voyage_id` (required, cascade), `sequence`, `port_id` (domain `is_port=True`), `call_purpose` (load/discharge/bunkering/transit/layup/other), `agent_id` (domain `is_port_agent=True`), `eta`/`etb`/`etd`, `ata`/`atb`/`atd`, `berth_name`, `cargo_ops_commenced`/`cargo_ops_completed`, `cargo_ops_rate_mt_day` (compute, placeholder 0 — diisi Sprint 12 setelah cargo_document_ids ada), `notes`
2. Constraint: `etb>=eta`, `etd>=etb` jika terisi; sama untuk `atb`/`ata`/`atd` — **warning bukan blokir** (data lapangan tidak ideal, sesuai spec eksplisit)
3. Model `vessel.port.clearance.line` — §3.7: `port_call_id` (required, cascade), `document_type_id`, `direction` (in/out), `status` (pending/submitted/cleared/rejected), `cleared_date`, `document_number`, `attachment_ids`
4. Logic §4.3: saat `vessel.port.call` dibuat dengan `call_purpose` terisi, auto-generate `clearance_line_ids` dari `vessel.clearance.document.type` yang `default_required=True`, masing-masing untuk `direction='in'` dan `direction='out'` (jadi kalau ada 3 tipe default_required, otomatis jadi 6 baris clearance: 3 in + 3 out)
5. Update `vessel.voyage`: toggle `action_arrive_port`/`action_depart_port` sekarang benar-benar pakai `port_call_id` aktif (isi `atb`/`atd` di port call yang sesuai, bukan cuma placeholder Sprint 9)
6. Update constraint `action_complete` di voyage: sekarang **benar-benar validasi** semua `port_call_ids` punya `atd` terisi (kecuali port terakhir/final cukup `atb`) — sesuai §4.1, ganti dari placeholder skip Sprint 9
7. Security access untuk `vessel.port.call` & `vessel.port.clearance.line`
8. Views: tab "Port Rotation" di form voyage (list inline `port_call_ids` editable, sequence handle), form port call terpisah dengan clearance checklist inline, menu Operasional → Port Calls (list, calendar by eta)
9. Dummy data: tambahkan 2-3 port call ke voyage dummy Sprint 9 (sequence 1,2,3), beda `call_purpose`, cek clearance line auto-generate

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_operations 2>&1 | grep -E "ERROR|CRITICAL"
```

Manual: buat 3 port call berurutan (acceptance criteria §10.3 tech spec) — cek urutan tampil benar, tidak error.

## Definition of Done
- [ ] 3 port call berurutan (sequence 1-3) dengan ETA/ATA beda — tidak error, urutan benar (acceptance criteria §10.3)
- [ ] Auto-generate clearance line terverifikasi — jumlah baris = 2 × jumlah `default_required=True` document type
- [ ] `action_complete` voyage sekarang benar-benar block kalau ada port call tanpa `atd` (kecuali port terakhir) — acceptance criteria §10.8, diverifikasi raise error jelas
- [ ] Idempotent
