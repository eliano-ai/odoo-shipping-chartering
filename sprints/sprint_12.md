# Sprint 12 — vessel_voyage_operations: Port Disbursement (PDA/FDA) & Variance

**Modul disentuh:** `vessel_voyage_operations`
**Depends on:** Sprint 10 (`vessel.port.call`)

## Konteks
PDA (estimasi) vs FDA (final) per port call, satu model dibedakan `disbursement_type` (§3.5-3.6, §4.4) — pola sama seperti direction di `vessel_chartering`. **Threshold variance configurable per port/klien** (sudah diputuskan user) dengan fallback global.

## Tasks

1. Model `vessel.port.disbursement` — §3.5: `port_call_id` (required, cascade), `disbursement_type` (pda/fda), `agent_id` (related dari port_call, store), `currency_id` (default USD atau ikut kebiasaan agen — biarkan manual default company currency), `line_ids`, `total_amount` (compute sum line), `variance_amount` (compute, **hanya terisi di record fda**: fda.total − pda.total dari `port_call_id` yang sama), `variance_pct` (compute), `state` (draft/confirmed), `document_ids` (Many2many ir.attachment)
2. Model `vessel.port.disbursement.line` — §3.6: `disbursement_id` (required, cascade), `item_type_id`, `description`, `amount`
3. Compute `variance_amount`/`variance_pct`: cari record `pda` dengan `port_call_id` sama, hitung selisih — **hanya jalan kalau kedua record (pda & fda) ada dan `state='confirmed'`**, kalau pda belum ada return 0 dengan catatan (bukan error)
4. Logic §4.4: saat FDA `state=confirmed`, hitung `variance_amount`. Ambil threshold: `port_call_id.port_id.disbursement_variance_threshold_pct` kalau terisi (>0), fallback ke `res.company.default_disbursement_variance_threshold_pct`. Kalau `variance_pct` > threshold → `activity_schedule` ke Chartering Manager & Finance
5. Field `reviewed` (Boolean, default False) di `vessel.port.disbursement` — dipakai cron Sprint 13 untuk reminder FDA yang variance-nya belum direview
6. Security access untuk kedua model, plus record rule: Nakhoda (portal) **tidak boleh lihat** disbursement sama sekali (sesuai §6 tabel security)
7. Views: form disbursement dengan line inline editable, tab "Disbursement (PDA/FDA)" di form port call, menu Finansial Pendukung → Disbursement (PDA/FDA) (list filter by type) + Variance Report (pivot: port call × PDA vs FDA)
8. **Unit test**: buat PDA 5 line item, lalu FDA dengan total 20% lebih tinggi → `variance_amount` & `variance_pct` benar, activity terkirim (acceptance criteria §10.7 — replikasi persis skenario tech spec)
9. Dummy data: PDA+FDA untuk 1-2 port call dummy, salah satu dengan variance di atas threshold (untuk demo activity), satu dengan threshold override di level port

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
- [ ] PDA 5 line + FDA +20% → variance_amount & variance_pct benar, activity ke Finance (acceptance criteria §10.7), diverifikasi test + manual dummy data
- [ ] Threshold per-port override bekerja (beda hasil activity/tidak dibanding pakai default global)
- [ ] Nakhoda (portal) tidak bisa akses disbursement sama sekali
- [ ] Idempotent, semua test pass tanpa regresi Sprint 8-11
