# Sprint 28 — vessel_bunker_management: Views Polish, Laporan & Acceptance Final

**Modul disentuh:** `vessel_bunker_management`
**Depends on:** Sprint 22-27 (semua model & workflow)

## Konteks
Sprint penutup — laporan tambahan (§5), polish views tersisa, jalankan seluruh 11 acceptance criteria §10 sebagai gate akhir, tutup roadmap 4-modul (`vessel_chartering` → `vessel_voyage_operations` → `vessel_voyage_pnl` → `vessel_bunker_management`).

## Tasks

1. Laporan tambahan (§5): "Price Analysis" (pivot/graph: quote/PO vs `vessel.bunker.price.reference`, group by supplier/fuel_type/bulan), "Dispute & Variance Summary" (pivot per supplier/surveyor — jumlah dispute, rata-rata variance_pct)
2. Polish form Inquiry — smart button Quotes/PO/Deliveries (semua count/link real, bukan placeholder invisible dari Sprint 23)
3. Polish smart button `rob_anomaly_count` di form `vessel.voyage` (extend Sprint 25) — pastikan tampil benar
4. Polish smart button `bunker_delivery_ids` count di form kapal (`fleet.vehicle`)
5. Menu lengkap sesuai §5 struktur penuh (Procurement / Delivery & Survey / Rekonsiliasi / Time Charter / Laporan / Konfigurasi) — cross-check tidak ada menu yang kepotong dari sprint sebelumnya
6. **Jalankan seluruh 11 poin Kriteria Penerimaan §10 tech spec** satu per satu, catat hasil per poin di `SPRINT_REPORT.md` (pola sama seperti sprint acceptance final modul-modul sebelumnya)
7. **Audit checklist §12.2 poin 13**:
   - `grep -rn "display_name" vessel_bunker_management/models/` (nihil sebagai field custom)
   - `grep -rn "fields.Datetime.from_string" vessel_bunker_management/` (nihil)
   - `grep -rn "@api.depends()" vessel_bunker_management/models/` (tidak ada depends kosong)
   - `grep -rn "_sql_constraints\s*=\|decoration-secondary\|expand=\"0\"\|\.groups_id\b" vessel_bunker_management/` (nihil — checklist gotcha CLAUDE.md lengkap)
   - Cek semua model baru yang pakai `message_post`/`activity_schedule` benar-benar `_inherit` mixin yang benar
   - Cek `ir.model.access.csv` prefix `vessel_bunker_management_`
   - Cek `vessel_chartering/__manifest__.py` tetap TIDAK depend ke modul ini (arah dependency satu arah, cross-check ulang final)
   - **Install ulang dari database bersih** (buat temp db, drop setelah verifikasi) dengan SEMUA modul (5 fleet + `vessel_chartering` + `vessel_voyage_operations` + `maritime` + `vessel_voyage_pnl` + `vessel_bunker_management` = 10 modul), `--test-enable`, zero ERROR/CRITICAL — **catatan dari pengalaman `vessel_voyage_pnl` Sprint 21**: fresh-install-dari-nol dengan `--test-enable` di database benar-benar kosong (auto-install banyak modul dependency Odoo standar) bisa memakan waktu SANGAT lama (~15+ menit hanya untuk registry load, lebih lama lagi untuk asset bundle generation + full test suite) — kalau di luar proporsi waktu wajar, cukup verifikasi update idempotent (`-u`) di database dev yang sudah berisi modul lain SEBAGAI bukti utama, dan install-dari-nol TANPA `--test-enable` sebagai bukti sekunder "tidak ada circular dependency/error struktural", didokumentasikan transparan di SPRINT_REPORT kalau full-test-suite-dari-nol tidak sempat diselesaikan penuh

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_bunker_management 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_bunker_management -u vessel_bunker_management 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

## Definition of Done — Checklist Acceptance Criteria §10 Tech Spec (jalankan semua)
- [ ] §10.1 Install bersih Odoo 19 tanpa error, tanpa konflik modul existing
- [ ] §10.2 Inquiry 3 quote → nominasi → PO ter-generate benar
- [ ] §10.3 BDN 500 MT, survey 495 MT, tolerance 0.5% → dispute otomatis, tidak bisa confirmed sebelum resolved
- [ ] §10.4 Setelah resolved → confirm → stock.picking qty 495 MT
- [ ] §10.5 ROB reconciliation: previous 200 + supply 495 - consumption 150 = expected 545, actual 500, variance -45, anomaly di threshold 8%
- [ ] §10.6 Time charter delivery event → draft BOD/BOR otomatis dengan ROB dari noon report terdekat
- [ ] §10.7 Settle BOD/BOR → bunker_adjustment terisi benar nilai & tanda
- [ ] §10.8 group_bunker_user tidak bisa resolve dispute maupun approve BOD/BOR settlement
- [ ] §10.9 Quote harga jauh di atas referensi → price_vs_market_pct signifikan
- [ ] §10.10 Semua unit test TransactionCase lulus
- [ ] §10.11 Audit bersih (display_name, fields.Datetime.from_string, @api.depends() kosong)

**Kalau semua 11 poin lulus → MVP `vessel_bunker_management` selesai, roadmap 4-modul TUNTAS.**

## Catatan Mode Autonomous
Sprint ini adalah PENUTUP roadmap modul keempat. Setelah Sprint 28 selesai: update SPRINT_REPORT.md ringkasan MVP, commit (lokal tiap sprint seperti biasa), kirim email otomatis, lalu **berhenti** — tidak ada Sprint 29 terdefinisi (modul roadmap berikutnya, kalau ada, belum ada tech spec-nya). Jalankan `/retro` untuk Sprint 22-28 setelah selesai (mengikuti pola retro tiap MVP modul selesai), lalu laporkan ke user bahwa siklus roadmap saat ini tuntas dan tunggu instruksi lanjutan. **Push ke `github` remote HANYA SEKALI di akhir**, setelah Sprint 28 selesai — bukan per-sprint (sama seperti aturan `vessel_voyage_pnl`).
