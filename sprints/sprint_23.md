# Sprint 23 — vessel_bunker_management: Procurement (Inquiry, Quote, PO Integration)

**Modul disentuh:** `vessel_bunker_management`
**Depends on:** Sprint 22 (foundation, master data)

## Konteks
Alur procurement (§4.1): inquiry → quote comparison → nominasi → PO otomatis. Ikuti saran §12.2 poin 3-4: compute dulu (`total_estimated_usd`, `price_vs_market_pct`) sebelum tombol nominasi/PO generation.

## Tasks

1. Model `vessel.bunker.inquiry` (§3.2) — `name` (ir.sequence `BINQ/2026/%05d`), `vessel_id`, `voyage_id` (opsional), `port_id`, `date_needed`, `requested_qty_fo`/`requested_qty_do`, `quote_ids`, `selected_quote_id`, `purchase_order_id` (readonly), `delivery_ids` (placeholder kosong, diisi Sprint 24), `state` (draft/inquiry_sent/quotes_received/nominated/delivered/cancelled), `analytic_account_id` (compute: `voyage_id.analytic_account_id` kalau ada, else `vessel_id.analytic_account_id` — **cek dulu field vessel_id.analytic_account_id benar ada dari `vessel_chartering`**, jangan asumsi nama)
2. Model `vessel.bunker.quote` (§3.3) — `inquiry_id`, `supplier_id`, `price_fo_usd_mt`/`price_do_usd_mt`, `barging_fee_usd`, `validity_date`, `total_estimated_usd` (compute store: `(price × requested_qty) + barging_fee` dari inquiry), `price_vs_market_pct` (compute: bandingkan `vessel.bunker.price.reference` tanggal terdekat SEBELUM `validity_date`, per `fuel_type` — kalau requested_qty_fo dan requested_qty_do dua-duanya ada, hitung weighted atau pisah per fuel type, tentukan pendekatan paling sederhana yang masih benar), `notes`
3. **Test compute dulu** sebelum lanjut ke action (§12.2 poin 3): unit test `total_estimated_usd` dengan angka konkret, unit test `price_vs_market_pct` dengan referensi harga dummy dari Sprint 22 (harga quote jauh di atas referensi → persentase signifikan, sesuai §10.9 acceptance criteria)
4. Constraint: minimal 1 `quote_ids` sebelum transisi ke `quotes_received`; `selected_quote_id` harus salah satu dari `quote_ids` milik inquiry yang sama (`@api.constrains`)
5. Tombol **"Kirim Inquiry"** (draft→inquiry_sent) — kirim email ke `partner_id` tiap quote (mail template, siapkan template-nya walau quote belum ada — kalau `quote_ids` kosong saat draft, technically belum bisa "kirim ke" siapa-siapa; cek ulang: mungkin transisi ini sebenarnya cuma menandai "inquiry resmi dikirim ke pasar", supplier lalu balas via quote yang diinput staff — desain ulang kalau perlu, dokumentasikan asumsi)
6. Transisi otomatis quotes_received (saat quote pertama diinput — via `@api.onchange`/compute atau override `create` pada `vessel.bunker.quote` yang cek state parent)
7. Tombol **"Nominasi Supplier"** (`action_nominate`, quotes_received→nominated) — wajib `selected_quote_id` terisi; **auto-create `purchase.order`** dengan line FO + DO (kalau qty>0) + barging fee sebagai line terpisah, `partner_id` dari `selected_quote_id.supplier_id`, analytic distribution ke `analytic_account_id`. **Test dengan TransactionCase bahwa PO line & analytic distribution benar** sebelum lanjut (§12.2 poin 4, jangan skip)
8. Tombol **"Batalkan"** (`action_cancel`) — wajib alasan (wizard simple atau field `cancel_reason` + context), hanya dari draft/inquiry_sent/quotes_received
9. Security access untuk `vessel.bunker.inquiry` & `vessel.bunker.quote`
10. Views: form inquiry (notebook Info Utama/Quote Comparison dengan highlight harga terendah + `price_vs_market_pct`), list, kanban by state; form quote inline di notebook. Smart button placeholder untuk Deliveries (invisible dulu, diisi Sprint 24)
11. Dummy data: 1 inquiry dengan 3 quote supplier berbeda (harga bervariasi, salah satu jauh di atas referensi harga Sprint 22 untuk demo `price_vs_market_pct` signifikan), nominasi salah satu → PO ter-generate — replikasi §10.2 & §10.9 acceptance criteria

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_bunker_management 2>&1 | grep -E "ERROR|CRITICAL"

MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags vessel_bunker_management -u vessel_bunker_management 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

Cross-check §10.2 dan §10.9 acceptance criteria SAAT INI.

## Definition of Done
- [ ] §10.2 acceptance criteria terpenuhi (3 quote → nominasi → PO ter-generate dengan line & harga sesuai quote terpilih)
- [ ] §10.9 acceptance criteria terpenuhi (`price_vs_market_pct` signifikan untuk quote jauh di atas referensi)
- [ ] Unit test PO line & analytic distribution lulus
- [ ] Idempotent, install bersih
- [ ] Pre-flight lengkap (termasuk mail.thread/mail.activity.mixin check kalau ada message_post/activity_schedule di sprint ini)
