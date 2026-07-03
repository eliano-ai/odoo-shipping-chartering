# Dokumen Teknis — Modul `vessel_bunker_management`

**Proyek:** Odoo Shipping Vertical Solution — Layer 3 (Finansial)
**Target Platform:** Odoo 19.0 Enterprise
**Lisensi:** LGPL-3
**Penyusun:** Sunartha ERP Consulting
**Status Dokumen:** Draft v1.0 — untuk review sebelum development
**Tanggal:** Juli 2026
**Urutan roadmap:** #4 (setelah `vessel_chartering`, `vessel_voyage_operations`, `vessel_voyage_pnl`)

---

## 1. Latar Belakang & Tujuan

Bunker adalah **40–60% biaya voyage** — komponen biaya terbesar sekaligus **celah fraud terbesar** di industri pelayaran (kuantitas BDN vs aktual yang diterima, kualitas off-spec, ROB yang "menghilang" tanpa penjelasan). `fleet_fuel_log` (Layer 1) sudah punya deteksi anomali konsumsi berbasis rata-rata historis, tapi belum bisa menyilangkan data **pembelian** (BDN), **posisi kapal** (noon report ROB), dan **konsumsi** (fuel log) dalam satu alur rekonsiliasi.

Modul ini menutup tiga celah sekaligus:
1. **Sisi pengadaan** — workflow procurement terstruktur (inquiry → quote → nominasi → delivery) menggantikan proses informal yang rawan mark-up harga/kick-back
2. **Sisi kuantitas** — independent survey vs BDN, dengan dispute tracking eksplisit
3. **Sisi rekonsiliasi** — ROB noon report vs perhitungan (previous ROB + supply − consumption), memperkuat anomaly detection `fleet_fuel_log` dengan sumber silang yang independen

Modul ini juga **menyelesaikan item MVP yang sengaja dibiarkan manual** di `vessel_chartering`: field `bunker_adjustment` di `vessel.hire.statement.line` (BOD/BOR — bunker on delivery/redelivery untuk Time Charter).

### 1.1 Ruang Lingkup (Scope)

| In Scope | Out of Scope (modul lain) |
|---|---|
| Bunker procurement workflow: inquiry → quote comparison → nomination → PO | Konsumsi harian bunker itu sendiri (`fleet_fuel_log`, sudah ada — modul ini konsumen datanya) |
| BDN (Bunker Delivery Note) — qty, density, temperature, sulfur content, scan | Freight/hire/laytime (`vessel_chartering`) — modul ini hanya menulis balik ke `bunker_adjustment` |
| Independent surveyor report vs BDN — dispute tracking | Noon report itu sendiri (`vessel_voyage_operations`, sudah ada — modul ini konsumen ROB-nya) |
| ROB reconciliation (noon report vs supply vs consumption) | CII/MARPOL resmi (§7.2 brainstorm, fase lanjutan terpisah) |
| Bunker price reference tracking (MOPS/Platts manual) vs harga beli aktual | Bunker hedging finansial (kontrak derivatif) — hanya price tracking referensi, bukan instrumen keuangan |
| BOD/BOR settlement otomatis ke hire statement (Time Charter) | Perhitungan hire statement itu sendiri (`vessel_chartering`) — modul ini hanya mengisi 1 field-nya |
| Integrasi `purchase` (PO), `stock` (penerimaan ke lokasi kapal) | Payroll/crew, HSE, dry docking — tidak relevan modul ini |

### 1.2 Persona Pengguna

| Role | Kebutuhan Utama |
|---|---|
| **Bunker/Procurement Staff (darat)** | Buat inquiry, bandingkan quote, nominasi supplier, input BDN saat delivery |
| **Nakhoda (Master)** — portal user | Konfirmasi qty diterima di kapal, upload BDN scan (peran terbatas — lihat §6) |
| **Independent Surveyor** (eksternal, bisa vendor portal atau input oleh staff) | Input hasil survey qty vs BDN |
| **Operations Staff** | Review ROB reconciliation, tindak lanjut anomali/dispute |
| **Finance/Accounting** | Terima vendor bill dari PO bunker, review variance harga vs market, settlement BOD/BOR ke hire statement |
| **Chartering Manager** | Approve BOD/BOR settlement sebelum masuk hire statement final |

---

## 2. Konsep Bisnis yang Dimodelkan

### 2.1 Alur Procurement

```
Inquiry (ke N supplier) → Quote per supplier (USD/MT + barging fee) → Bandingkan
   → Nominasi 1 supplier → Purchase Order (`purchase.order`)
   → Delivery fisik → BDN dicatat → Independent Survey (opsional/sesuai kebijakan)
   → Penerimaan stok (`stock.picking`) ke lokasi kapal → Vendor Bill
```

Satu inquiry bisa untuk kebutuhan satu voyage tertentu (link opsional ke `vessel.voyage`) atau kebutuhan umum kapal (tanpa voyage, misal isi ulang rutin time charter).

### 2.2 BDN (Bunker Delivery Note)

Dokumen resmi dari supplier/barging saat serah terima bunker di kapal — kuantitas (MT), density, temperature, sulfur content (relevan untuk kepatuhan MARPOL sulphur cap). Ini adalah **klaim supplier**, bukan kuantitas terverifikasi — karenanya perlu independent survey sebagai pembanding independen.

### 2.3 Independent Survey & Dispute

Surveyor independen (pihak ketiga, bukan supplier maupun kapal) mengukur ulang qty saat/setelah delivery. Selisih BDN vs survey di luar toleransi (default **0.5%**, configurable) → otomatis flag sebagai **dispute** yang perlu ditindaklanjuti (klaim ke supplier, kompensasi, atau penerimaan dengan catatan).

### 2.4 ROB Reconciliation — Inti Anti-Fraud Modul Ini

```
Expected ROB (di titik waktu T2)
  = ROB noon report sebelumnya (T1)
  + Total supply (BDN) antara T1-T2
  − Total consumption (fleet_fuel_log) antara T1-T2

Variance = ROB aktual (noon report T2) − Expected ROB
```

Variance signifikan (di luar threshold %, configurable per jenis bahan bakar) menandakan salah satu dari: BDN qty tidak sesuai aktual, konsumsi tidak tercatat lengkap di fuel log, atau **kebocoran/pencurian**. Modul ini tidak "menuduh" — hanya memunculkan variance sebagai sinyal investigasi ke Operations, konsisten dengan filosofi anomaly detection `fleet_fuel_log` yang sudah ada (bandingkan §2 `fleet_fuel_log` di FLEET_MODULES_OVERVIEW).

### 2.5 Price Reference & Analisa Harga

Harga referensi pasar (MOPS/Platts) diinput manual secara berkala (fase awal — API feed otomatis adalah opsi integrasi eksternal, §7.4 brainstorm, di luar MVP). Setiap quote/PO dibandingkan terhadap referensi tanggal terdekat → deteksi harga beli yang mencurigakan jauh di atas pasar (indikasi mark-up/kick-back).

### 2.6 BOD/BOR — Bunker on Delivery/Redelivery (Time Charter)

Saat kapal **delivery** ke charterer (awal time charter) dan **redelivery** (akhir), ROB bunker di kapal pada titik tersebut punya nilai finansial yang harus disettle antara owner dan charterer sesuai charter party (biasanya: charterer bayar owner untuk ROB saat delivery, owner bayar charterer untuk ROB saat redelivery, dengan harga yang disepakati — harga beli terakhir atau harga pasar tanggal tsb, tergantung klausul). Modul ini menghitung otomatis dan **mengisi kembali** field `bunker_adjustment` di `vessel.hire.statement.line` (`vessel_chartering`) yang di MVP-nya sengaja dibiarkan manual.

---

## 3. Desain Data Model

### 3.1 Diagram Relasi (ringkas)

```
vessel.bunker.inquiry (jantung procurement)
 ├── vessel_id → fleet.vehicle
 ├── voyage_id → vessel.voyage (opsional, vessel_voyage_operations)
 ├── port_id → res.partner (is_port=True, dari vessel_chartering)
 ├── quote_ids → vessel.bunker.quote (1..n, per supplier)
 ├── selected_quote_id → vessel.bunker.quote
 ├── purchase_order_id → purchase.order
 └── delivery_ids → vessel.bunker.delivery (1..n, biasanya 1)

vessel.bunker.delivery (BDN)
 ├── inquiry_id → vessel.bunker.inquiry
 ├── vessel_id, port_id
 ├── survey_id → vessel.bunker.survey (0..1)
 ├── stock_picking_id → stock.picking
 └── account_move_id → account.move (vendor bill, via PO)

vessel.bunker.survey
 └── delivery_id → vessel.bunker.delivery

vessel.bunker.rob.reconciliation
 ├── voyage_id → vessel.voyage
 ├── noon_report_start_id / noon_report_end_id → vessel.noon.report
 └── delivery_ids (compute, delivery dalam rentang)

vessel.bunker.bod.bor
 └── contract_id → vessel.charter.contract (contract_type=time)
     └── tulis balik ke hire_statement_line_id.bunker_adjustment

Master data (baru):
 vessel.bunker.price.reference   (tanggal, index name, fuel type, harga USD/MT)

Reuse master existing:
 fleet.fuel.type (dari fleet_fuel_log) — TIDAK duplikasi master fuel type
 res.partner (is_port dari vessel_chartering; supplier bunker = partner biasa)
```

### 3.2 Model: `vessel.bunker.inquiry`

`_name = 'vessel.bunker.inquiry'`
`_inherit = ['mail.thread', 'mail.activity.mixin']`
`_order = 'date_needed desc, id desc'`

| Field | Type | Keterangan |
|---|---|---|
| `name` | Char, readonly | Nomor via `ir.sequence` — format `BINQ/2026/0001` |
| `vessel_id` | Many2one `fleet.vehicle`, required | |
| `voyage_id` | Many2one `vessel.voyage` | Opsional — jika bunker untuk kebutuhan voyage spesifik |
| `port_id` | Many2one `res.partner` (`is_port=True`) | Lokasi delivery |
| `date_needed` | Date, required | Tanggal dibutuhkan |
| `requested_qty_fo` / `requested_qty_do` | Float | MT |
| `quote_ids` | One2many `vessel.bunker.quote` | |
| `selected_quote_id` | Many2one `vessel.bunker.quote` | Diisi saat nominasi |
| `purchase_order_id` | Many2one `purchase.order`, readonly | Auto-create saat nominasi |
| `delivery_ids` | One2many `vessel.bunker.delivery` | |
| `state` | Selection | `draft` / `inquiry_sent` / `quotes_received` / `nominated` / `delivered` / `cancelled` |
| `analytic_account_id` | Many2one, compute | Dari `voyage_id.analytic_account_id` jika ada, else dari `vessel_id.analytic_account_id` (plan Vessel saja) |

#### Constraint
- Minimal 1 `quote_ids` sebelum bisa transisi ke `quotes_received`
- `selected_quote_id` harus salah satu dari `quote_ids` milik inquiry yang sama

### 3.3 Model: `vessel.bunker.quote`

`_name = 'vessel.bunker.quote'`

| Field | Type | Keterangan |
|---|---|---|
| `inquiry_id` | Many2one, required, ondelete=cascade | |
| `supplier_id` | Many2one `res.partner`, required | |
| `price_fo_usd_mt` / `price_do_usd_mt` | Float | |
| `barging_fee_usd` | Float | Biaya tongkang/pengantaran, jika ada |
| `validity_date` | Date | Quote berlaku sampai kapan |
| `total_estimated_usd` | Monetary, compute | `(price × requested_qty) + barging_fee` dari inquiry terkait |
| `price_vs_market_pct` | Float, compute | Bandingkan terhadap `vessel.bunker.price.reference` tanggal terdekat sebelum `validity_date` |
| `notes` | Char | |

### 3.4 Model: `vessel.bunker.delivery` (BDN)

`_name = 'vessel.bunker.delivery'`
`_inherit = ['mail.thread']`
`_order = 'delivery_datetime desc'`

| Field | Type | Keterangan |
|---|---|---|
| `inquiry_id` | Many2one `vessel.bunker.inquiry`, required | |
| `vessel_id` | Many2one, related, store | |
| `port_id` | Many2one, related, store | |
| `bdn_number` | Char, required | Nomor BDN dari supplier |
| `bdn_date` | Date | |
| `delivery_datetime` | Datetime, required | Waktu aktual serah terima |
| `fuel_type_id` | Many2one `fleet.fuel.type` (reuse dari `fleet_fuel_log`) | |
| `qty_bdn_mt` | Float, required | Klaim kuantitas dari BDN |
| `density` | Float | kg/m³ pada 15°C |
| `temperature_c` | Float | |
| `sulfur_content_pct` | Float | Kepatuhan MARPOL sulphur cap |
| `attachment_ids` | Many2many `ir.attachment` | Scan BDN |
| `survey_id` | Many2one `vessel.bunker.survey` | 0..1, opsional sesuai kebijakan klien |
| `qty_confirmed_mt` | Float, compute | `survey_id.survey_qty_mt` jika ada survey, else `qty_bdn_mt` — qty yang dipakai untuk stok & rekonsiliasi |
| `stock_picking_id` | Many2one `stock.picking`, readonly | Auto-create saat state `confirmed` |
| `account_move_id` | Many2one `account.move`, related dari `inquiry_id.purchase_order_id` | Vendor bill, read-only reference |
| `state` | Selection | `draft` / `delivered` / `surveyed` / `disputed` / `confirmed` |

#### Constraint
- `qty_bdn_mt > 0`
- Tidak bisa `confirmed` jika `state='disputed'` dan dispute belum `resolved` (lihat §3.5)

### 3.5 Model: `vessel.bunker.survey`

`_name = 'vessel.bunker.survey'`

| Field | Type | Keterangan |
|---|---|---|
| `delivery_id` | Many2one, required | |
| `surveyor_id` | Many2one `res.partner`, required | Perusahaan surveyor independen |
| `survey_date` | Date | |
| `survey_qty_mt` | Float, required | |
| `survey_density` | Float | |
| `variance_qty_mt` | Float, compute, store | `survey_qty_mt − delivery_id.qty_bdn_mt` |
| `variance_pct` | Float, compute, store | |
| `tolerance_pct` | Float | Default dari `res.config.settings` (default 0.5%), editable per survey |
| `is_dispute` | Boolean, compute, store | `True` jika `abs(variance_pct) > tolerance_pct` |
| `dispute_state` | Selection | `open` / `resolved` — hanya relevan jika `is_dispute=True` |
| `resolution_notes` | Html | Wajib diisi sebelum `dispute_state='resolved'` |
| `attachment_ids` | Many2many `ir.attachment` | Laporan survey |

### 3.6 Model: `vessel.bunker.rob.reconciliation`

Satu record per pasangan noon report berurutan (atau per rentang custom yang dipilih Operations) — merekonsiliasi ROB.

`_name = 'vessel.bunker.rob.reconciliation'`
`_inherit = ['mail.thread']`

| Field | Type | Keterangan |
|---|---|---|
| `voyage_id` | Many2one `vessel.voyage`, required | |
| `noon_report_start_id` / `noon_report_end_id` | Many2one `vessel.noon.report` (approved) | Titik T1 dan T2 |
| `fuel_type` | Selection | `fo` / `do` (lube oil opsional fase 2) |
| `previous_rob` | Float, related | Dari `noon_report_start_id.rob_fo` atau `rob_do` |
| `actual_rob` | Float, related | Dari `noon_report_end_id.rob_fo` atau `rob_do` |
| `total_supply` | Float, compute | Sum `qty_confirmed_mt` dari `vessel.bunker.delivery` berdasar fuel_type, dalam rentang waktu T1-T2 |
| `total_consumption` | Float, compute | Sum dari `fleet.fuel.log` (jika terinstall) berdasar `fuel_type` & `fleet_trip_id`/analytic voyage, dalam rentang T1-T2 |
| `expected_rob` | Float, compute | `previous_rob + total_supply − total_consumption` |
| `variance` | Float, compute, store | `actual_rob − expected_rob` |
| `variance_pct` | Float, compute, store | Relatif terhadap `expected_rob` |
| `threshold_pct` | Float | Default dari `res.config.settings`, editable |
| `is_anomaly` | Boolean, compute, store | `abs(variance_pct) > threshold_pct` |
| `state` | Selection | `draft` / `reviewed` / `flagged` (flagged = anomaly dikonfirmasi butuh investigasi lanjut, bukan sekadar data noise) |
| `review_notes` | Html | |

Constraint: `noon_report_end_id.report_datetime > noon_report_start_id.report_datetime`, keduanya milik `voyage_id` yang sama.

### 3.7 Model: `vessel.bunker.bod.bor`

`_name = 'vessel.bunker.bod.bor'`

| Field | Type | Keterangan |
|---|---|---|
| `contract_id` | Many2one `vessel.charter.contract`, required, domain `contract_type='time'` | |
| `event_type` | Selection | `delivery` / `redelivery` |
| `event_date` | Date, related dari `contract_id.delivery_date`/`redelivery_date` | |
| `rob_fo` / `rob_do` | Float | Diambil dari noon report terdekat dengan `event_date`, editable override manual |
| `price_source` | Selection | `last_purchase` (harga BDN terakhir sebelum event) / `market_reference` (dari `vessel.bunker.price.reference`) / `manual` |
| `price_fo_usd_mt` / `price_do_usd_mt` | Float | Terisi sesuai `price_source`, editable |
| `settlement_amount` | Monetary, compute | `(rob_fo × price_fo) + (rob_do × price_do)` |
| `settlement_direction` | Selection, compute | `delivery` → charterer bayar owner (amount positif ke `bunker_adjustment`); `redelivery` → owner bayar charterer (amount negatif) |
| `hire_statement_line_id` | Many2one `vessel.hire.statement.line` | Target penulisan `bunker_adjustment` |
| `state` | Selection | `draft` / `confirmed` / `settled` |

Tombol **"Settle ke Hire Statement"** — hanya aktif saat `state='confirmed'`, menulis `settlement_amount` (dengan tanda sesuai `settlement_direction`) ke `hire_statement_line_id.bunker_adjustment`, set `state='settled'`.

### 3.8 Master: `vessel.bunker.price.reference`

| Field | Type | Keterangan |
|---|---|---|
| `date` | Date, required | |
| `index_name` | Selection | `mops` / `platts` / `other` |
| `fuel_type_id` | Many2one `fleet.fuel.type` | Reuse master existing |
| `price_usd_mt` | Float | Input manual |
| `region` | Char | Opsional, harga bisa beda per region (Singapore, Jakarta, dll) |

### 3.9 Extend model existing

**`fleet.vehicle`**:
| Field | Keterangan |
|---|---|
| `bunker_inquiry_ids` | One2many `vessel.bunker.inquiry` |
| `rob_reconciliation_ids` | One2many `vessel.bunker.rob.reconciliation`, melalui `voyage_ids` |

**`vessel.voyage`** (dari `vessel_voyage_operations`):
| Field | Keterangan |
|---|---|
| `bunker_delivery_ids` | One2many `vessel.bunker.delivery`, melalui `inquiry_id.voyage_id` |
| `rob_reconciliation_ids` | One2many `vessel.bunker.rob.reconciliation` |
| `rob_anomaly_count` | Integer, compute — smart button, hitung `is_anomaly=True` |

**`vessel.charter.contract`** (dari `vessel_chartering`):
| Field | Keterangan |
|---|---|
| `bod_bor_ids` | One2many `vessel.bunker.bod.bor` — hanya relevan `contract_type='time'` |

**`vessel.hire.statement.line`** (dari `vessel_chartering`):
| Field | Keterangan |
|---|---|
| `bod_bor_id` | Many2one `vessel.bunker.bod.bor`, compute — referensi sumber jika `bunker_adjustment` diisi otomatis (bukan manual) |

---

## 4. Workflow & Business Logic

### 4.1 Procurement Flow

| Transisi | Tombol | Logic |
|---|---|---|
| draft → inquiry_sent | "Kirim Inquiry" | Kirim email ke `partner_id` tiap quote yang ditambahkan (mail template) |
| → quotes_received | Otomatis saat quote pertama diinput/manual | |
| → nominated | "Nominasi Supplier" | Wajib pilih `selected_quote_id`; **auto-create `purchase.order`** dengan line sesuai quote (FO + DO + barging fee sebagai line terpisah), analytic distribution ke `analytic_account_id` |
| → delivered | Otomatis saat `delivery_ids` pertama `state='confirmed'` | |
| → cancelled | "Batalkan" | Wajib alasan; hanya dari draft/inquiry_sent/quotes_received |

### 4.2 BDN & Survey Flow

`draft` (Bunker Staff input BDN) → `delivered` → (opsional) survey diinput → jika `survey_id.is_dispute=True`, state otomatis pindah ke `disputed` (tidak bisa lanjut ke `confirmed` sampai `dispute_state='resolved'`) → `surveyed` (jika survey ada & tidak dispute, atau dispute sudah resolved) → **"Konfirmasi Penerimaan"** → `confirmed`: auto-create `stock.picking` (qty = `qty_confirmed_mt`) ke lokasi stok kapal (asumsi lokasi stok per kapal sudah ada dari `fleet_model_sparepart`/`fleet_fuel_log` — cek existing, jangan duplikasi).

### 4.3 ROB Reconciliation — Generation

Bisa dibuat manual oleh Operations (pilih 2 noon report berurutan) atau **otomatis via cron** (`_cron_generate_rob_reconciliation`) yang membuat record untuk setiap pasangan noon report approved berurutan pada voyage `sailing`/`at_port` yang belum punya reconciliation. Saat `is_anomaly=True`, kirim activity ke Operations — ini **melengkapi** (bukan menggantikan) anomaly detection consumption-based yang sudah ada di `fleet_fuel_log`.

### 4.4 BOD/BOR Settlement

Saat kontrak time charter transisi `delivery_date`/`redelivery_date` terisi (event di `vessel_chartering`), sistem (via method dipanggil dari extend `vessel.charter.contract`, bukan langsung dependency terbalik — lihat §8) memicu pembuatan `vessel.bunker.bod.bor` draft dengan `event_type` sesuai. Bunker Staff/Finance melengkapi `price_source`, konfirmasi, lalu tombol "Settle ke Hire Statement".

### 4.5 Cron Jobs

| Cron | Frekuensi | Fungsi |
|---|---|---|
| `_cron_quote_validity_reminder` | Harian | Quote `validity_date` H-1 tanpa nominasi → activity ke Bunker Staff |
| `_cron_generate_rob_reconciliation` | Harian | Auto-generate reconciliation untuk pasangan noon report baru (§4.3) |
| `_cron_rob_anomaly_alert` | Harian | Reconciliation `is_anomaly=True` state masih `draft` > 2 hari → escalate activity ke Fleet Manager |
| `_cron_dispute_followup` | Mingguan | Survey `dispute_state='open'` > 7 hari → reminder ke Bunker Manager |

### 4.6 Notifikasi

Email/activity: inquiry terkirim ke supplier, quote validity reminder, dispute terbuka (ke Bunker Manager & Finance), ROB anomaly terdeteksi (ke Fleet Manager), BOD/BOR siap settle (ke Chartering Manager untuk approve sebelum masuk hire statement final).

---

## 5. Views & Menu

**Menu:** Fleet → **Bunker Management**

```
Bunker Management
├── Procurement
│   ├── Bunker Inquiry           (list, form, kanban by state)
│   └── Perbandingan Quote       (list grouped by inquiry)
├── Delivery & Survey
│   ├── BDN / Delivery           (list, form)
│   ├── Independent Survey       (list, form)
│   └── Dispute Terbuka          (filter is_dispute=True, dispute_state=open)
├── Rekonsiliasi
│   ├── ROB Reconciliation       (list, form; filter anomali)
│   └── Anomaly Alert            (filter is_anomaly=True)
├── Time Charter
│   └── BOD/BOR Settlement       (list, form)
├── Laporan
│   ├── Price Analysis           (pivot/graph: quote/PO vs price reference)
│   └── Dispute & Variance Summary (pivot per supplier/surveyor)
└── Konfigurasi (Manager only)
    ├── Price Reference (MOPS/Platts)
    └── Setting Tolerance & Threshold
```

**Form Inquiry** — notebook: Info Utama / Quote Comparison (list inline dengan highlight harga terendah & `price_vs_market_pct`) / Delivery / Dokumen. Smart buttons: Quotes, PO, Deliveries.

**Form ROB Reconciliation** — panel ringkas selalu terlihat: previous ROB → supply → consumption → expected vs actual, dengan indikator warna (hijau/kuning/merah sesuai `variance_pct` vs `threshold_pct`).

---

## 6. Security

| Group | Hak |
|---|---|
| `group_bunker_user` (Bunker/Procurement Staff) | RWC inquiry, quote, delivery (no unlink confirmed), tidak bisa resolve dispute |
| `group_bunker_surveyor_portal` (Surveyor eksternal, opsional) | Create/write survey pada delivery yang ditugaskan saja (record rule) — **opsional di MVP, default: staff input manual atas nama surveyor**, lihat §11 |
| `group_bunker_manager` | Full + resolve dispute + approve BOD/BOR + konfigurasi tolerance/threshold |
| Operations (`group_voyage_ops_user` dari `vessel_voyage_operations`) | Read ROB reconciliation, review & flag |
| Finance (`account.group_account_invoice`) | Read PO/vendor bill terkait, RWC BOD/BOR settlement |

`ir.model.access.csv` — prefix modul `vessel_bunker_management_*`.

---

## 7. Integrasi Antar Modul

| Modul | Integrasi | Sifat Dependency |
|---|---|---|
| `fleet_fuel_log` | Sumber `fleet.fuel.type` (reuse master), sumber `total_consumption` untuk ROB reconciliation | **Wajib** — fitur inti (rekonsiliasi) tidak bermakna tanpa data konsumsi |
| `vessel_voyage_operations` | Sumber noon report (ROB aktual), `voyage_id` sebagai konteks reconciliation | **Wajib** — sama alasan di atas, ROB hanya ada di noon report |
| `vessel_chartering` | Target tulis `bunker_adjustment` di hire statement (BOD/BOR), sumber `vessel.charter.contract` & analytic plan | **Wajib** — BOD/BOR secara definisi adalah fitur Time Charter dari modul ini |
| `purchase` | Auto-create PO saat nominasi supplier | **Wajib** (`purchase` modul Odoo standar) |
| `stock` | Penerimaan bunker sebagai `stock.picking` ke lokasi kapal | **Wajib** (`stock` modul Odoo standar) |
| `account` | Vendor bill dari PO, analytic distribution | **Wajib** |

**Catatan penting:** berbeda dari `vessel_chartering` yang secara sengaja membuat dependency ke `fleet_fuel_log` bersifat *soft* (via bridge), modul ini **wajib** hard-depend ke `fleet_fuel_log` dan `vessel_voyage_operations` karena fitur intinya — ROB reconciliation — secara definisi butuh kedua sisi data (konsumsi + posisi/ROB) sekaligus. Modul tidak bisa "berdiri sendiri tanpa makna" seperti pola bridge sebelumnya (lihat §8).

---

## 8. Keputusan Desain & Alternatif yang Ditolak

| Keputusan | Alternatif ditolak | Alasan |
|---|---|---|
| Dependency **wajib (hard)** ke `fleet_fuel_log` & `vessel_voyage_operations` | Soft dependency via bridge module, konsisten pola `vessel_chartering` | ROB reconciliation adalah *raison d'être* modul ini — tanpa consumption (`fleet_fuel_log`) dan ROB (`vessel_voyage_operations`) modul kehilangan fitur intinya, beda dengan fuel log yang tetap berguna tanpa chartering |
| Reuse `fleet.fuel.type` dari `fleet_fuel_log`, bukan master baru | Master `vessel.bunker.fuel.type` terpisah | Konsisten prinsip "satu sumber kebenaran" yang sudah dipakai di seluruh solusi (port = `res.partner`, dsb.); harga & akun akuntansi per jenis BBM sudah ada di master itu |
| Independent survey sebagai model **opsional** (`survey_id` 0..1 di delivery, bukan wajib) | Survey wajib untuk setiap BDN | Realita lapangan: klien kecil (tug & barge) sering tidak pakai independent surveyor untuk tiap delivery karena biaya; MVP fleksibel sesuai kebijakan per klien, dispute-detection tetap jalan jika survey diinput |
| BOD/BOR ditulis balik ke `vessel.hire.statement.line.bunker_adjustment` via tombol eksplisit ("Settle") | Auto-write otomatis tanpa approval | Nilai BOD/BOR mempengaruhi invoice hire final ke charterer — perlu titik approval eksplisit (state `confirmed`→`settled`) sebelum masuk dokumen finansial, konsisten pola approval di `vessel_chartering` (laytime harus `approved` sebelum invoice) |
| Trigger pembuatan draft BOD/BOR dari sisi `vessel_chartering` (method dipanggil, bukan `vessel_bunker_management` yang polling kontrak) | `vessel_bunker_management` cron polling kontrak time charter untuk delivery/redelivery baru | Menjaga arah dependency tetap satu arah (bunker_management depends on chartering, bukan sebaliknya) — kontrak charter memanggil hook/method modul bunker (via `hasattr`/module check) saat event terjadi, bukan bunker management yang "mengintip" state kontrak terus-menerus via cron terpisah yang rawan race condition |
| Toleransi survey & threshold ROB **configurable**, bukan hardcode | Hardcode 0.5% universal | Industri punya variasi toleransi tergantung jenis kapal/kontrak; konsisten filosofi "configurable" yang dipakai `vessel_voyage_pnl` untuk alokasi cost |

---

## 9. Rencana Fase & Estimasi Kompleksitas

| Fase | Deliverable | Kompleksitas |
|---|---|---|
| **MVP (fase ini)** | Model §3 lengkap, procurement flow (§4.1), BDN + survey + dispute (§4.2), ROB reconciliation manual & cron (§4.3), BOD/BOR settlement (§4.4), integrasi PO/stock/vendor bill, menu & views, security, cron §4.5 | Tinggi — rekonsiliasi lintas 3 sumber data adalah inti kompleksitas, mirip `vessel_voyage_pnl` |
| Fase 2 | Portal surveyor eksternal (input langsung, bukan lewat staff), API feed MOPS/Platts otomatis (§7.4 brainstorm), analisa hedging dasar, laporan PDF dispute resmi ke supplier | Sedang |
| Fase 3 | Prediksi ROB (forecast kapan bunker akan habis berdasar trend konsumsi), integrasi langsung ke `vessel_voyage_pnl` cost line otomatis (saat ini masih via `account.move.line` umum) | Sedang |

---

## 10. Kriteria Penerimaan (Acceptance Criteria) MVP

1. Install bersih di Odoo 19 Enterprise tanpa error, tanpa konflik dengan `vessel_chartering`, `vessel_voyage_operations`, `vessel_voyage_pnl`, dan modul fleet existing
2. Buat inquiry dengan 3 quote supplier berbeda → nominasi salah satu → `purchase.order` ter-generate otomatis dengan line & harga sesuai quote terpilih
3. Input BDN 500 MT, survey menghasilkan 495 MT dengan tolerance 0.5% → `is_dispute=True` otomatis, tidak bisa `confirmed` sebelum `dispute_state='resolved'`
4. Setelah dispute resolved → konfirmasi delivery → `stock.picking` ter-generate dengan qty sesuai `qty_confirmed_mt` (495 MT, bukan 500 MT BDN)
5. ROB reconciliation: previous ROB 200 MT, supply 495 MT, consumption 150 MT (dari `fleet_fuel_log`) → expected ROB 545 MT; noon report aktual 500 MT → variance −45 MT, `is_anomaly=True` jika threshold < 8%
6. Time charter delivery event → `vessel.bunker.bod.bor` draft ter-generate otomatis dengan `rob_fo`/`rob_do` dari noon report terdekat
7. Settle BOD/BOR → `bunker_adjustment` di `vessel.hire.statement.line` terisi dengan nilai & tanda (+/−) yang benar sesuai `settlement_direction`
8. User role `group_bunker_user` tidak bisa resolve dispute maupun approve BOD/BOR settlement
9. Quote dengan harga jauh di atas `vessel.bunker.price.reference` terdekat → `price_vs_market_pct` menampilkan angka signifikan sebagai sinyal review
10. Semua unit test `TransactionCase` untuk compute (`variance_qty_mt`, `expected_rob`, `variance_pct`, `settlement_amount`) lulus
11. Tidak ada penggunaan `display_name` sebagai field custom, `fields.Datetime.from_string`, atau `@api.depends()` kosong (checklist audit Odoo 19)

---

## 11. Pertanyaan Terbuka (perlu keputusan sebelum coding)

1. **Portal surveyor eksternal** — apakah independent surveyor butuh akses input langsung (portal user, mirip Nakhoda di `vessel_voyage_operations`), atau MVP cukup staff internal yang input hasil survey dari laporan PDF surveyor? Berpengaruh besar ke security & effort development.
2. **Lokasi stok kapal** — apakah `fleet_fuel_log`/`fleet_model_sparepart` sudah punya konsep `stock.location` per kapal yang bisa langsung dipakai untuk `stock.picking` penerimaan bunker, atau perlu didefinisikan dari nol di modul ini?
3. **Threshold ROB reconciliation** — satu nilai global, atau perlu berbeda per jenis kapal (kapal besar dengan tangki besar bisa punya toleransi absolut lebih besar meski persentase sama)?
4. **Frekuensi ROB reconciliation** — otomatis per pasangan noon report berurutan (bisa banyak record kecil), atau lebih baik per periode custom (mingguan/per port-to-port leg) yang dipilih Operations? MVP saat ini asumsi per-pasangan noon report.
5. **BOD/BOR untuk kontrak non-time-charter** — apakah ada skenario serupa untuk relet (charter-in lalu charter-out) yang butuh treatment BOD/BOR juga, atau murni Time Charter standar untuk MVP?
6. **Approval matrix nominasi supplier** — apakah nominasi di atas nilai tertentu perlu approval berjenjang (mirip pertanyaan terbuka approval matrix di `vessel_chartering` §11), atau cukup role `group_bunker_manager`?

---

## 12. Panduan Eksekusi Development (untuk Claude Code)

### 12.1 Struktur Direktori Modul (Odoo standar)

```
vessel_bunker_management/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── vessel_bunker_inquiry.py
│   ├── vessel_bunker_quote.py
│   ├── vessel_bunker_delivery.py
│   ├── vessel_bunker_survey.py
│   ├── vessel_bunker_rob_reconciliation.py
│   ├── vessel_bunker_bod_bor.py
│   ├── vessel_bunker_price_reference.py
│   ├── fleet_vehicle.py             # extend bunker_inquiry_ids, rob_reconciliation_ids
│   ├── vessel_voyage.py             # extend bunker_delivery_ids, rob_anomaly_count
│   ├── vessel_charter_contract.py   # extend bod_bor_ids + hook trigger delivery/redelivery
│   └── vessel_hire_statement_line.py # extend bod_bor_id
├── wizards/
│   └── __init__.py                  # (wizard resolve dispute, jika perlu form terpisah)
├── views/
│   ├── vessel_bunker_inquiry_views.xml
│   ├── vessel_bunker_quote_views.xml
│   ├── vessel_bunker_delivery_views.xml
│   ├── vessel_bunker_survey_views.xml
│   ├── vessel_bunker_rob_reconciliation_views.xml
│   ├── vessel_bunker_bod_bor_views.xml
│   ├── vessel_bunker_price_reference_views.xml
│   ├── fleet_vehicle_views.xml
│   ├── vessel_voyage_views.xml
│   ├── vessel_charter_contract_views.xml
│   └── menu_views.xml
├── data/
│   ├── ir_sequence_data.xml
│   ├── mail_template_data.xml
│   └── ir_cron_data.xml
├── security/
│   ├── vessel_bunker_management_groups.xml
│   ├── ir.model.access.csv
│   └── vessel_bunker_management_security.xml   # record rule surveyor portal (jika diimplementasi)
├── report/
│   └── (opsional, laporan dispute PDF fase 2)
└── tests/
    ├── __init__.py
    ├── test_bunker_procurement.py
    ├── test_bdn_survey_dispute.py
    ├── test_rob_reconciliation.py
    └── test_bod_bor_settlement.py
```

### 12.2 Urutan Kerja yang Disarankan (todo list untuk Claude Code)

1. **Skeleton modul** — `__manifest__.py` dengan depends `['fleet', 'mail', 'purchase', 'stock', 'account', 'fleet_fuel_log', 'vessel_chartering', 'vessel_voyage_operations']` — perhatikan semuanya **hard dependency** sesuai §7, tidak ada soft-check di modul ini kecuali untuk fitur opsional portal surveyor (§11 poin 1)
2. **Master data**: `vessel.bunker.price.reference` + security dasar — cek dulu bahwa `fleet.fuel.type` dari `fleet_fuel_log` bisa langsung direferensikan (jangan bikin master baru, §8)
3. **Model procurement**: `vessel.bunker.inquiry` (§3.2) → `vessel.bunker.quote` (§3.3) — implementasikan dulu tanpa tombol nominasi/PO generation, test compute `total_estimated_usd` & `price_vs_market_pct` dulu
4. **Integrasi PO**: implementasikan `action_nominate` yang generate `purchase.order` — test dengan `TransactionCase` bahwa PO line & analytic distribution benar sebelum lanjut
5. **Model BDN & survey**: `vessel.bunker.delivery` (§3.4) → `vessel.bunker.survey` (§3.5) — implementasikan state machine dispute (§4.2) dengan test case variance di atas & di bawah tolerance
6. **Integrasi stock**: `action_confirm_delivery` yang generate `stock.picking` — verifikasi dulu field/model lokasi stok kapal existing (§11 poin 2) sebelum coding, jangan asumsi
7. **Model ROB reconciliation**: `vessel.bunker.rob.reconciliation` (§3.6) — bagian paling kompleks, pecah compute jadi method terpisah per komponen (`_compute_total_supply`, `_compute_total_consumption`, `_compute_expected_rob`) supaya mudah di-unit-test satu-satu
8. **Model BOD/BOR**: `vessel.bunker.bod.bor` (§3.7) — implementasikan hook di `vessel.charter.contract` (extend, method `write` atau override state transition delivery/redelivery) yang memanggil pembuatan draft BOD/BOR; pastikan hook ini **tidak** membuat `vessel_chartering` depend balik ke modul ini (gunakan pattern `self.env['ir.module.module'].search(...)` check atau `hasattr` sebelum memanggil model bunker dari kontrak, exactly seperti pola bridge fuel log — meski di sini dependency bunker→chartering wajib, arah panggilan tetap harus dijaga satu arah)
9. **Security & access**: groups, `ir.model.access.csv` (prefix wajib `vessel_bunker_management_`), record rule surveyor portal jika diimplementasi (§11 poin 1)
10. **Cron jobs** (§4.5) + mail templates (§4.6)
11. **Views & menu** (§5)
12. **Test end-to-end** mengikuti skenario Kriteria Penerimaan §10 satu per satu — siapkan fixture minimal dari `vessel_chartering` (kontrak time charter) & `vessel_voyage_operations` (voyage + 2 noon report approved) di `setUp`
13. **Audit checklist final**:
    - `grep -rn "display_name" models/` → nihil sebagai field custom
    - `grep -rn "fields.Datetime.from_string" .` → nihil
    - `grep -rn "@api.depends()" models/` → tidak ada depends kosong
    - Cek `ir.model.access.csv` prefix `vessel_bunker_management_`
    - Cek xmlid menu valid, tidak bentrok
    - Install ulang dari nol (`-i vessel_bunker_management --test-enable`) di database yang sudah berisi 8 modul existing (5 fleet + chartering + voyage_operations + voyage_pnl)

### 12.3 Dependency & Prasyarat Environment

- `fleet_fuel_log`, `vessel_chartering`, `vessel_voyage_operations` **harus** sudah terinstall (hard dependency penuh, §7-§8) — modul ini tidak bisa diinstall standalone, beda dari pola bridge modul-modul sebelumnya
- Sebelum mulai coding model `stock.picking` (langkah 6), **wajib** cek existing implementasi lokasi stok kapal di `fleet_fuel_log`/`fleet_model_sparepart` — jika belum ada konsep `stock.location` per kapal yang jelas, ini jadi blocker yang perlu diselesaikan dulu (via diskusi/keputusan desain terpisah), jangan menebak
- `vessel_voyage_pnl` **tidak** menjadi dependency modul ini (arah sebaliknya — `vessel_voyage_pnl` di masa depan akan konsumsi data dari modul ini sebagai `bunker_cost` line, lihat §9 Fase 3), jadi tidak perlu ada di environment dev untuk modul ini, meski akan ada di database produksi bersamaan

### 12.4 Definisi "Selesai" untuk Modul Ini

Modul dianggap siap review jika: seluruh 11 poin Kriteria Penerimaan (§10) lulus sebagai automated test, checklist audit §12.2 poin 13 bersih, dan modul bisa diinstall di database yang sudah berisi 8 modul existing tanpa error maupun warning dependency melingkar. Tambahan khusus modul ini: skenario dispute (poin 3 §10) dan ROB anomaly (poin 5 §10) harus punya test case dengan angka yang **sengaja di luar toleransi** untuk membuktikan flag otomatis benar-benar terpicu, bukan hanya jalur "semua normal" yang diuji.
