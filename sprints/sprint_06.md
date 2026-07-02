# Sprint 6 — Invoicing Integration (Freight, Demurrage, Hire, Charter-In)

**Modul disentuh:** `vessel_chartering`
**Depends on:** Sprint 2 (kontrak), Sprint 4 (laytime/demurrage), Sprint 5 (hire statement)

## Konteks
Menghubungkan semua kontrak/laytime/hire statement ke `account.move` sungguhan (§4.2 tech spec). Ini titik temu dengan 2 dari 4 "Pertanyaan Terbuka" tech spec (§11) — **lihat catatan keputusan di bawah sebelum mulai**.

## Keputusan atas Pertanyaan Terbuka (§11 tech spec) — konfirmasi sebelum lanjut jika ada yang keberatan

1. **Pro-rata demurrage**: pakai asumsi dokumen — **per jam** (balance/24 × rate), sudah diimplementasi Sprint 4
2. **PPN**: modul **tidak hardcode tax** — pakai `account.tax` standar yang dikonfigurasi terpisah per company, product service cukup sediakan field tax default kosong/configurable
3. **Approval matrix**: **skip di MVP** — Odoo Community tidak punya module `approvals` (Enterprise-only), cukup role-based `group_chartering_manager` untuk approve laytime & confirm fixture
4. **Format PDF hire statement**: **skip BIMCO-style PDF di MVP** — pakai invoice/report standar Odoo dulu, BIMCO-format jadi kandidat Fase 2

## Tasks

1. Seed 3 `product.product` (type=service) via data XML: "Freight Revenue", "Demurrage", "Charter Hire" — income account per company dikonfigurasi via `product.category` standar (jangan hardcode account id)
2. Wizard `vessel.freight.invoice.wizard` — dipanggil dari tombol "Buat Invoice Freight" (muncul setelah `bl_qty` terisi), preview qty × rate, pilih kurs sesuai `exchange_rate_policy`, opsi `freight_split_pct` (freight 95% saat B/L + 5% balance — field baru di kontrak jika belum ada dari §3.2, tambahkan sekarang)
3. Method `_create_freight_invoice()` — generate `account.move` (`out_invoice` untuk direction=out, `in_invoice`/vendor bill untuk direction=in), currency sesuai `invoice_currency_id`, jika policy `fixed` hitung amount = USD × `fixed_exchange_rate` dan catat kurs di narration line
4. Method `_create_demurrage_invoice()` — dari laytime `approved`, generate invoice/credit note; despatch pakai `despatch_as_credit_note` (Boolean di `res.config.settings` — tambahkan setting baru) untuk pilih credit note vs invoice line negatif. Update `laytime.state` → `invoiced` setelah invoice dibuat
5. Tombol "Buat Invoice" per `vessel.hire.statement.line` — generate invoice sesuai direction, update `hire_statement_line.invoice_id` & `state`
6. **Semua invoice line yang dihasilkan wajib bawa `analytic_distribution` 2 dimensi** — `{vessel_analytic_account_id: 100, voyage_analytic_account_id: 100}` (format Odoo 19 multi-plan, lihat §2.5)
7. Update `invoiced_amount`/`residual_amount` di kontrak (§3.2, sebelumnya return 0 dari Sprint 2) — compute nyata dari `invoice_ids` + `payment_state`
8. Charter-in (`direction='in'`): pastikan semua alur di atas menghasilkan Vendor Bill draft (bukan auto-post) untuk dicocokkan manual oleh Finance (three-way-match manual sesuai §4.2)
9. Views: tab "Invoicing" di form kontrak — list invoice terkait + tombol aksi generate, smart button "Invoices" dengan count asli

## Verifikasi

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  -u vessel_chartering 2>&1 | grep -E "ERROR|CRITICAL"
```

Test manual/unit (`TransactionCase`) mereplikasi acceptance criteria:
1. §10.4: Laytime approved balance −36 jam, demurrage rate USD 10,000/day → demurrage invoice USD 15,000 terbentuk dengan `analytic_distribution` 2 plan
2. §10.5: Invoice IDR dengan policy fixed rate 16.250 → amount IDR benar, kurs tercatat di narration
3. §10.7: Charter-in menghasilkan vendor bill draft dengan expense account & analytic benar

## Definition of Done
- [ ] Freight invoice, demurrage invoice/despatch credit note, hire statement invoice semua bisa digenerate dari UI tanpa error
- [ ] Semua invoice line punya analytic_distribution 2 dimensi yang benar
- [ ] Fixed exchange rate policy menghasilkan angka IDR yang benar + kurs tercatat
- [ ] Charter-in menghasilkan vendor bill (in_invoice), bukan customer invoice
- [ ] `invoiced_amount`/`residual_amount` di kontrak ter-update otomatis setelah invoice dibuat
