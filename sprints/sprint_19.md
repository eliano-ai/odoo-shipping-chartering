# Sprint 19 — vessel_voyage_pnl: Budget

**Modul disentuh:** `vessel_voyage_pnl`
**Depends on:** Sprint 18 (vessel P&L bulanan — sumber `actual_amount` budget)

## Konteks
§2.7, §3.5-3.6 — rencana biaya per kapal per tahun, dibandingkan realisasi dari `vessel.vessel.pnl`. Threshold variance **configurable per kapal** sesuai keputusan user (field override di `fleet.vehicle`, sudah ditambahkan Sprint 15).

## Tasks

1. Model `vessel.vessel.budget` (§3.5) — `vessel_id`, `year`, `budget_line_ids`, `total_budget_cost` (compute), `total_actual_cost` (compute, dari `vessel.vessel.pnl` tahun berjalan), `state` (draft/approved). Constraint unique `(vessel_id, year)`
2. Model `vessel.vessel.budget.line` (§3.6) — `budget_id`, `month` (1-12), `cost_category_id`, `planned_amount`, `actual_amount` (compute, **on-the-fly tidak store berat** sesuai §4.4 — dari `vessel.vessel.pnl` bulan & kategori terkait), `variance_amount`/`variance_pct` (compute)
3. Logic threshold variance (§4.4, keputusan user): ambil `fleet_vehicle.budget_variance_threshold_pct` kalau terisi (>0), fallback ke `res.company.default_budget_variance_threshold_pct` (sudah di-seed Sprint 15) — pola identik `_check_variance_threshold` di `vessel.port.disbursement` (`vessel_voyage_operations` Sprint 12), **reuse pola yang sama** (termasuk idempotency guard skip user yang sudah punya activity)
4. `_cron_budget_variance_alert` (§4.5) — bulanan, budget line dengan variance > threshold → activity ke Fleet Manager. **Pastikan model punya mail.activity.mixin sebelum pakai activity_schedule — cross-check dulu, jangan asumsi** (pelajaran retro Sprint 8-14)
5. Security: `group_voyage_pnl_user` **tidak boleh** lihat menu Budget maupun generate/lock P&L (acceptance criteria §10.9) — access CSV harus benar-benar exclude group ini dari model budget, bukan cuma sembunyikan menu
6. Views: form budget (`budget_line_ids` inline editable per bulan × kategori), list, pivot (realisasi vs budget), menu Budget → Budget per Kapal + Realisasi vs Budget
7. Dummy data: 1 budget kapal dengan minimal 1 line variance di atas threshold (replikasi §10.8: planned 50,000, actual 65,000 → variance_pct 30%, threshold default 20%)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_pnl 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_voyage_pnl -u vessel_voyage_pnl 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

Cross-check §10.8 dan §10.9 SAAT INI — termasuk verifikasi eksplisit `group_voyage_pnl_user` (buat test user, coba akses budget, harus `AccessError`, pola sama seperti test portal isolation `vessel_voyage_operations` Sprint 13).

## Definition of Done
- [ ] §10.8 acceptance criteria terpenuhi persis (planned 50,000, actual 65,000 → variance_pct 30%, activity terkirim karena >20% threshold default)
- [ ] §10.9 acceptance criteria terpenuhi — `group_voyage_pnl_user` diverifikasi TIDAK bisa akses budget/generate/lock P&L (test eksplisit dengan `with_user`, bukan cuma asumsi dari access CSV)
- [ ] Threshold override per-kapal bekerja (beda hasil dibanding pakai default global — pola verifikasi sama seperti PDA/FDA Sprint 12 `vessel_voyage_operations`)
- [ ] Idempotent, install bersih, tidak ada regresi Sprint 15-18
