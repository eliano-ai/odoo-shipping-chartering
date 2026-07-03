# Sprint 26 — vessel_bunker_management: BOD/BOR Settlement (Time Charter)

**Modul disentuh:** `vessel_bunker_management`
**Depends on:** Sprint 22-25 (foundation lengkap; BOD/BOR tidak depend langsung ke ROB reconciliation, tapi butuh noon report untuk ROB di titik delivery/redelivery)

## Konteks
Menyelesaikan item MVP yang sengaja dibiarkan manual di `vessel_chartering`: field `bunker_adjustment` di `vessel.hire.statement.line` (§2.6, §3.7, §4.4). **Arah dependency harus dijaga satu arah** (§8 keputusan desain) — `vessel_chartering` TIDAK boleh depend balik ke `vessel_bunker_management`.

## Tasks

1. Model `vessel.bunker.bod.bor` (§3.7) — `contract_id` (M2O `vessel.charter.contract`, domain `contract_type='time'`), `event_type` (delivery/redelivery), `event_date` (related dari `contract_id.delivery_date`/`redelivery_date` — **cek dulu field real ini ada di `vessel.charter.contract`**, jangan asumsi nama), `rob_fo`/`rob_do` (Float, default dari noon report terdekat dengan `event_date`, editable override), `price_source` (last_purchase/market_reference/manual), `price_fo_usd_mt`/`price_do_usd_mt` (terisi sesuai price_source), `settlement_amount` (compute: `(rob_fo × price_fo) + (rob_do × price_do)`), `settlement_direction` (compute: delivery→positif charterer bayar owner, redelivery→negatif), `hire_statement_line_id` (M2O `vessel.hire.statement.line`), `state` (draft/confirmed/settled)
2. Logic `price_source`: `last_purchase` — cari `vessel.bunker.delivery` (state=confirmed) terakhir sebelum `event_date` untuk `contract_id.vessel_id`, ambil harga dari PO/quote terkait; `market_reference` — dari `vessel.bunker.price.reference` tanggal terdekat sebelum `event_date`; `manual` — user isi langsung. Method terpisah per source (modular, pola sama alokasi cost `vessel_voyage_pnl`)
3. **Hook di `vessel.charter.contract`** (extend model, §12.2 poin 8) — method dipanggil saat `delivery_date`/`redelivery_date` ter-set (via `write()` override **HATI-HATI**: jangan sampai kena pola bug idempotency demo data seperti Sprint 11 `vessel_voyage_pnl` — guard idempotency di level method bunker yang dipanggil, BUKAN blokir write kontrak) yang create draft `vessel.bunker.bod.bor` sesuai `event_type`. **Arah panggilan**: `vessel_charter_contract.py` di modul INI (vessel_bunker_management, extend `_inherit = 'vessel.charter.contract'`) yang override `write()`/tambah logic — BUKAN `vessel_chartering` yang dimodifikasi untuk tahu tentang bunker (jaga arah dependency satu arah persis seperti didokumentasikan §8/§12.2 poin 8)
4. Tombol **"Settle ke Hire Statement"** (`action_settle`, hanya aktif state='confirmed', group_bunker_manager approve) — tulis `settlement_amount` (dengan tanda sesuai `settlement_direction`) ke `hire_statement_line_id.bunker_adjustment`, set `state='settled'`
5. Extend `vessel.charter.contract`: `bod_bor_ids` (One2many, hanya relevan `contract_type='time'`)
6. Extend `vessel.hire.statement.line`: `bod_bor_id` (M2O `vessel.bunker.bod.bor`, compute — referensi sumber kalau `bunker_adjustment` diisi otomatis)
7. Security access untuk `vessel.bunker.bod.bor`, guard `group_bunker_user` tidak bisa approve settlement (cross-check §10.8 bagian BOD/BOR di sprint ini)
8. Views: form BOD/BOR (info event, price source, settlement), list, menu Time Charter → BOD/BOR Settlement
9. Dummy data: replikasi **persis** §10.6/§10.7 acceptance criteria — kontrak time charter dengan `delivery_date` ter-set → draft BOD/BOR ter-generate otomatis dengan ROB dari noon report terdekat; settle → `bunker_adjustment` di hire statement line terisi dengan nilai & tanda benar. **Perlu kontrak time charter demo yang punya `delivery_date` DAN noon report approved di sekitar tanggal itu** — cek demo data `vessel_chartering`/`vessel_voyage_operations` existing, kemungkinan perlu tambah baru kalau belum ada kombinasi yang pas

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_bunker_management 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_bunker_management -u vessel_bunker_management 2>&1 | grep -E "FAIL|ERROR|tests when loading"

# Pastikan vessel_chartering TIDAK ikut berubah manifest depends-nya:
grep -n "vessel_bunker_management" vessel_chartering/__manifest__.py && echo "SALAH - dependency terbalik!" || echo "OK - arah dependency benar"
```

Cross-check §10.6, §10.7, dan §10.8 (bagian BOD/BOR) SAAT INI.

## Definition of Done
- [ ] §10.6 acceptance criteria terpenuhi (delivery event → draft BOD/BOR otomatis dengan ROB dari noon report terdekat)
- [ ] §10.7 acceptance criteria terpenuhi (settle → `bunker_adjustment` terisi benar nilai & tanda)
- [ ] `group_bunker_user` diverifikasi eksplisit tidak bisa approve BOD/BOR settlement
- [ ] Dikonfirmasi `vessel_chartering/__manifest__.py` TIDAK berubah/depend ke modul ini (arah dependency satu arah terjaga)
- [ ] Idempotent (termasuk override `write()` di `vessel.charter.contract` — pastikan tidak memecah reload demo data, ikuti pelajaran Sprint 11 `vessel_voyage_pnl`)
- [ ] Install bersih, tidak ada regresi Sprint 22-25
