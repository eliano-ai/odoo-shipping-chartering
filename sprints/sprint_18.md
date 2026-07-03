# Sprint 18 — vessel_voyage_pnl: Estimate vs Actual + Vessel P&L Bulanan

**Modul disentuh:** `vessel_voyage_pnl`
**Depends on:** Sprint 17 (allocated cost lengkap)

## Konteks
§2.4 (variance vs estimate) dan §2.6/§3.4 (agregasi bulanan per kapal, termasuk idle cost).

## Tasks

1. Compute variance vs estimate (§2.4) di `vessel.voyage.pnl`: `revenue_variance`/`revenue_variance_pct` (vs `estimate_id.revenue_estimate`), `cost_variance`/`cost_variance_pct` (vs total cost estimate — cek field yang tepat di `vessel.voyage.estimate`, kemungkinan perlu jumlah beberapa field cost di model itu, grep dulu struktur real-nya sebelum implementasi), `tce_variance` (vs `estimate_id.tce_per_day`). Semua compute, tidak store perlu (ringan, tidak sering diakses masif)
2. Model `vessel.vessel.pnl` (§3.4) — `vessel_id`, `period_month`/`period_year`, `voyage_pnl_ids` (M2M compute — voyage yang overlap periode), `total_revenue`/`total_cost` (compute store, pro-rata kalau voyage overlap 2 bulan berdasar hari overlap), `idle_cost_allocated` (compute store — pool crew/maintenance/depresiasi yang tidak terserap voyage manapun di bulan itu), `net_result`, `calendar_days` (compute), `voyage_days_total` (compute), `utilization_pct` (compute store: `voyage_days_total / calendar_days × 100`), `avg_tce` (compute store, rata-rata tertimbang hari voyage), `state` (draft/closed). Constraint unique `(vessel_id, period_month, period_year)`
3. Logic `idle_cost_allocated` — pool bulanan kapal (crew/maintenance/depresiasi) dikurangi total yang sudah terserap `vessel.voyage.pnl.allocated_cost` voyage-voyage yang overlap bulan itu; sisanya = idle cost (kapal nganggur/menunggu fixture)
4. `_cron_generate_vessel_pnl` (§4.3, §4.5) — bulanan tanggal 5 (kasih waktu voyage bulan lalu selesai di-lock), generate/update `vessel.vessel.pnl` bulan sebelumnya per kapal aktif. **Pastikan model yang manggil `activity_schedule`/`message_post` di cron ini benar-benar `_inherit` mixin yang benar** (pelajaran retro Sprint 8-14 — cek SEBELUM install, bukan sesudah error)
5. Extend `fleet.vehicle`: `vessel_pnl_ids` (One2many, sudah di-placeholder Sprint 16, isi field beneran sekarang), `current_month_utilization_pct` (compute quick-info di form kapal)
6. Security access untuk `vessel.vessel.pnl`
7. Views: form/list `vessel.vessel.pnl`, pivot (kapal × bulan), graph (utilisasi & TCE trend), menu Vessel P&L → P&L Bulanan per Kapal + Utilisasi & TCE Trend
8. Dummy data: 2 voyage yang overlap bulan yang sama untuk 1 kapal (replikasi skenario acceptance criteria §10.7), generate `vessel.vessel.pnl` untuk bulan itu

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_pnl 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_voyage_pnl -u vessel_voyage_pnl 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

Cross-check §10.5 dan §10.7 SAAT INI.

## Definition of Done
- [ ] §10.5 acceptance criteria terpenuhi (voyage dengan estimate selected → 3 variance field terhitung benar)
- [ ] §10.7 acceptance criteria terpenuhi (2 voyage overlap bulan sama → agregasi benar, utilization_pct sesuai hari voyage vs hari kalender)
- [ ] Idle cost logic diverifikasi manual (kapal dengan voyage cuma sebagian bulan → sisa hari dihitung idle)
- [ ] Cron `_cron_generate_vessel_pnl` jalan tanpa error via shell manual
- [ ] Idempotent, install bersih, tidak ada regresi Sprint 15-17
