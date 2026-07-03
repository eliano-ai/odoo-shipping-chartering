# Dokumen Teknis — Modul `vessel_voyage_pnl`

**Proyek:** Odoo Shipping Vertical Solution — Layer 3 (Finansial)
**Target Platform:** Odoo 19.0 Enterprise
**Lisensi:** LGPL-3
**Penyusun:** Sunartha ERP Consulting
**Status Dokumen:** Draft v1.0 — untuk review sebelum development
**Tanggal:** Juli 2026
**Urutan roadmap:** #3 (setelah `vessel_chartering` & `vessel_voyage_operations`, sebelum `vessel_bunker_management`)

---

## 1. Latar Belakang & Tujuan

Manajemen tahu total laba perusahaan dari laporan keuangan bulanan, tapi tidak tahu **voyage mana yang rugi**. Keputusan terima/tolak cargo, negosiasi ulang charter, atau evaluasi kapal mana yang jadi beban armada saat ini masih berbasis intuisi/pengalaman, bukan data.

Modul ini adalah **payoff utama** dari investasi Analytic Plans (plan Vessel + plan Voyage) yang sudah dikunci sejak `vessel_chartering`. Semua modul Layer 1-2 (`fleet_fuel_log`, `fleet_maintenance_schedule`, `vessel_crew_management`, `vessel_chartering`, `vessel_voyage_operations`) sudah/akan menulis transaksi dengan analytic distribution ke plan yang sama — modul ini tinggal **mengagregasi**, mengalokasikan biaya tidak langsung, dan menyajikan sebagai P&L per voyage, per kapal, dan per periode, lengkap dengan variance terhadap estimate dan budget.

### 1.1 Ruang Lingkup (Scope)

| In Scope | Out of Scope (modul lain) |
|---|---|
| Voyage P&L statement (agregasi revenue, direct cost, allocated cost per voyage) | Sumber data mentah: freight/demurrage (`vessel_chartering`), bunker konsumsi (`fleet_fuel_log`), port cost (`vessel_voyage_operations`), crew cost (`vessel_crew_management`/payroll), maintenance (`fleet_maintenance_schedule`) |
| Metode alokasi biaya tidak langsung (crew, maintenance, depresiasi) — configurable | Perhitungan payroll itu sendiri (`hr_payroll`) |
| Estimate vs Actual — variance analysis per komponen | Pembuatan voyage estimate (`vessel_chartering`, model `vessel.voyage.estimate` sudah ada) |
| TCE aktual per kapal per periode + benchmark | Bunker procurement & BDN detail (`vessel_bunker_management`, fase berikutnya) |
| Vessel P&L bulanan (agregasi lintas-voyage per kapal per bulan) | Konsolidasi laporan keuangan resmi perusahaan (`account` standar) |
| Budget per vessel per tahun + variance terhadap actual | Approval budget korporat lintas-departemen non-armada |
| Dashboard direksi (utilisasi, TCE trend, top voyage rugi, demurrage outstanding) | Data source dashboard yang belum ada di modul lain (mis. compliance score dari `fleet_document_id` — dikonsumsi read-only saja) |

### 1.2 Persona Pengguna

| Role | Kebutuhan Utama |
|---|---|
| **Finance/Accounting** | Verifikasi & lock P&L per voyage sebelum jadi acuan resmi; kelola alokasi cost tidak langsung |
| **Chartering Manager** | Bandingkan estimate vs actual sebagai feedback loop akurasi fixture berikutnya |
| **Fleet/Operations Manager** | Lihat kapal mana yang jadi beban (vessel P&L bulanan), evaluasi utilisasi |
| **Direksi** | Dashboard ringkas: TCE trend, top 10 voyage rugi, demurrage outstanding, realisasi vs budget |

---

## 2. Konsep Bisnis yang Dimodelkan

### 2.1 Struktur P&L per Voyage

```
Revenue
  + Freight Revenue          (dari vessel.charter.contract, freight_amount_final)
  + Demurrage Revenue        (dari vessel.laytime.calculation, approved)
  − Despatch (cost)          (dari vessel.laytime.calculation, approved)
  − Brokerage                (brokerage_pct × freight, dari kontrak)
  + Other Revenue            (manual adjustment, jarang)
= Total Revenue

Direct Cost (melekat langsung ke voyage ini)
  − Bunker Cost              (dari fleet_fuel_log, account.move terkait analytic voyage)
  − Port Cost (PDA/FDA)      (dari vessel.port.disbursement, type=fda confirmed)
  − Cargo Handling Cost      (account.move.line dikategorikan manual/mapping)
  − Insurance Voyage         (account.move.line dikategorikan)
  − Other Direct Cost
= Total Direct Cost

Allocated Cost (tidak melekat langsung, dialokasikan proporsional)
  − Crew Cost                (pool bulanan per kapal dari payroll ÷ voyage days proporsional)
  − Maintenance Cost         (pool bulanan/tahunan per kapal, alokasi configurable)
  − Depreciation             (pool tahunan per kapal ÷ hari, alokasi configurable)
  − Overhead                 (opsional, % dari revenue atau fixed per hari)
= Total Allocated Cost

Voyage Result = Total Revenue − Total Direct Cost − Total Allocated Cost
TCE per Day   = (Total Revenue − Total Direct Cost yang relevan TCE*) / Voyage Days
```

*\*Definisi baku TCE (Time Charter Equivalent) di industri hanya mengurangkan voyage-related cost (bunker, port cost, komisi) — bukan allocated cost tetap seperti crew/depresiasi. Modul ini mengikuti definisi tersebut secara default, lihat §11 poin 1 untuk konfirmasi dengan klien pilot.*

### 2.2 Sumber Data per Komponen

| Komponen | Sumber | Cara Ambil |
|---|---|---|
| Freight, Demurrage, Despatch, Brokerage | `vessel_chartering` | Query `account.move.line` dengan `analytic_distribution` mengandung `analytic_account_id` (plan Voyage) milik voyage ini, filter by product category Revenue |
| Bunker Cost | `fleet_fuel_log` (soft dependency) | Query `account.move.line` dari journal entry fuel log yang linked ke `fleet.vehicle.trip` = `voyage.fleet_trip_id` (jika ada bridge); fallback: filter analytic voyage langsung jika fuel log sudah menulis analytic yang sama |
| Port Cost | `vessel_voyage_operations` | `vessel.port.disbursement` type=`fda`, state=`confirmed`, per `port_call_id.voyage_id` |
| Cargo Handling, Insurance Voyage | `account` (manual/vendor bill) | `account.move.line` dikategorikan via mapping `vessel.pnl.cost.category` ↔ akun akuntansi, atau tag manual analytic + product category |
| Crew Cost | `vessel_crew_management` + `hr_payroll` (soft dependency) | Pool biaya payroll ABK yang `on_board` di kapal tsb selama bulan berjalan, dialokasikan ke voyage aktif proporsional hari |
| Maintenance Cost | `fleet_maintenance_schedule` | Actual cost dari `fleet.maintenance.schedule` (done) per kapal per periode, dialokasikan |
| Depreciation | `account.asset` (Odoo standar, jika aset kapal dikelola sebagai fixed asset) | Nilai depresiasi bulanan per kapal, dialokasikan per hari voyage |

### 2.3 Metode Alokasi Biaya Tidak Langsung

Biaya tidak langsung (crew, maintenance, depresiasi, overhead) tidak melekat ke satu voyage — perlu dialokasikan. Metode yang didukung (configurable per kategori biaya, di master `vessel.cost.allocation.rule`):

| Metode | Formula |
|---|---|
| `per_voyage_day` | Pool biaya bulanan kapal × (hari voyage ini dalam bulan tsb / total hari kapal beroperasi dalam bulan tsb) |
| `per_calendar_day` | Pool biaya bulanan kapal / jumlah hari kalender bulan tsb × jumlah hari voyage overlap bulan tsb (termasuk hari idle) |
| `equal_split` | Pool biaya dibagi rata ke semua voyage aktif kapal itu dalam periode, tanpa mempertimbangkan durasi |
| `fixed_percentage` | % tetap dari revenue voyage (umum untuk overhead) |
| `manual` | Diinput manual per voyage oleh Finance (fallback jika data pool tidak tersedia) |

**Prinsip penting:** metode alokasi *tidak boleh diubah di tengah tahun berjalan* tanpa proses migrasi — konsisten dengan catatan risiko di brainstorm §10 soal "Analytic plans harus dikunci sekarang".

### 2.4 Estimate vs Actual

Setiap voyage yang berasal dari kontrak dengan `vessel.voyage.estimate` ber-state `selected` dijadikan baseline. Variance dihitung per komponen (revenue, bunker, port cost, TCE) — bukan hanya total, supaya jadi feedback loop akurasi estimasi ke Chartering Manager (\"biasanya kita under-estimate bunker sebesar X%\").

### 2.5 TCE Aktual & Benchmark

`tce_actual_per_day` dihitung per voyage, lalu diagregasi jadi **TCE rata-rata per kapal per periode** (`vessel.vessel.pnl`) untuk dibandingkan antar kapal sejenis dan terhadap rate pasar (input manual referensi, bukan feed otomatis di MVP).

### 2.6 Vessel P&L Bulanan

Agregasi seluruh voyage yang overlap bulan berjalan per kapal, plus alokasi cost yang tidak habis diserap voyage (idle time) → gambaran kapal ini net profit atau net cost ke perusahaan bulan itu, termasuk **utilisasi (%)** = hari on-voyage / hari kalender.

### 2.7 Budget per Vessel per Tahun

Rencana biaya (dan optionally revenue target) per kapal per bulan, dibandingkan realisasi dari `vessel.vessel.pnl`. Alert jika realisasi menyimpang dari budget di luar threshold.

---

## 3. Desain Data Model

### 3.1 Diagram Relasi (ringkas)

```
vessel.voyage.pnl (jantung modul — 1 record per voyage completed)
 ├── voyage_id → vessel.voyage (vessel_voyage_operations), unique
 ├── contract_id → vessel.charter.contract (related dari voyage_id)
 ├── vessel_id → fleet.vehicle (related)
 ├── analytic_account_id → account.analytic.account (related, plan Voyage)
 ├── estimate_id → vessel.voyage.estimate (baseline, state=selected, opsional)
 ├── line_ids → vessel.voyage.pnl.line (1..n, breakdown & traceability)
 └── state → draft / computed / locked

vessel.voyage.pnl.line
 ├── pnl_id → vessel.voyage.pnl
 ├── cost_category_id → vessel.pnl.cost.category (master)
 ├── source_model / source_res_id → reference record asal (traceability, drill-down)
 └── amount, is_allocated, allocation_rule_id (jika allocated)

vessel.vessel.pnl (agregasi bulanan per kapal)
 ├── vessel_id → fleet.vehicle
 ├── period_month / period_year
 └── (compute dari vessel.voyage.pnl yang overlap periode + idle allocation)

vessel.vessel.budget (tahunan per kapal)
 ├── vessel_id → fleet.vehicle
 ├── year
 └── budget_line_ids → vessel.vessel.budget.line (per bulan × per kategori biaya)

Master data:
 vessel.pnl.cost.category      (Freight, Demurrage, Bunker, Port Cost, Crew, Maintenance, Depreciation, Overhead, ...)
 vessel.cost.allocation.rule   (kategori biaya → metode alokasi)
```

### 3.2 Model: `vessel.voyage.pnl`

`_name = 'vessel.voyage.pnl'`
`_inherit = ['mail.thread']`
`_order = 'voyage_id desc'`

| Field | Type | Keterangan |
|---|---|---|
| `voyage_id` | Many2one `vessel.voyage`, required, unique | Domain state=`completed` |
| `contract_id` | Many2one, related `voyage_id.charter_contract_id`, store | |
| `vessel_id` | Many2one, related `voyage_id.vessel_id`, store | |
| `analytic_account_id` | Many2one, related, store | Plan Voyage |
| `estimate_id` | Many2one `vessel.voyage.estimate` | Auto-set: estimate ber-state `selected` milik `contract_id`, editable override |
| `voyage_days` | Float, compute, store | `date_arrival_final − date_departure` dari `voyage_id`, dalam hari |
| **Revenue** | | |
| `freight_revenue` | Monetary, compute, store | |
| `demurrage_revenue` | Monetary, compute, store | |
| `despatch_cost` | Monetary, compute, store | |
| `brokerage_cost` | Monetary, compute, store | |
| `other_revenue` | Monetary | Manual adjustment |
| `total_revenue` | Monetary, compute, store | |
| **Direct Cost** | | |
| `bunker_cost` | Monetary, compute, store | |
| `port_cost` | Monetary, compute, store | |
| `cargo_handling_cost` | Monetary, compute, store | |
| `insurance_voyage_cost` | Monetary, compute, store | |
| `other_direct_cost` | Monetary | Manual adjustment |
| `total_direct_cost` | Monetary, compute, store | |
| **Allocated Cost** | | |
| `crew_cost_allocated` | Monetary, compute, store | |
| `maintenance_cost_allocated` | Monetary, compute, store | |
| `depreciation_allocated` | Monetary, compute, store | |
| `overhead_allocated` | Monetary, compute, store | |
| `total_allocated_cost` | Monetary, compute, store | |
| **Hasil** | | |
| `voyage_result` | Monetary, compute, store | `total_revenue − total_direct_cost − total_allocated_cost` |
| `tce_actual_per_day` | Monetary, compute, store | `(total_revenue − total_direct_cost) / voyage_days` |
| **Variance vs Estimate** | | |
| `revenue_variance` / `revenue_variance_pct` | Monetary/Float, compute | vs `estimate_id.revenue_estimate` |
| `cost_variance` / `cost_variance_pct` | Monetary/Float, compute | vs total cost estimate |
| `tce_variance` | Monetary, compute | vs `estimate_id.tce_per_day` |
| **Meta** | | |
| `line_ids` | One2many `vessel.voyage.pnl.line` | |
| `state` | Selection | `draft` / `computed` / `locked` |
| `computed_date` | Datetime | Kapan terakhir di-generate/recompute |
| `locked_by` / `locked_date` | Many2one/Datetime | |
| `currency_id` | Many2one, default company currency (biasanya USD) | Basis P&L; line lintas-mata-uang dikonversi kurs tanggal transaksi masing-masing |

#### Constraint
- Satu `voyage_id` hanya boleh punya 1 record `vessel.voyage.pnl` (SQL unique constraint)
- Field compute hanya bisa diubah via tombol "Recompute" saat `state='draft'`; saat `state='locked'` semua field read-only kecuali lewat adjustment line manual (audit trail via `mail.thread`)

### 3.3 Model: `vessel.voyage.pnl.line`

Baris rincian untuk traceability — setiap angka agregat di header punya jejak sumbernya.

`_name = 'vessel.voyage.pnl.line'`

| Field | Type | Keterangan |
|---|---|---|
| `pnl_id` | Many2one, required, ondelete=cascade | |
| `cost_category_id` | Many2one `vessel.pnl.cost.category`, required | |
| `category_group` | Selection, related dari cost_category_id | `revenue` / `direct_cost` / `allocated_cost` |
| `source_model` | Char | Nama model asal, mis. `account.move.line`, `vessel.port.disbursement` |
| `source_res_id` | Integer | ID record asal — dipakai tombol "Lihat Sumber" (generic `ir.actions.act_window` dinamis) |
| `description` | Char | |
| `amount` | Monetary | Positif untuk revenue, negatif untuk cost (konsisten satu konvensi tanda) |
| `is_allocated` | Boolean | |
| `allocation_rule_id` | Many2one `vessel.cost.allocation.rule` | Terisi jika `is_allocated=True` |
| `is_manual_adjustment` | Boolean | True jika diinput manual oleh Finance (bukan hasil compute) |

### 3.4 Model: `vessel.vessel.pnl`

Agregasi bulanan per kapal — termasuk voyage yang overlap dan alokasi cost yang tidak terserap voyage (idle days).

`_name = 'vessel.vessel.pnl'`
`_order = 'period_year desc, period_month desc'`

| Field | Type | Keterangan |
|---|---|---|
| `vessel_id` | Many2one `fleet.vehicle`, required | |
| `period_month` | Selection 1-12 | |
| `period_year` | Integer | |
| `voyage_pnl_ids` | Many2many `vessel.voyage.pnl`, compute | Voyage yang overlap periode ini |
| `total_revenue` | Monetary, compute, store | Sum, pro-rata jika voyage overlap 2 bulan (berdasar hari overlap) |
| `total_cost` | Monetary, compute, store | Direct + allocated, pro-rata sama |
| `idle_cost_allocated` | Monetary, compute, store | Pool crew/maintenance/depresiasi yang tidak terserap voyage (kapal idle/menunggu fixture) |
| `net_result` | Monetary, compute, store | |
| `calendar_days` | Integer, compute | Jumlah hari kalender bulan itu |
| `voyage_days_total` | Float, compute | Sum hari voyage overlap |
| `utilization_pct` | Float, compute, store | `voyage_days_total / calendar_days × 100` |
| `avg_tce` | Monetary, compute, store | Rata-rata `tce_actual_per_day` tertimbang hari voyage |
| `state` | Selection | `draft` / `closed` (closed = tidak recompute otomatis lagi setelah bulan tutup buku) |

Constraint: unique `(vessel_id, period_month, period_year)`.

### 3.5 Model: `vessel.vessel.budget`

`_name = 'vessel.vessel.budget'`
`_inherit = ['mail.thread']`

| Field | Type | Keterangan |
|---|---|---|
| `vessel_id` | Many2one, required | |
| `year` | Integer, required | |
| `budget_line_ids` | One2many `vessel.vessel.budget.line` | |
| `total_budget_cost` | Monetary, compute | |
| `total_actual_cost` | Monetary, compute | Dari `vessel.vessel.pnl` tahun berjalan |
| `state` | Selection | `draft` / `approved` |

Constraint: unique `(vessel_id, year)`.

### 3.6 Model: `vessel.vessel.budget.line`

| Field | Type | Keterangan |
|---|---|---|
| `budget_id` | Many2one, required, ondelete=cascade | |
| `month` | Selection 1-12 | |
| `cost_category_id` | Many2one `vessel.pnl.cost.category` | |
| `planned_amount` | Monetary | |
| `actual_amount` | Monetary, compute | Dari `vessel.vessel.pnl` bulan & kategori terkait |
| `variance_amount` / `variance_pct` | Monetary/Float, compute | |

### 3.7 Master: `vessel.pnl.cost.category`

| Field | Type | Keterangan |
|---|---|---|
| `name` | Char | Freight Revenue, Demurrage, Despatch, Brokerage, Bunker, Port Cost, Cargo Handling, Insurance Voyage, Crew Cost, Maintenance, Depreciation, Overhead, Other |
| `category_group` | Selection | `revenue` / `direct_cost` / `allocated_cost` |
| `default_account_ids` | Many2many `account.account` | Untuk mapping otomatis saat kategorisasi `account.move.line` yang tidak berasal dari modul terstruktur (mis. cargo handling dari vendor bill manual) |
| `sequence` | Integer | Urutan tampil di P&L statement |
| `active` | Boolean | |

Seed via data XML `noupdate="1"` untuk kategori standar; Finance boleh tambah kategori "Other" custom.

### 3.8 Master: `vessel.cost.allocation.rule`

| Field | Type | Keterangan |
|---|---|---|
| `cost_category_id` | Many2one `vessel.pnl.cost.category`, domain category_group=`allocated_cost` | |
| `allocation_method` | Selection | `per_voyage_day` / `per_calendar_day` / `equal_split` / `fixed_percentage` / `manual` |
| `fixed_percentage_value` | Float | Terisi jika method `fixed_percentage` |
| `active` | Boolean | |

Constraint: 1 rule aktif per `cost_category_id` (tidak boleh dobel method untuk kategori yang sama).

### 3.9 Extend model existing

**`fleet.vehicle`**:
| Field | Keterangan |
|---|---|
| `voyage_pnl_ids` | One2many `vessel.voyage.pnl` — riwayat P&L voyage kapal ini |
| `vessel_pnl_ids` | One2many `vessel.vessel.pnl` — riwayat P&L bulanan |
| `current_month_utilization_pct` | Float, compute — quick info di form kapal |

**`vessel.voyage`** (dari `vessel_voyage_operations`):
| Field | Keterangan |
|---|---|
| `pnl_id` | Many2one `vessel.voyage.pnl`, compute — smart button ke P&L, jika sudah di-generate |

---

## 4. Workflow & Business Logic

### 4.1 Generate Voyage P&L

Tombol **"Generate P&L"** muncul di form `vessel.voyage` saat `state=completed` dan belum punya `pnl_id`. Aksi:
1. Create `vessel.voyage.pnl` state `draft`
2. Jalankan compute seluruh field revenue & direct cost (query `account.move.line` by `analytic_distribution` + sumber terstruktur §2.2), buat `line_ids` per item dengan traceability
3. Jalankan alokasi cost tidak langsung sesuai `vessel.cost.allocation.rule` aktif, buat `line_ids` dengan `is_allocated=True`
4. Set `state='computed'`

Tombol **"Recompute"** — hanya aktif saat `state` in (`draft`, `computed`), menjalankan ulang langkah 2-3 (replace `line_ids` non-manual, `line_ids` manual adjustment dipertahankan).

Tombol **"Lock"** (Finance/Manager only) — set `state='locked'`, field jadi read-only permanen kecuali via adjustment line + alasan wajib (wizard, tercatat di chatter).

### 4.2 Alokasi Cost Tidak Langsung — Detail Timing

Karena pool biaya (crew, maintenance, depresiasi) sifatnya bulanan sementara voyage bisa lintas bulan atau lebih pendek dari sebulan, alokasi dihitung **saat P&L voyage di-generate**, dengan pool bulan berjalan (bulan saat `date_departure` voyage jatuh; jika voyage lintas bulan, pool diambil pro-rata dari tiap bulan yang dilalui — kompleksitas ini didokumentasikan sebagai kasus khusus, lihat §11 poin 2).

### 4.3 Vessel P&L Bulanan — Cron Generation

Cron bulanan (`_cron_generate_vessel_pnl`, tanggal 5 tiap bulan untuk kasih waktu voyage bulan lalu selesai di-lock) generate/update `vessel.vessel.pnl` untuk bulan sebelumnya, per kapal aktif, mengagregasi `vessel.voyage.pnl` yang overlap + hitung idle cost.

### 4.4 Budget vs Actual

`vessel.vessel.budget.line.actual_amount` dihitung on-the-fly (compute, tidak store berat — hanya dipanggil saat dibuka user) dari `vessel.vessel.pnl` bulan & kategori terkait. Variance > threshold (config, default 20%) → activity ke Fleet Manager.

### 4.5 Cron Jobs

| Cron | Frekuensi | Fungsi |
|---|---|---|
| `_cron_generate_vessel_pnl` | Bulanan (tgl 5) | Generate/update `vessel.vessel.pnl` bulan sebelumnya per kapal |
| `_cron_pnl_pending_lock_alert` | Mingguan | Voyage P&L `state=computed` > 14 hari belum di-lock → activity ke Finance |
| `_cron_budget_variance_alert` | Bulanan | Budget line dengan variance > threshold → activity ke Fleet Manager |

### 4.6 Notifikasi

Email/activity: P&L voyage siap review (ke Finance), variance estimate signifikan (>25%, ke Chartering Manager — feedback akurasi), budget variance tinggi (ke Fleet Manager).

---

## 5. Views & Menu

**Menu:** Fleet → **Voyage P&L**

```
Voyage P&L
├── Voyage P&L
│   ├── Semua Voyage P&L         (list, form; filter by state)
│   ├── Perlu Review             (filter state=computed)
│   └── Top Voyage Rugi          (list sorted voyage_result asc)
├── Vessel P&L
│   ├── P&L Bulanan per Kapal    (list, pivot: kapal × bulan)
│   └── Utilisasi & TCE Trend    (graph)
├── Budget
│   ├── Budget per Kapal         (list, form)
│   └── Realisasi vs Budget      (pivot)
├── Laporan
│   ├── Estimate vs Actual       (list/pivot: variance per komponen)
│   └── Dashboard Direksi        (spreadsheet_dashboard)
└── Konfigurasi (Manager only)
    ├── Kategori Biaya P&L
    └── Aturan Alokasi Biaya
```

**Form Voyage P&L** — header ringkasan (revenue/cost/result/TCE), notebook: Revenue Detail / Direct Cost Detail / Allocated Cost Detail / Estimate vs Actual / Adjustment Manual. Statusbar draft→computed→locked. Smart button ke Voyage, ke Kontrak Charter, ke Estimate.

**Dashboard Direksi** (`spreadsheet_dashboard`) — utilisasi armada (%), TCE trend per kapal, top 10 voyage rugi, demurrage receivable outstanding (dari `vessel_chartering`), realisasi vs budget ringkas.

---

## 6. Security

| Group | Hak |
|---|---|
| `group_voyage_pnl_user` (Operations/Chartering) | Read voyage P&L & vessel P&L, tidak bisa generate/lock, tidak lihat budget |
| `group_voyage_pnl_finance` | RWC voyage P&L (generate, recompute, adjustment), lock, RWC budget |
| `group_voyage_pnl_manager` | Full + konfigurasi kategori biaya & aturan alokasi |
| Direksi (group baru `group_voyage_pnl_director` atau reuse group existing) | Read-only ke semua, akses dashboard |

`ir.model.access.csv` — prefix modul `vessel_voyage_pnl_*`. Record rule: multi-company via `company_id` (related dari vessel).

---

## 7. Integrasi Antar Modul

| Modul | Integrasi | Sifat Dependency |
|---|---|---|
| `vessel_chartering` | Sumber revenue (freight, demurrage, despatch, brokerage), sumber estimate baseline, analytic plan Voyage & Vessel | **Wajib** — modul ini murni agregasi data chartering |
| `vessel_voyage_operations` | Sumber voyage (`vessel.voyage`), sumber port cost (PDA/FDA), voyage days | **Wajib** |
| `fleet_fuel_log` | Sumber bunker cost aktual | **Soft** — jika tidak terinstall, `bunker_cost` tetap bisa diisi manual via adjustment line |
| `vessel_crew_management` + `hr_payroll` | Sumber pool crew cost untuk alokasi | **Soft** — jika payroll tidak terhubung, alokasi crew pakai method `manual` sebagai fallback |
| `fleet_maintenance_schedule` | Sumber actual maintenance cost | **Soft** |
| `account` (+ `account.asset` jika ada) | Query `account.move.line` analytic, sumber depresiasi, `account` budget standar sebagai referensi opsional | **Wajib** (account selalu ada di Odoo) |
| `spreadsheet_dashboard` (Enterprise) | Dashboard direksi | **Soft** — jika modul tidak tersedia, laporan fallback ke pivot/graph view standar |

---

## 8. Keputusan Desain & Alternatif yang Ditolak

| Keputusan | Alternatif ditolak | Alasan |
|---|---|---|
| `vessel.voyage.pnl` sebagai model **snapshot tersimpan** (compute + store, dengan tombol Recompute/Lock) | Field compute murni tanpa store, dihitung ulang tiap kali dibuka | P&L jadi basis laporan resmi ke direksi & dasar keputusan bisnis — perlu titik waktu "locked" yang tidak berubah walau data sumber (mis. voucher terkoreksi) berubah belakangan; compute-only juga mahal secara performa untuk voyage lama dengan banyak move line |
| Traceability via `vessel.voyage.pnl.line` dengan `source_model`/`source_res_id` generik | Field agregat saja tanpa breakdown baris | Finance & auditor butuh drill-down "angka bunker cost 50rb USD ini dari mana" — pola generic reference lebih maintainable daripada bikin FK terpisah ke tiap model sumber |
| Metode alokasi cost tidak langsung **configurable per kategori** (`vessel.cost.allocation.rule`) | Hardcode satu metode (mis. selalu per hari) | Brainstorm eksplisit minta "metode alokasi configurable (per hari, per voyage)" — praktik lapangan bervariasi per klien; hardcode akan menyulitkan Professional/Enterprise package yang beda kebutuhan |
| TCE aktual **tidak** memasukkan allocated cost (crew/maintenance/depresiasi) | TCE dari net result penuh (termasuk allocated) | Konsisten dengan definisi TCE standar industri (dipakai juga di `vessel.voyage.estimate` fase chartering) — mencampur allocated cost akan bikin TCE tidak bisa dibandingkan dengan rate pasar/broker |
| `vessel.vessel.pnl` sebagai model agregasi bulanan terpisah, bukan cuma view/report SQL | View SQL / report langsung dari voyage P&L | Perlu simpan `idle_cost_allocated` (biaya yang tidak terserap voyage manapun saat kapal nganggur) — angka ini tidak otomatis muncul dari agregasi voyage saja, perlu logic tambahan yang lebih pas di model tersimpan daripada view |
| Dependency ke `vessel_chartering` & `vessel_voyage_operations`: **wajib** | Soft dependency | Modul ini secara definisi murni derivatif/agregasi dari dua modul tersebut — tanpa keduanya modul ini tidak punya data untuk diagregasi sama sekali |

---

## 9. Rencana Fase & Estimasi Kompleksitas

| Fase | Deliverable | Kompleksitas |
|---|---|---|
| **MVP (fase ini)** | Model §3 lengkap, generate & recompute P&L per voyage (§4.1), alokasi cost dasar 3 metode (`per_voyage_day`, `equal_split`, `manual`), estimate vs actual, vessel P&L bulanan (§4.3), budget dasar (§3.5-3.6), menu & views, security, cron §4.5 | Tinggi — logic agregasi lintas-modul & alokasi adalah inti kompleksitas |
| Fase 2 | Metode alokasi `per_calendar_day` & `fixed_percentage` penuh, integrasi `account.asset` otomatis untuk depresiasi, dashboard direksi versi lengkap (`spreadsheet_dashboard`), handling voyage lintas-bulan yang lebih presisi (pro-rata pool per hari aktual, bukan snapshot bulan keberangkatan) | Sedang-Tinggi |
| Fase 3 | Benchmark TCE vs market rate (feed eksternal manual/API), forecasting P&L voyage in-progress (belum completed, estimasi real-time berbasis noon report terkini) | Sedang |

---

## 10. Kriteria Penerimaan (Acceptance Criteria) MVP

1. Install bersih di Odoo 19 Enterprise tanpa error, tanpa konflik dengan `vessel_chartering`, `vessel_voyage_operations`, dan modul fleet existing
2. Voyage `completed` dengan freight invoice posted + 1 demurrage approved → generate P&L menghasilkan `total_revenue` benar sesuai rate × qty + demurrage
3. Bunker cost dari `fleet_fuel_log` (voyage dengan `fleet_trip_id` terisi) muncul otomatis di `bunker_cost` dengan `line_ids` traceability ke `account.move.line` asal
4. Alokasi crew cost dengan method `per_voyage_day`: pool bulanan kapal USD 30,000, voyage 10 hari dari 30 hari kapal aktif bulan itu → `crew_cost_allocated` = USD 10,000
5. Voyage dengan estimate `selected` → `revenue_variance`, `cost_variance`, `tce_variance` terhitung benar dibanding baseline
6. Lock P&L → semua field header read-only; tambah adjustment line manual tetap bisa dengan alasan wajib tercatat di chatter
7. Vessel P&L bulanan mengagregasi 2 voyage yang overlap bulan yang sama dengan benar, `utilization_pct` terhitung sesuai hari voyage vs hari kalender
8. Budget line dengan planned USD 50,000 dan actual USD 65,000 → `variance_pct` = 30%, activity terkirim ke Fleet Manager (>20% threshold default)
9. User role `group_voyage_pnl_user` tidak bisa melihat menu Budget maupun generate/lock P&L
10. Semua unit test `TransactionCase` untuk compute (`total_revenue`, `voyage_result`, `tce_actual_per_day`, alokasi 3 metode, `utilization_pct`) lulus
11. Tidak ada penggunaan `display_name` sebagai field custom, `fields.Datetime.from_string`, atau `@api.depends()` kosong (checklist audit Odoo 19)

---

## 11. Pertanyaan Terbuka (perlu keputusan sebelum coding)

1. **Definisi TCE** — konfirmasi dengan klien pilot apakah TCE aktual harus persis meniru formula di `vessel.voyage.estimate` (exclude allocated cost) atau ada penyesuaian lokal.
2. **Voyage lintas bulan** — MVP mengambil pool alokasi dari bulan `date_departure` saja (simplifikasi); perlu keputusan apakah ini cukup akurat untuk voyage tug-barge pendek (biasanya selesai < 1 bulan) vs mother vessel/time charter (voyage bisa lintas 2-3 bulan, butuh pro-rata per bulan di fase 2).
3. **Ketersediaan data payroll granular per kapal** — apakah `hr_payroll` existing klien sudah bisa di-breakdown cost per kapal (bukan cuma per karyawan), atau perlu kerja tambahan di `vessel_crew_management` dulu sebelum alokasi crew cost otomatis bisa jalan (di luar `manual` fallback).
4. **Depresiasi kapal** — apakah klien pilot mengelola kapal sebagai `account.asset` di Odoo, atau nilai depresiasi selalu diinput manual per bulan? Menentukan prioritas integrasi `account.asset` di fase 2.
5. **Historical backfill** — voyage yang sudah `completed` sebelum modul ini terinstall, apakah perlu tombol bulk-generate P&L untuk data historis, atau MVP cukup berlaku untuk voyage baru ke depan?
6. **Threshold budget variance** (default 20%) — global setting atau per kapal/per kategori biaya?

---

## 12. Panduan Eksekusi Development (untuk Claude Code)

### 12.1 Struktur Direktori Modul (Odoo standar)

```
vessel_voyage_pnl/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── vessel_voyage_pnl.py
│   ├── vessel_voyage_pnl_line.py
│   ├── vessel_vessel_pnl.py
│   ├── vessel_vessel_budget.py
│   ├── vessel_vessel_budget_line.py
│   ├── vessel_pnl_cost_category.py
│   ├── vessel_cost_allocation_rule.py
│   ├── fleet_vehicle.py            # extend voyage_pnl_ids, vessel_pnl_ids, dsb.
│   └── vessel_voyage.py            # extend pnl_id compute
├── wizards/
│   ├── __init__.py
│   └── vessel_pnl_adjustment_wizard.py   # adjustment manual saat locked, wajib alasan
├── views/
│   ├── vessel_voyage_pnl_views.xml
│   ├── vessel_vessel_pnl_views.xml
│   ├── vessel_vessel_budget_views.xml
│   ├── vessel_pnl_cost_category_views.xml
│   ├── vessel_cost_allocation_rule_views.xml
│   ├── fleet_vehicle_views.xml
│   ├── dashboard_views.xml         # spreadsheet_dashboard config, soft-dependency
│   └── menu_views.xml
├── data/
│   ├── vessel_pnl_cost_category_data.xml
│   ├── vessel_cost_allocation_rule_data.xml
│   ├── mail_template_data.xml
│   └── ir_cron_data.xml
├── security/
│   ├── vessel_voyage_pnl_groups.xml
│   └── ir.model.access.csv
├── report/
│   └── (opsional, PDF P&L statement per voyage, fase 2)
└── tests/
    ├── __init__.py
    ├── test_voyage_pnl_compute.py
    ├── test_cost_allocation.py
    ├── test_vessel_pnl_aggregation.py
    └── test_budget_variance.py
```

### 12.2 Urutan Kerja yang Disarankan (todo list untuk Claude Code)

1. **Skeleton modul** — `__manifest__.py` dengan depends `['fleet', 'mail', 'account', 'vessel_chartering', 'vessel_voyage_operations']` (+ soft-check `fleet_fuel_log`, `vessel_crew_management`, `fleet_maintenance_schedule`, `spreadsheet_dashboard` di kode, bukan di manifest depends)
2. **Master data**: `vessel.pnl.cost.category`, `vessel.cost.allocation.rule` + seed data XML `noupdate="1"` + security dasar
3. **Model inti agregasi**: `vessel.voyage.pnl` (§3.2) + `vessel.voyage.pnl.line` (§3.3) — implementasikan compute revenue dulu (paling sederhana, sumbernya jelas dari `vessel_chartering`), baru direct cost, baru allocated cost (paling kompleks) — tulis unit test bertahap sesuai urutan ini, jangan langsung semua compute sekaligus
4. **Logic alokasi**: implementasikan `_compute_allocated_cost` sebagai method terpisah yang membaca `vessel.cost.allocation.rule` aktif per kategori — desain method ini modular (satu function per `allocation_method`) supaya mudah tambah metode baru di fase 2
5. **Model agregasi bulanan**: `vessel.vessel.pnl` (§3.4) — perhatikan constraint unique per `(vessel_id, period_month, period_year)`, dan logic `idle_cost_allocated`
6. **Model budget**: `vessel.vessel.budget` + `.line` (§3.5-3.6)
7. **Extend model existing**: `fleet.vehicle`, `vessel.voyage` — pastikan `vessel_chartering` & `vessel_voyage_operations` sudah terinstall di environment dev
8. **Security & access**: groups, `ir.model.access.csv` (prefix wajib `vessel_voyage_pnl_`)
9. **Workflow**: tombol Generate/Recompute/Lock (§4.1), wizard adjustment manual (§4.1, locked state)
10. **Cron jobs** (§4.5) + mail templates (§4.6)
11. **Views & menu** (§5) — list/form/pivot dulu; dashboard `spreadsheet_dashboard` di paling akhir dan hanya jika modul tersedia di environment (cek `ir.module.module` sebelum load view yang depend padanya)
12. **Test end-to-end** mengikuti skenario Kriteria Penerimaan §10 satu per satu sebagai `TransactionCase` — siapkan fixture data test yang mencakup voyage lengkap dari `vessel_chartering` + `vessel_voyage_operations` (mock/create data minimal dari kedua modul tsb di `setUp`)
13. **Audit checklist final**:
    - `grep -rn "display_name" models/` → nihil sebagai field custom
    - `grep -rn "fields.Datetime.from_string" .` → nihil
    - `grep -rn "@api.depends()" models/` → tidak ada depends kosong
    - Cek `ir.model.access.csv` prefix `vessel_voyage_pnl_`
    - Cek xmlid menu valid, tidak bentrok
    - Install ulang dari nol (`-i vessel_voyage_pnl --test-enable`) di database yang sudah berisi 7 modul existing (5 fleet + chartering + voyage_operations)

### 12.3 Dependency & Prasyarat Environment

- `vessel_chartering` dan `vessel_voyage_operations` **harus** sudah terinstall dan punya minimal 1 voyage `completed` dengan data lengkap (freight invoice posted, laytime approved) untuk bisa test generate P&L end-to-end
- `fleet_fuel_log`, `vessel_crew_management`, `fleet_maintenance_schedule` bersifat soft dependency — cek via `ir.module.module` sebelum expose field/compute terkait; jika tidak ada, field terkait tetap ada di model tapi hanya bisa diisi lewat adjustment manual (`is_manual_adjustment=True`)
- `spreadsheet_dashboard` (Enterprise) — cek ketersediaan sebelum load `dashboard_views.xml`; siapkan fallback pivot/graph view standar Odoo sebagai default agar modul tetap fungsional tanpa Enterprise dashboard

### 12.4 Definisi "Selesai" untuk Modul Ini

Modul dianggap siap review jika: seluruh 11 poin Kriteria Penerimaan (§10) lulus sebagai automated test, checklist audit §12.2 poin 13 bersih, dan modul bisa diinstall di database yang sudah berisi 7 modul existing tanpa error maupun warning dependency melingkar. Tambahan khusus modul ini: skenario alokasi cost (poin 4 §10) harus punya minimal 3 test case dengan angka berbeda untuk membuktikan formula alokasi benar secara matematis, bukan hanya "tidak error".
