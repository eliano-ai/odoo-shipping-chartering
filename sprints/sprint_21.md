# Sprint 21 — vessel_voyage_pnl: Views Polish, Dashboard Direksi & Acceptance Final

**Modul disentuh:** `vessel_voyage_pnl`
**Depends on:** Sprint 15-20 (semua model & workflow)

## Konteks
Sprint penutup — dashboard direksi (§5) via `spreadsheet_dashboard` (**sudah terinstall di environment ini**, jadi build penuh sesuai spec, bukan fallback), polish views tersisa, jalankan seluruh 11 acceptance criteria §10 sebagai gate akhir.

## Tasks

1. Dashboard Direksi (`spreadsheet_dashboard`) — utilisasi armada (%), TCE trend per kapal (dari `vessel.vessel.pnl.avg_tce`), top 10 voyage rugi (`vessel.voyage.pnl` sorted `voyage_result` asc), demurrage receivable outstanding (dari `vessel_chartering` — cek field yang tepat, kemungkinan `demurrage_amount_total` yang belum invoiced), realisasi vs budget ringkas
2. Laporan tambahan (§5): "Top Voyage Rugi" (list sorted `voyage_result` asc), "Estimate vs Actual" (list/pivot variance per komponen)
3. Polish form Voyage P&L — notebook lengkap (Revenue Detail/Direct Cost Detail/Allocated Cost Detail/Estimate vs Actual/Adjustment Manual), smart button ke Voyage/Kontrak Charter/Estimate (semua count/link real)
4. Polish smart button `pnl_id` di form `vessel.voyage` (extend dari Sprint 16) — pastikan tampil benar kalau sudah generate, invisible kalau belum
5. Menu lengkap sesuai §5 struktur penuh (Voyage P&L / Vessel P&L / Budget / Laporan / Konfigurasi) — cross-check tidak ada menu yang kepotong dari sprint sebelumnya
6. **Keputusan menu root Voyage P&L** (dari Sprint 15 task 7, kalau belum diputuskan): finalisasi apakah masuk app `maritime` atau tetap `fleet.menu_root` — kalau masuk `maritime`, tambah `depends: ['maritime']` dan reparent menu via xmlid (pola sama restrukturisasi Maritime kemarin)
7. **Jalankan seluruh 11 poin Kriteria Penerimaan §10 tech spec** satu per satu, catat hasil per poin di `SPRINT_REPORT.md` (pola sama seperti Sprint 7 `vessel_chartering` dan Sprint 14 `vessel_voyage_operations`)
8. **Audit checklist §12.2 poin 13**:
   - `grep -rn "display_name" vessel_voyage_pnl/models/` (nihil sebagai field custom)
   - `grep -rn "fields.Datetime.from_string" vessel_voyage_pnl/` (nihil)
   - `grep -rn "@api.depends()" vessel_voyage_pnl/models/` (tidak ada depends kosong)
   - `grep -rn "_sql_constraints\s*=" vessel_voyage_pnl/models/` (nihil — pakai models.Constraint)
   - `grep -rn "decoration-secondary\|\.groups_id\b" vessel_voyage_pnl/` (nihil)
   - Cek semua model baru yang pakai `message_post`/`activity_schedule` benar-benar `_inherit` mixin yang benar
   - Cek `ir.model.access.csv` prefix `vessel_voyage_pnl_`
   - **Install ulang dari database bersih** (buat temp db, drop setelah verifikasi — pola sama Sprint 14) dengan SEMUA modul (5 fleet + `vessel_chartering` + `vessel_voyage_operations` + `maritime` + `vessel_voyage_pnl` = 9 modul), `--test-enable`, zero ERROR/CRITICAL

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_pnl 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_voyage_pnl -u vessel_voyage_pnl 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

Manual (browser, dashboard `spreadsheet_dashboard` tidak sepenuhnya bisa diverifikasi via shell/curl): buka Dashboard Direksi, cek widget utilisasi/TCE trend/top voyage rugi/demurrage outstanding tampil data benar sesuai dummy data.

## Definition of Done — Checklist Acceptance Criteria §10 Tech Spec (jalankan semua)
- [ ] §10.1 Install bersih Odoo 19 tanpa error, tanpa konflik `vessel_chartering`/`vessel_voyage_operations`/5 modul fleet — **fresh DB test 9 modul bareng**
- [ ] §10.2 Freight+demurrage → total_revenue benar
- [ ] §10.3 Bunker cost dari fleet_fuel_log dengan traceability line_ids
- [ ] §10.4 Alokasi crew cost per_voyage_day: pool 30,000, 10/30 hari → allocated 10,000
- [ ] §10.5 Estimate selected → 3 variance field benar
- [ ] §10.6 Lock → read-only, adjustment manual tetap bisa dengan alasan wajib
- [ ] §10.7 2 voyage overlap bulan sama → agregasi & utilization_pct benar
- [ ] §10.8 Budget variance 30% > threshold 20% → activity ke Fleet Manager
- [ ] §10.9 group_voyage_pnl_user tidak bisa akses Budget/generate/lock P&L
- [ ] §10.10 Semua unit test TransactionCase lulus
- [ ] §10.11 Audit bersih (display_name, fields.Datetime.from_string, @api.depends() kosong)

**Kalau semua 11 poin lulus → MVP `vessel_voyage_pnl` selesai.**

## Catatan Mode Autonomous
Sprint ini adalah PENUTUP roadmap Layer 2/3 yang sudah direncanakan (`vessel_chartering` → `vessel_voyage_operations` → `vessel_voyage_pnl`). Setelah Sprint 21 selesai: update SPRINT_REPORT.md ringkasan MVP, commit+push, kirim email otomatis, lalu **berhenti** (tidak ada Sprint 22 terdefinisi — modul roadmap berikutnya, `vessel_bunker_management`, belum ada tech spec-nya). Jalankan `/retro` untuk Sprint 15-21 setelah selesai (mengikuti pola retro tiap MVP modul selesai), lalu laporkan ke user bahwa siklus roadmap saat ini tuntas dan tunggu instruksi lanjutan (tech spec modul berikutnya, atau prioritas lain).
