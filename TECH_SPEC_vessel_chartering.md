# Dokumen Teknis — Modul `vessel_chartering`

**Proyek:** Odoo Shipping Vertical Solution — Layer 2 (Komersial)
**Target Platform:** Odoo 19.0 Enterprise
**Lisensi:** LGPL-3
**Penyusun:** Sunartha ERP Consulting
**Status Dokumen:** Draft v1.0 — untuk review sebelum development
**Tanggal:** Juli 2026

---

## 1. Latar Belakang & Tujuan

Perusahaan pelayaran Indonesia (tug & barge, mother vessel, LNG carrier, floating crane) menjalankan bisnis melalui kontrak charter. Odoo standar tidak memiliki konsep charter party, laytime, demurrage, maupun voyage-based revenue. Modul ini menjadi **entry point komersial** dari vertical solution, menjembatani kontrak charter ke `sale`/`purchase`/`account` standar Odoo.

### 1.1 Ruang Lingkup (Scope)

| In Scope | Out of Scope (modul lanjutan) |
|---|---|
| Charter Party management (Voyage Charter, Time Charter, COA) | Noon report / posisi kapal (`vessel_voyage_operations`) |
| **Charter-Out** (kapal milik disewakan → revenue) | Voyage P&L lengkap (`vessel_voyage_pnl`) |
| **Charter-In** (sewa kapal pihak ketiga → cost) | Bunker procurement workflow (`vessel_bunker_management`) |
| Freight per MT dengan laytime & demurrage/despatch calculator | Port disbursement account (PDA/FDA) |
| Hire statement untuk Time Charter (on-hire/off-hire) | CTMS LNG, billing floating crane per shift |
| Estimasi bunker berbasis kurs USD | |
| Integrasi Analytic Plans (per vessel + per voyage/contract) | |
| Invoicing otomatis ke `account.move` | |

### 1.2 Persona Pengguna

| Role | Kebutuhan Utama |
|---|---|
| **Chartering Manager** | Buat & negosiasi fixture, monitor kontrak aktif, approve laytime calculation |
| **Operations Staff** | Input SOF, NOR, aktual loading/discharge, hitung laytime |
| **Finance/Accounting** | Terima invoice draft otomatis, rekonsiliasi hire statement, kurs USD |
| **Direksi** | Dashboard: fixture pipeline, utilisasi armada, demurrage exposure |

---

## 2. Konsep Bisnis yang Dimodelkan

### 2.1 Tiga Tipe Kontrak

```
COA (Contract of Affreightment)
 └── 1..n Voyage Charter (shipment nomination per periode)

Voyage Charter  → revenue = freight rate (USD/MT) × cargo qty ± demurrage/despatch
Time Charter    → revenue = hire rate (USD/day) × durasi on-hire − off-hire deduction
```

### 2.2 Dua Arah Kontrak (direction)

| Direction | Perusahaan bertindak sebagai | Dokumen keuangan |
|---|---|---|
| `out` (Charter-Out) | **Owner/Disponent Owner** — menyewakan kapal | Customer Invoice (`account.move`, `out_invoice`) |
| `in` (Charter-In) | **Charterer** — menyewa kapal pihak ketiga | Vendor Bill (`account.move`, `in_invoice`) |

Satu model kontrak yang sama melayani dua arah — dibedakan field `direction`, partner (customer vs vendor), dan tipe jurnal. Ini mencegah duplikasi model dan memungkinkan skenario **relet** (charter-in lalu charter-out kapal yang sama) dengan dua kontrak yang saling terhubung.

### 2.3 Laytime & Demurrage (Voyage Charter — fokus tug & barge batubara)

Definisi yang dimodelkan:
- **Laytime allowed**: waktu yang diizinkan untuk loading + discharge (bisa reversible/non-reversible)
- **NOR (Notice of Readiness)**: waktu kapal siap; laytime mulai dihitung setelah NOR tendered + turn time
- **SOF (Statement of Facts)**: kronologi kejadian di pelabuhan — basis perhitungan laytime used
- **Demurrage**: laytime used > allowed → charterer bayar denda (USD/day, pro-rata)
- **Despatch**: laytime used < allowed → owner bayar insentif (biasanya 50% demurrage rate)
- **Interupsi laytime**: hujan (weather working days), shifting, breakdown alat — configurable apakah counting atau tidak per jenis interupsi

### 2.4 Multi-Currency

- Freight rate, hire rate, demurrage rate dalam **USD** (praktik pasar)
- Invoicing bisa USD atau IDR — konversi memakai `res.currency.rate` Odoo standar
- **Kurs acuan kontrak** (contract rate) opsional: beberapa charter party mengunci kurs (mis. kurs KMK/JISDOR tanggal B/L); field `exchange_rate_policy` menentukan pakai kurs sistem tanggal invoice atau kurs manual terkunci
- Estimasi bunker dalam voyage estimate memakai harga USD/MT × kurs berjalan → tampil dual currency

### 2.5 Analytic Plans (Odoo 19)

Dua analytic plan di-seed saat instalasi (idempotent — cek existing dulu):

| Plan | Kode | Isi |
|---|---|---|
| **Vessel** | `PLAN_VESSEL` | 1 analytic account per `fleet.vehicle` (is_vessel=True), auto-create saat kapal dibuat |
| **Voyage/Contract** | `PLAN_VOYAGE` | 1 analytic account per charter contract / per voyage, auto-create saat kontrak confirmed |

Semua `account.move.line` yang dihasilkan modul ini membawa **analytic_distribution** dengan dua dimensi sekaligus (fitur multi-plan Odoo 19: `{"vessel_aa_id": 100, "voyage_aa_id": 100}`). Modul lain (fuel_log, maintenance) akan menulis ke plan yang sama di fase berikutnya sehingga voyage P&L tinggal agregasi.

---

## 3. Desain Data Model

### 3.1 Diagram Relasi (ringkas)

```
vessel.charter.contract (jantung modul)
 ├── partner_id → res.partner (customer/vendor)
 ├── vessel_id → fleet.vehicle
 ├── tug_id → fleet.vehicle (opsional, pairing tug-barge)
 ├── coa_id → vessel.charter.contract (parent COA, self-reference)
 ├── relet_source_id → vessel.charter.contract (link charter-in ↔ out)
 ├── analytic_account_id → account.analytic.account (plan Voyage)
 ├── voyage_estimate_ids → vessel.voyage.estimate (1..n revisi)
 ├── laytime_ids → vessel.laytime.calculation (per port call)
 ├── hire_line_ids → vessel.hire.statement.line (Time Charter)
 ├── offhire_ids → vessel.offhire.event (Time Charter)
 └── invoice_ids → account.move

vessel.laytime.calculation
 ├── sof_line_ids → vessel.sof.line (kronologi)
 └── interruption_type_id → vessel.laytime.interruption.type (master)

Master data:
 vessel.cargo.type            (batubara, nikel, CPO, general cargo, LNG, ...)
 vessel.charter.terms         (template terms: FIOST, CQD, SHINC/SHEX, ...)
 vessel.laytime.interruption.type (hujan, shifting, breakdown, ... + flag counting)
 vessel.port                  (master pelabuhan — atau pakai res.partner kategori port; lihat §8 keputusan desain)
```

### 3.2 Model: `vessel.charter.contract`

`_name = 'vessel.charter.contract'`
`_inherit = ['mail.thread', 'mail.activity.mixin']`
`_order = 'date_start desc, id desc'`

#### Field Umum

| Field | Type | Keterangan |
|---|---|---|
| `name` | Char, readonly | Nomor kontrak via `ir.sequence` — format `CHO/2026/0001` (out) / `CHI/2026/0001` (in) |
| `contract_type` | Selection | `voyage` / `time` / `coa` |
| `direction` | Selection | `out` (revenue) / `in` (cost) |
| `partner_id` | Many2one `res.partner` | Charterer (out) atau Owner (in), required |
| `broker_id` | Many2one `res.partner` | Opsional; `brokerage_pct` Float |
| `vessel_id` | Many2one `fleet.vehicle` | Domain `[('is_vessel','=',True)]`; **tidak required untuk COA** (nominasi per shipment) |
| `tug_id` | Many2one `fleet.vehicle` | Pairing tug untuk barge; domain vessel_type = tug |
| `cargo_type_id` | Many2one `vessel.cargo.type` | |
| `cargo_qty` | Float | MT; `qty_tolerance_pct` Float (±%, MOLOO/MOLCO) |
| `date_start` / `date_end` | Date | Laycan (voyage) / periode charter (time/COA) |
| `currency_id` | Many2one `res.currency` | Default USD |
| `invoice_currency_id` | Many2one `res.currency` | Mata uang penerbitan invoice (USD/IDR) |
| `exchange_rate_policy` | Selection | `system` (kurs Odoo tanggal invoice) / `fixed` (kurs manual) |
| `fixed_exchange_rate` | Float, digits=(12,4) | Terisi jika policy `fixed` |
| `charter_terms_id` | Many2one `vessel.charter.terms` | Template terms |
| `analytic_account_id` | Many2one, readonly | Auto-create saat confirm, plan Voyage |
| `company_id`, `user_id` | | Standar |
| `state` | Selection | Lihat §4.1 |

#### Field Voyage Charter

| Field | Type | Keterangan |
|---|---|---|
| `freight_rate` | Monetary | USD per MT |
| `freight_basis` | Selection | `per_mt` / `lumpsum` |
| `lumpsum_amount` | Monetary | Jika basis lumpsum |
| `load_port_id` / `discharge_port_id` | Many2one | Multi-port via One2many `port_call_ids` jika >1; MVP: 1 load + 1 discharge |
| `laytime_allowed_load` / `laytime_allowed_discharge` | Float | Dalam **jam** (input bisa hari, disimpan jam) |
| `laytime_reversible` | Boolean | Reversible = gabung load+discharge |
| `turn_time_hours` | Float | Waktu tunggu setelah NOR sebelum laytime mulai |
| `demurrage_rate` | Monetary | USD/day |
| `despatch_rate` | Monetary | Default = 50% demurrage, editable |
| `bl_date` | Date | Tanggal Bill of Lading — acuan kurs jika policy fixed |
| `bl_qty` | Float | Qty aktual B/L → basis final freight |

#### Field Time Charter

| Field | Type | Keterangan |
|---|---|---|
| `hire_rate` | Monetary | USD/day |
| `hire_payment_term` | Selection | `15_days_advance` / `monthly_advance` / `monthly_arrears` |
| `delivery_date` / `redelivery_date` | Datetime | On-hire & off-hire aktual |
| `delivery_place` / `redelivery_place` | Char/M2o port | |
| `cve_rate` | Monetary | C/V/E (Communication, Victualling, Entertainment) USD/bulan, opsional |
| `total_offhire_hours` | Float, compute | Dari `offhire_ids` |

#### Field COA

| Field | Type | Keterangan |
|---|---|---|
| `total_qty_commitment` | Float | Total MT kontrak |
| `shipment_ids` | One2many `vessel.charter.contract` | Child voyage charter (nominasi), `coa_id` sebagai inverse |
| `qty_shipped` / `qty_remaining` | Float, compute | Agregasi dari child yang state ≥ completed |

#### Field Compute / Monitoring

| Field | Keterangan |
|---|---|
| `freight_amount_estimate` | rate × cargo_qty (atau lumpsum) |
| `freight_amount_final` | rate × bl_qty |
| `demurrage_amount_total` / `despatch_amount_total` | Agregasi dari `laytime_ids` yang approved |
| `invoiced_amount` / `residual_amount` | Dari `invoice_ids` |
| `estimate_count`, `laytime_count`, `invoice_count` | Untuk smart buttons |

#### Constraint

- `_check_dates`: date_end ≥ date_start
- `_check_vessel_overlap` (voyage & time, state confirmed+): warning (bukan blokir — kapal bisa punya kontrak berurutan dengan laycan beririsan; blokir hanya jika overlap penuh dengan kontrak `in_progress`)
- `_check_rates`: freight_rate/hire_rate > 0 saat confirm
- COA tidak boleh punya laytime/hire lines (hanya child yang punya)

### 3.3 Model: `vessel.voyage.estimate`

Pre-fixture estimate — alat bantu keputusan sebelum kontrak dikonfirmasi. Boleh multiple revisi per kontrak.

`_name = 'vessel.voyage.estimate'`

| Field | Type | Keterangan |
|---|---|---|
| `contract_id` | Many2one, required | |
| `name` | Char | Revisi: EST-001, EST-002 |
| `distance_nm` | Float | Jarak total NM |
| `speed_knots` | Float | Kecepatan rata-rata |
| `sea_days` | Float, compute | distance / (speed × 24), editable override |
| `port_days_load` / `port_days_discharge` | Float | |
| `total_voyage_days` | Float, compute | |
| **Bunker section** | | |
| `fo_consumption_sea` / `fo_consumption_port` | Float | MT/day |
| `do_consumption_sea` / `do_consumption_port` | Float | MT/day |
| `fo_price_usd` / `do_price_usd` | Float | USD/MT |
| `usd_rate` | Float, digits=(12,4) | **Kurs USD→IDR estimasi**, default dari `res.currency.rate` hari ini, editable |
| `bunker_cost_usd` | Monetary, compute | (cons × days × price) FO+DO |
| `bunker_cost_idr` | Monetary, compute | bunker_cost_usd × usd_rate |
| **Cost lain** | | |
| `port_cost_estimate` | Monetary | |
| `other_cost_estimate` | Monetary | Asuransi tambahan, agency, dll |
| `charter_in_cost` | Monetary | Jika relet: biaya sewa kapal |
| **Hasil** | | |
| `revenue_estimate` | Monetary, compute | Dari kontrak (freight × qty) |
| `voyage_result` | Monetary, compute | Revenue − total cost |
| `tce_per_day` | Monetary, compute | (Revenue − voyage cost) / total_voyage_days — Time Charter Equivalent |
| `state` | Selection | `draft` / `selected` (1 estimate terpilih sebagai baseline) |

### 3.4 Model: `vessel.laytime.calculation`

Satu record per port call (load / discharge). Jika `laytime_reversible`, sistem tetap membuat 2 record tapi perhitungan demurrage digabung di level kontrak.

`_name = 'vessel.laytime.calculation'`
`_inherit = ['mail.thread']`

| Field | Type | Keterangan |
|---|---|---|
| `contract_id` | Many2one, required | |
| `port_call_type` | Selection | `load` / `discharge` |
| `port_id` | Many2one | |
| `nor_tendered` | Datetime | |
| `nor_accepted` | Datetime | |
| `laytime_commenced` | Datetime, compute | nor_accepted + turn_time (editable override) |
| `laytime_completed` | Datetime | Selesai cargo ops |
| `laytime_allowed_hours` | Float | Default dari kontrak |
| `sof_line_ids` | One2many `vessel.sof.line` | |
| `laytime_used_hours` | Float, compute | Total durasi counting dari SOF lines |
| `balance_hours` | Float, compute | allowed − used (negatif = demurrage) |
| `time_on_demurrage_hours` | Float, compute | |
| `demurrage_amount` | Monetary, compute | (time_on_demurrage / 24) × demurrage_rate. **Once on demurrage, always on demurrage** — interupsi tidak menghentikan counting setelah masuk demurrage |
| `despatch_amount` | Monetary, compute | (balance positif / 24) × despatch_rate |
| `state` | Selection | `draft` → `submitted` → `approved` (Chartering Manager) → `invoiced` |
| `notes` | Html | |

**Aturan compute `laytime_used_hours`:**
1. Iterasi `sof_line_ids` terurut waktu
2. Line dengan `interruption_type_id.is_counting = False` dikecualikan dari counting **kecuali** posisi waktu sudah melewati titik on-demurrage (aturan "once on demurrage")
3. Terms SHINC/SHEX dari `charter_terms_id` menentukan apakah Minggu/libur dihitung (MVP: flag boolean `sundays_holidays_included`; kalender libur nasional via `resource.calendar` — fase 2)

### 3.5 Model: `vessel.sof.line`

| Field | Type | Keterangan |
|---|---|---|
| `laytime_id` | Many2one, required, ondelete=cascade | |
| `datetime_start` / `datetime_end` | Datetime | |
| `duration_hours` | Float, compute, store | |
| `activity` | Char | "Commenced loading", "Rain stop", ... |
| `interruption_type_id` | Many2one `vessel.laytime.interruption.type` | Kosong = normal counting |
| `is_counting` | Boolean, compute store | Dari interruption type; True jika kosong |
| `remarks` | Char | |

Constraint: `datetime_end > datetime_start`; tidak boleh overlap antar line dalam satu laytime (warning, bukan blokir — SOF nyata kadang paralel).

### 3.6 Model: `vessel.laytime.interruption.type` (master)

| Field | Type |
|---|---|
| `name` | Char — Hujan, Shifting, Equipment Breakdown (shore), Equipment Breakdown (vessel), Waiting Berth, Force Majeure |
| `is_counting` | Boolean — apakah waktu tetap dihitung sebagai laytime |
| `active` | Boolean |

Di-seed via data XML `noupdate="1"`.

### 3.7 Model: `vessel.hire.statement.line` (Time Charter)

Satu line per periode penagihan hire.

| Field | Type | Keterangan |
|---|---|---|
| `contract_id` | Many2one | |
| `period_start` / `period_end` | Date | |
| `days_in_period` | Float, compute | |
| `offhire_hours` | Float, compute | Dari `vessel.offhire.event` yang beririsan periode |
| `net_hire_days` | Float, compute | days − offhire/24 |
| `hire_amount` | Monetary, compute | net_hire_days × hire_rate |
| `cve_amount` | Monetary, compute | Pro-rata bulanan |
| `bunker_adjustment` | Monetary | Manual — BOD/BOR (bunker on delivery/redelivery) fase ini manual |
| `total_amount` | Monetary, compute | |
| `invoice_id` | Many2one `account.move` | |
| `state` | Selection | `draft` / `invoiced` / `paid` (related dari invoice) |

### 3.8 Model: `vessel.offhire.event`

| Field | Type |
|---|---|
| `contract_id` | Many2one |
| `datetime_start` / `datetime_end` | Datetime |
| `duration_hours` | Float, compute store |
| `reason` | Selection: `breakdown` / `drydock` / `crew` / `deficiency` / `other` |
| `description` | Char |
| `fuel_deduction` | Monetary — biaya bunker selama off-hire yang ditanggung owner |

### 3.9 Master lain

**`vessel.cargo.type`**: name, `is_dangerous` Boolean, `default_stowage_factor` Float, active.

**`vessel.charter.terms`**: name (mis. "FIOST 8,000/8,000 SHINC"), `loading_terms` Char, `sundays_holidays_included` Boolean, `laytime_reversible_default` Boolean, `notes` Html.

**Port**: **Keputusan desain — pakai `res.partner`** dengan `is_port` Boolean + `unlocode` Char (extend via modul ini), bukan model baru. Alasan: pelabuhan sering sekaligus jadi vendor (port charges), dan agen pelabuhan adalah partner. Menghindari duplikasi master. View port tersendiri difilter `is_port=True`.

### 3.10 Extend `fleet.vehicle`

| Field | Keterangan |
|---|---|
| `analytic_account_id` | Many2one, auto-create di plan Vessel saat is_vessel=True |
| `charter_contract_ids` | One2many |
| `active_charter_id` | Many2one, compute — kontrak in_progress saat ini |
| `charter_status` | Selection compute: `available` / `on_voyage_charter` / `on_time_charter` / `chartered_in` |
| `gt`, `dwt` | Float — jika belum ada dari modul lain (cek fleet_document_id dulu, hindari duplikat field) |

---

## 4. Workflow & Business Logic

### 4.1 State Machine `vessel.charter.contract`

```
draft → negotiation → confirmed → in_progress → completed → closed
                          ↓
                      cancelled
```

| Transisi | Tombol | Logic |
|---|---|---|
| draft → negotiation | "Kirim Penawaran" | Opsional, untuk pipeline tracking |
| → confirmed | "Konfirmasi Fixture" | Validasi: rate>0, vessel & partner terisi (kecuali COA), laycan valid. **Auto-create analytic account** (plan Voyage, nama = nomor kontrak). Cek overlap kontrak. Post message chatter |
| → in_progress | "Mulai Voyage" / "Delivery" (TC) | Voyage: manual atau otomatis saat NOR pertama diinput. TC: isi `delivery_date` |
| → completed | "Selesai" / "Redelivery" (TC) | Voyage: semua laytime approved & bl_qty terisi. TC: isi `redelivery_date` |
| → closed | "Tutup Kontrak" | Semua invoice posted & lunas (atau manual override oleh Manager dengan alasan) |
| → cancelled | "Batalkan" | Hanya dari draft/negotiation/confirmed; wajib isi alasan (wizard) |

### 4.2 Invoicing

**Voyage Charter (direction=out):**
1. **Freight invoice** — tombol "Buat Invoice Freight", tersedia setelah `bl_qty` terisi. Wizard preview: qty × rate, pilih kurs (policy), opsi prosentase (freight 95% on signing B/L + 5% balance — praktik umum; field `freight_split_pct`)
2. **Demurrage invoice / Despatch credit note** — dari laytime approved; despatch menghasilkan credit note atau invoice line negatif (konfigurasi `despatch_as_credit_note` Boolean di settings)

**Time Charter (out):** tombol "Generate Hire Statement" membuat `vessel.hire.statement.line` periode berikutnya sesuai `hire_payment_term`; tombol "Buat Invoice" per line.

**Direction=in:** alur sama tetapi menghasilkan **Vendor Bill draft** untuk dicocokkan dengan invoice owner (three-way-match manual).

**Semua invoice line membawa:**
- `analytic_distribution` = {vessel_plan_account: 100%, voyage_plan_account: 100%}
- Product: 3 product service di-seed — "Freight Revenue", "Demurrage", "Charter Hire" (income account dikonfigurasi per company; untuk direction=in dipakai juga dengan expense account)
- Currency sesuai `invoice_currency_id`; jika `fixed` policy dan invoice IDR: amount = USD × `fixed_exchange_rate`, kurs dicatat di narration

### 4.3 Cron Jobs

| Cron | Frekuensi | Fungsi |
|---|---|---|
| `_cron_laycan_alert` | Harian | Kontrak confirmed dengan laycan start H-7/H-3/H-0 tanpa NOR → activity ke Operations + email |
| `_cron_hire_due` | Harian | TC: hire statement line berikutnya jatuh tempo H-5 → activity ke Finance |
| `_cron_coa_progress` | Mingguan | COA dengan qty_remaining > 0 dan sisa periode < 60 hari → warning under-lifting ke Chartering Manager |
| `_cron_demurrage_exposure` | Harian | Laytime draft/submitted dengan balance negatif → update field exposure di dashboard |

### 4.4 Notifikasi

Email template: fixture confirmed (internal), laycan reminder, demurrage approved (ke partner, opsional), hire due. Mengikuti pola `mail.thread` + template XML seperti modul existing. WhatsApp **tidak** di scope modul ini (cukup email — audiens internal & B2B korporat).

---

## 5. Views & Menu

**Menu:** Fleet → **Chartering** *(sejajar Dokumen Legal, Fuel, dst)*

```
Chartering
├── Fixtures / Kontrak
│   ├── Semua Kontrak            (list, form, kanban by state, calendar by laycan)
│   ├── Charter Out              (filter direction=out)
│   ├── Charter In               (filter direction=in)
│   └── COA                      (filter contract_type=coa)
├── Operasional
│   ├── Laytime Calculations     (list, form)
│   └── Hire Statements          (list)
├── Laporan
│   ├── Fixture Pipeline         (kanban/graph by state & bulan laycan)
│   ├── Demurrage Exposure       (pivot: kontrak × status laytime)
│   └── Analisa Voyage Estimate  (list estimate vs actual — basic; lengkap di vessel_voyage_pnl)
└── Konfigurasi (Manager only)
    ├── Tipe Cargo
    ├── Charter Terms
    ├── Tipe Interupsi Laytime
    └── Pelabuhan
```

**Form kontrak** — notebook pages: Info Utama / Komersial (rate, laytime terms) / Estimate / Laytime (smart button + inline list) / Hire & Off-hire (invisible untuk voyage) / Invoicing / Dokumen (lampiran charter party PDF). Statusbar dengan tombol aksi. Smart buttons: Estimates, Laytime, Invoices, Analytic Entries.

**Form laytime** — header NOR/commenced/completed, SOF lines editable inline list dengan running total, panel ringkasan (allowed vs used vs balance, demurrage amount) selalu terlihat.

---

## 6. Security

| Group | Hak |
|---|---|
| `group_chartering_user` (Operations) | RWC kontrak & laytime (no unlink), tidak bisa approve laytime, tidak lihat COA nilai total |
| `group_chartering_manager` | Full + approve laytime + konfigurasi + cancel/close kontrak |
| Finance (`account.group_account_invoice`) | Read kontrak, RWC invoice dari wizard |

`ir.model.access.csv` — **selalu pakai prefix modul** pada xmlid group referensi (pelajaran audit sebelumnya). Record rules: user hanya lihat kontrak company-nya (multi-company ready, `company_id` required).

---

## 7. Integrasi Antar Modul

| Modul | Integrasi |
|---|---|
| `fleet_fuel_log` | `fleet.vehicle.trip` diberi field `charter_contract_id` (Many2one, lewat modul bridge opsional `vessel_chartering_fuel` ATAU langsung jika dependency diterima — lihat §8) sehingga fuel log per voyage ter-link ke kontrak & analytic |
| `fleet_document_id` | Validasi soft saat confirm fixture: warning jika kapal punya dokumen expired/segera expired (reuse status compute) |
| `vessel_crew_management` | Fase berikutnya: warning jika manning tidak lengkap saat mulai voyage |
| `account` | Invoice, analytic plans, multi-currency |
| `documents` (Enterprise, opsional) | Folder per kontrak untuk charter party & B/L — soft dependency, cek `ir.module.module` |

---

## 8. Keputusan Desain & Alternatif yang Ditolak

| Keputusan | Alternatif ditolak | Alasan |
|---|---|---|
| Satu model kontrak untuk out & in | Dua model terpisah | 80% field sama; direction field + view berbeda lebih maintainable; pola sama dengan account.move |
| Port = extend `res.partner` | Model `vessel.port` baru | Port ≈ vendor/agen; hindari master ganda |
| Laytime per port call, reversible dihitung di kontrak | Satu laytime gabungan | SOF secara fisik memang per pelabuhan; audit lebih jelas |
| Estimate model terpisah multi-revisi | Field estimate di kontrak | Negosiasi nyata perlu bandingkan skenario |
| Dependency ke `fleet_fuel_log`: **TIDAK** (pakai bridge module) | Direct depends | Jaga prinsip modul berdiri sendiri (README existing); klien kecil mungkin hanya butuh chartering |
| Demurrage: "once on demurrage always on demurrage" hardcoded | Configurable | Standar pasar hampir universal; simplifikasi MVP, jadikan flag di fase 2 jika ada klien butuh |
| Kurs fixed per kontrak opsional | Selalu kurs sistem | Praktik lokal Indonesia sering mengunci kurs di charter party |

---

## 9. Rencana Fase & Estimasi Kompleksitas

| Fase | Deliverable | Kompleksitas |
|---|---|---|
| **MVP (fase ini)** | Model lengkap §3, workflow §4.1, laytime calculator + SOF, freight & demurrage invoicing (out), hire statement dasar (out), charter-in vendor bill, analytic plans, menu & views, security, cron laycan | Tinggi — laytime compute adalah inti |
| Fase 2 | COA nominasi otomatis, kalender libur nasional untuk SHEX, despatch credit note config, multi-port rotation, laporan PDF laytime statement (format standar BIMCO) | Sedang |
| Fase 3 | Bunker adjustment BOD/BOR otomatis, integrasi vessel_voyage_operations (NOR dari noon report), relet linking otomatis | Sedang |

---

## 10. Kriteria Penerimaan (Acceptance Criteria) MVP

1. Install bersih di Odoo 19 Enterprise tanpa error (zero-install-error), tanpa konflik dengan 5 modul existing
2. Buat voyage charter out USD, konfirmasi → analytic account terbentuk di plan Voyage; vessel punya analytic di plan Vessel
3. Input SOF dengan interupsi hujan (non-counting) → laytime used terhitung benar termasuk aturan once-on-demurrage (disediakan 3 test case perhitungan manual sebagai pembanding)
4. Laytime approved dengan balance −36 jam, demurrage rate USD 10,000/day → demurrage invoice USD 15,000 terbentuk dengan analytic distribution 2 plan
5. Invoice IDR dengan policy fixed rate 16,250 → amount IDR benar, kurs tercatat
6. Time charter: hire statement 15 hari dengan off-hire 12 jam → net hire days = 14.5
7. Charter-in menghasilkan vendor bill draft dengan expense account & analytic yang benar
8. COA dengan 3 shipment child → qty_remaining terhitung benar
9. Semua unit test `TransactionCase` untuk compute laytime lulus
10. Tidak ada penggunaan `display_name` sebagai field custom, `fields.Datetime.from_string`, atau `@api.depends()` kosong (checklist audit Odoo 19)

---

## 11. Pertanyaan Terbuka (perlu keputusan sebelum coding)

1. **Pro-rata demurrage**: dihitung per jam (balance/24 × rate) atau per hari dibulatkan? Dokumen ini asumsi **pro-rata per jam** (praktik umum) — konfirmasi dengan klien pilot.
2. **PPN**: freight domestik kena PPN 1.1% (nilai lain) atau mengikuti konfigurasi tax standar? Asumsi: pakai `account.tax` standar yang dikonfigurasi konsultan finance — modul tidak hardcode tax.
3. Apakah butuh **approval matrix** untuk fixture di atas nilai tertentu (integrasi modul `approvals` Enterprise) di MVP, atau cukup role manager?
4. Hire statement TC: perlu format **BIMCO-style PDF** di MVP atau cukup invoice standar?
