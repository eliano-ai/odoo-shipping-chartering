# Sprint 17 — vessel_voyage_pnl: Allocated Cost & Alokasi Logic

**Modul disentuh:** `vessel_voyage_pnl`
**Depends on:** Sprint 16 (revenue & direct cost)

## Konteks
Bagian paling kompleks tech spec (§2.3, §4.1, §4.2) — alokasi biaya tidak langsung (crew, maintenance, depresiasi, overhead) yang tidak melekat ke satu voyage. **Ingat**: crew cost & depreciation di environment ini SELALU `manual` (hr_payroll/account_asset tidak ada) — method lain (`per_voyage_day`, `equal_split`, `fixed_percentage`) tetap harus diimplementasi penuh untuk kategori yang punya sumber data (Maintenance dari `fleet_maintenance_schedule`, Overhead dari `fixed_percentage`).

## Tasks

1. `_compute_allocated_cost()` di `vessel.voyage.pnl` — method **modular, satu function per `allocation_method`** (§12.2 poin 4 tech spec, supaya gampang tambah metode baru fase 2): `_allocate_per_voyage_day()`, `_allocate_per_calendar_day()` (bisa skip implementasi detail penuh untuk MVP kalau kompleks, tapi function stub-nya harus ada dengan `NotImplementedError`/fallback yang jelas — cek dulu apakah spec MVP scope benar-benar butuh ini atau boleh Fase 2 murni, lihat §9 tabel Fase), `_allocate_equal_split()`, `_allocate_fixed_percentage()`, `_allocate_manual()` (no-op, biarkan Finance isi manual di adjustment line)
2. Implementasi lengkap `per_voyage_day`: pool biaya bulanan kapal (dari `fleet_maintenance_schedule.actual_cost` untuk Maintenance) × (hari voyage ini dalam bulan `date_departure` / total hari kapal aktif bulan itu — **pool diambil dari bulan `date_departure` saja untuk MVP**, sesuai keputusan §4.2/§11 poin 2 tech spec, voyage lintas-bulan presisi pro-rata di fase 2)
3. Implementasi `equal_split`: pool dibagi rata ke semua voyage aktif kapal itu dalam periode yang sama, tanpa mempertimbangkan durasi
4. Implementasi `fixed_percentage`: overhead = `fixed_percentage_value × total_revenue`
5. `crew_cost_allocated`/`depreciation_allocated` — karena `vessel.cost.allocation.rule` untuk kategori ini di-seed `manual` (Sprint 15), pastikan `_compute_allocated_cost()` tidak error kalau tidak ada sumber data otomatis — nilai default 0.0, Finance isi via adjustment line kalau perlu
6. Tombol **"Lock"** (Finance/Manager only, group check via `has_group`) — set `state='locked'`, semua field header jadi read-only **di level VIEW** (bukan override `write()` — pelajaran retro Sprint 8-14: override write() memecah idempotency demo data)
7. Wizard `vessel.pnl.adjustment.wizard` (§4.1) — muncul saat `state='locked'`, input `cost_category_id`+`amount`+alasan wajib, create `vessel.voyage.pnl.line` dengan `is_manual_adjustment=True`, tercatat di chatter (`mail.thread` — **pastikan model `vessel.voyage.pnl` benar-benar `_inherit mail.thread` dari Sprint 16**, cross-check dulu)
8. `voyage_result` (compute store: `total_revenue - total_direct_cost - total_allocated_cost`) dan `tce_actual_per_day` (compute store: `(total_revenue - total_direct_cost) / voyage_days` — **exclude allocated cost**, sesuai keputusan user)
9. Security access untuk wizard adjustment
10. Views: notebook tab "Allocated Cost Detail" + "Adjustment Manual" di form P&L, tombol Lock/Recompute di header, wizard form
11. **Unit test** minimal 3 test case dengan angka BEDA untuk membuktikan formula alokasi benar secara matematis (§12.4 tech spec — syarat khusus modul ini, bukan cuma "tidak error"): (a) `per_voyage_day` — pool 30,000, voyage 10 hari dari 30 hari kapal aktif → allocated 10,000 (persis acceptance criteria §10.4), (b) `equal_split`, (c) `fixed_percentage`
12. Dummy data: update voyage P&L demo dari Sprint 16 dengan skenario alokasi lengkap — replikasi persis acceptance criteria §10.4 (pool bulanan kapal USD 30,000, voyage 10 hari dari 30 hari kapal aktif)

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_pnl 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_voyage_pnl -u vessel_voyage_pnl 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

Cross-check §10.4 dan §10.6 SAAT INI (jangan tunda ke sprint terakhir).

## Definition of Done
- [ ] §10.4 acceptance criteria terpenuhi persis (pool 30,000, 10/30 hari → allocated 10,000)
- [ ] §10.6 acceptance criteria terpenuhi (Lock → field read-only, adjustment manual tetap bisa dengan alasan wajib tercatat chatter)
- [ ] Minimal 3 test case alokasi dengan angka berbeda, semua pass
- [ ] Lock diimplementasi via VIEW readonly, bukan override write() Python — cross-check eksplisit sebelum commit
- [ ] Idempotent, install bersih, tidak ada regresi Sprint 15-16
