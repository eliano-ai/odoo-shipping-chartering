# Sprint 20 — vessel_voyage_pnl: Historical Backfill, Cron Lengkap & Email

**Modul disentuh:** `vessel_voyage_pnl`
**Depends on:** Sprint 15-19 (semua model & workflow inti)

## Konteks
Melengkapi cron tersisa (§4.5), 3 email template (§4.6), dan wizard bulk-generate P&L untuk voyage `completed` historis (keputusan user — sertakan di MVP, bukan cuma voyage baru ke depan).

## Tasks

1. Wizard `vessel.pnl.bulk.generate.wizard` (baru, di luar §12.1 struktur asli tapi sesuai keputusan user) — pilih rentang tanggal (opsional, default semua) + generate `vessel.voyage.pnl` untuk semua `vessel.voyage` state=completed yang belum punya `pnl_id`, masing-masing state=draft (Finance review manual sebelum lock, bukan auto-lock). Tombol akses dari menu Voyage P&L → Generate P&L Massal (atau letak lain yang masuk akal di §5 IA)
2. `_cron_pnl_pending_lock_alert` (§4.5) — mingguan, voyage P&L `state=computed` > 14 hari belum di-lock → activity ke Finance
3. 3 email template (§4.6, `mail.template`, `noupdate="1"`): P&L voyage siap review (ke Finance, trigger saat state jadi `computed`), variance estimate signifikan >25% (ke Chartering Manager — feedback akurasi estimasi, trigger saat P&L computed & `revenue_variance_pct`/`cost_variance_pct` melebihi threshold), budget variance tinggi (ke Fleet Manager, sudah ada activity dari Sprint 19, tambah email juga konsisten pola `vessel_voyage_operations`)
4. Wire email ke titik yang tepat: `action_compute` (voyage P&L jadi computed) kirim email siap-review, cek variance >25% kirim email terpisah kalau kondisinya terpenuhi
5. Security: pastikan wizard bulk generate & wizard adjustment (Sprint 17) punya access CSV lengkap
6. Dummy data: pastikan minimal 1 voyage completed lama (dari demo `vessel_chartering`) BELUM di-generate P&L-nya sebelum sprint ini — supaya wizard bulk-generate ada sesuatu untuk diverifikasi benar-benar generate sesuatu, bukan 0 hasil

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_voyage_pnl 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_voyage_pnl -u vessel_voyage_pnl 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

Manual via shell: jalankan wizard bulk-generate, cek jumlah `vessel.voyage.pnl` baru sesuai jumlah voyage completed yang sebelumnya belum punya pnl_id.

## Definition of Done
- [ ] Wizard bulk-generate P&L berhasil generate untuk voyage completed historis, tidak duplikat untuk voyage yang sudah punya pnl_id (idempotent by design, bukan cuma idempotent instalasi)
- [ ] 3 email template terdaftar dengan model target benar, terverifikasi via psql
- [ ] Semua cron (§4.5 lengkap: generate vessel pnl, pending lock alert, budget variance alert) terdaftar `active=true` dengan interval benar
- [ ] Idempotent, install bersih, tidak ada regresi Sprint 15-19
