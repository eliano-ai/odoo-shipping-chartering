# Sprint 24 — vessel_bunker_management: BDN, Survey, Dispute & Stock Integration

**Modul disentuh:** `vessel_bunker_management`
**Depends on:** Sprint 23 (procurement, PO)

## Konteks
BDN + independent survey + dispute tracking (§4.2) — bagian anti-fraud pertama. Ikuti saran §12.2 poin 5-6: state machine dispute dulu, baru integrasi stock.

## Tasks

1. Model `vessel.bunker.delivery` (§3.4) — `inquiry_id`, `vessel_id`/`port_id` (related store), `bdn_number`, `bdn_date`, `delivery_datetime`, `fuel_type_id`, `qty_bdn_mt`, `density`, `temperature_c`, `sulfur_content_pct`, `attachment_ids`, `survey_id` (0..1), `qty_confirmed_mt` (compute: `survey_id.survey_qty_mt` kalau ada, else `qty_bdn_mt`), `stock_picking_id` (readonly, placeholder — diisi task 6), `account_move_id` (related dari `inquiry_id.purchase_order_id`, readonly), `state` (draft/delivered/surveyed/disputed/confirmed). Constraint `qty_bdn_mt > 0`
2. Model `vessel.bunker.survey` (§3.5) — `delivery_id`, `surveyor_id`, `survey_date`, `survey_qty_mt`, `survey_density`, `variance_qty_mt` (compute store), `variance_pct` (compute store), `tolerance_pct` (default dari `res.company.default_bdn_survey_tolerance_pct` Sprint 22), `is_dispute` (compute store: `abs(variance_pct) > tolerance_pct`), `dispute_state` (open/resolved), `resolution_notes` (Html, wajib sebelum resolved), `attachment_ids`
3. **State machine dispute** (§4.2): saat `survey_id` diisi dan `is_dispute=True` → `delivery.state` otomatis pindah `disputed`; constraint tolak transisi ke `confirmed` selama `state='disputed'` dan `dispute_state != 'resolved'`. **Test case eksplisit variance DI ATAS dan DI BAWAH tolerance** (§12.4 syarat khusus modul ini — jangan cuma test jalur normal)
4. Tombol **resolve dispute** (`action_resolve_dispute`, group_bunker_manager only) — wajib `resolution_notes` terisi, set `dispute_state='resolved'`, `delivery.state` kembali ke `surveyed`
5. Tombol **"Konfirmasi Penerimaan"** (`action_confirm_delivery`) — guard: tidak bisa jalan kalau masih `disputed` & belum resolved; buat `stock.location` per kapal kalau belum ada (`fleet.vehicle.bunker_stock_location_id`, keputusan teknis Sprint 22 — auto-create child dari parent lokasi "Vessels" yang juga dibuat sekali via data XML kalau belum ada), auto-create `stock.picking` (incoming, qty = `qty_confirmed_mt`, destination = lokasi kapal), set `state='confirmed'`
6. Extend `fleet.vehicle`: `bunker_stock_location_id` (M2O `stock.location`, compute+store atau lazy-create — pilih pendekatan yang idempotent-safe untuk demo data reload)
7. Security access untuk `vessel.bunker.delivery` & `vessel.bunker.survey`, termasuk guard `group_bunker_user` tidak bisa `action_resolve_dispute` (cross-check §10.8 di sprint ini juga, jangan tunda semua ke akhir)
8. Views: form delivery (info BDN, tombol Confirm/tautan survey), form survey (indikator warna dispute), list filter "Dispute Terbuka" (`is_dispute=True`, `dispute_state='open'`)
9. Dummy data: replikasi **persis** §10.3/§10.4 acceptance criteria — BDN 500 MT, survey 495 MT, tolerance 0.5% → `is_dispute=True`, resolve dispute, confirm → `stock.picking` qty 495 MT (bukan 500)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_bunker_management 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_bunker_management -u vessel_bunker_management 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

Cross-check §10.3, §10.4, dan §10.8 (bagian dispute) SAAT INI.

## Definition of Done
- [ ] §10.3 acceptance criteria persis (500 MT BDN, survey 495 MT, tolerance 0.5% → `is_dispute=True`, tidak bisa confirmed sebelum resolved)
- [ ] §10.4 acceptance criteria persis (setelah resolved, confirm → `stock.picking` qty 495 MT)
- [ ] Test variance di atas DAN di bawah tolerance, dua-duanya lulus
- [ ] `group_bunker_user` diverifikasi eksplisit tidak bisa resolve dispute (`with_user`, bukan asumsi)
- [ ] Idempotent, install bersih, tidak ada regresi Sprint 22-23
