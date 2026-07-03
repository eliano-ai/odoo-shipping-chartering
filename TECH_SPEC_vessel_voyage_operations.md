# Dokumen Teknis — Modul `vessel_voyage_operations`

**Proyek:** Odoo Shipping Vertical Solution — Layer 2 (Komersial)
**Target Platform:** Odoo 19.0 Enterprise
**Lisensi:** LGPL-3
**Penyusun:** Sunartha ERP Consulting
**Status Dokumen:** Draft v1.0 — untuk review sebelum development
**Tanggal:** Juli 2026
**Urutan roadmap:** #2 (setelah `vessel_chartering`, sebelum `vessel_voyage_pnl`)

---

## 1. Latar Belakang & Tujuan

Saat ini operasional kapal (posisi, status voyage, port call, noon report) dikelola manual via WhatsApp group & Excel. Kantor darat tidak punya satu sumber kebenaran mengenai posisi/status kapal, dan data noon report tidak terstruktur — padahal data ini menjadi basis perhitungan CII (MARPOL), rekonsiliasi bunker, dan analisa performa kapal.

Modul ini menjembatani **kontrak charter** (`vessel_chartering`) dengan **realita operasional harian di laut/pelabuhan**, dan menjadi sumber data utama untuk modul finansial berikutnya (`vessel_voyage_pnl`, `vessel_bunker_management`).

### 1.1 Ruang Lingkup (Scope)

| In Scope | Out of Scope (modul lain) |
|---|---|
| Voyage lifecycle (fixture → port rotation → sailing → completed) | Charter party & laytime/demurrage (`vessel_chartering`, sudah ada) |
| Port rotation multi-port dengan ETA/ETB/ETD vs ATA/ATB/ATD | Voyage P&L & costing lengkap (`vessel_voyage_pnl`) |
| Noon report / daily position report (posisi, ROB, cuaca) | Bunker procurement, BDN, survey (`vessel_bunker_management`) |
| Port call management: agen, PDA/FDA, clearance checklist | Perhitungan CII final & pelaporan resmi IMO DCS (fase 2, §7.2 brainstorm) |
| Cargo document tracking (B/L, manifest, mate's receipt) | ISM/HSE incident & audit (`vessel_hse_ism`) |
| Delay & event log per voyage | AIS live feed eksternal (opsional, fase lanjutan) |
| Dashboard operasional (posisi armada, status per kapal) | Payroll/crew — hanya referensi baca dari `vessel_crew_management` |
| Portal input untuk Nakhoda (noon report, SOF handoff) | Portal penuh multi-modul (§7.1 brainstorm — dibangun incremental, MVP di sini hanya noon report) |

### 1.2 Persona Pengguna

| Role | Kebutuhan Utama |
|---|---|
| **Nakhoda (Master)** — portal user | Input noon report harian, update ETA, lapor delay/event, input SOF sederhana |
| **Operations Staff (darat)** | Approve noon report, kelola port rotation, kelola PDA/FDA & agen, monitor posisi seluruh armada |
| **Chartering Manager** | Lihat link voyage ↔ kontrak charter, pastikan laytime di `vessel_chartering` konsisten dengan ATA/ATB/ATD |
| **Finance/Accounting** | Terima variance PDA vs FDA sebagai basis pencocokan biaya pelabuhan |
| **Direksi** | Dashboard posisi armada real-time, analisa delay per kategori |

---

## 2. Konsep Bisnis yang Dimodelkan

### 2.1 Voyage Lifecycle

```
draft → fixed → sailing → at_port → completed
                    ↑         ↓
                    └── (loop port rotation N kali) ──┘
                              ↓
                          cancelled
```

Satu **voyage** (`vessel.voyage`) merepresentasikan satu pelayaran fisik kapal dari port awal hingga redelivery/selesai cargo, dan **1-ke-1 atau 1-ke-banyak** terhadap `vessel.charter.contract` (satu voyage charter = satu voyage; satu time charter bisa punya banyak voyage berurutan).

### 2.2 Port Rotation Multi-Port

Realita: kapal batubara sering singgah >2 pelabuhan (misal load di 2 anchorage berbeda untuk mencukupi tonase). Setiap singgah dicatat sebagai `vessel.port.call` dengan urutan (`sequence`), rencana (ETA/ETB/ETD) vs aktual (ATA/ATB/ATD).

### 2.3 Noon Report / Daily Position Report

Input harian dari Nakhoda (idealnya sekali per 24 jam laut, jam standar 12:00 waktu kapal), berisi:
- Posisi (lat/long), course, speed (knots), distance run 24 jam, distance to go
- **ROB** (Remaining On Board): FO, DO, FW (fresh water), lube oil — inti data untuk rekonsiliasi bunker fase berikutnya
- Cuaca: wind force (Beaufort), sea state, kondisi umum
- RPM mesin, slip (%)
- Status: `noon_at_sea` / `noon_in_port` / `sof_event` (kejadian pelabuhan dicatat juga via noon report jika di port, agar timeline tidak putus)

Noon report adalah **sumber data utama CII (MARPOL)** — modul ini tidak menghitung CII (itu di §7.2 brainstorm, fase lanjutan), tapi memastikan data konsumsi & jarak tersimpan rapi agar modul CII tinggal agregasi.

### 2.4 Port Call Management

- **Agen pelabuhan** — reuse `res.partner` dengan flag `is_port_agent` (baru) — beda dari `is_port` (flag pelabuhan itu sendiri, sudah ada dari `vessel_chartering`)
- **PDA → FDA**: Proforma Disbursement Account (estimasi biaya sebelum kapal sandar) vs Final DA (tagihan aktual dari agen) → variance analysis per item biaya
- **Clearance in/out**: checklist dokumen (SPB/Port Clearance dari Syahbandar, imigrasi, karantina, bea cukai) — status per item, tanggal selesai
- **Cargo ops summary**: waktu commenced/completed loading-discharge, daily rate (MT/day) — dipakai lintas-cek dengan SOF di `vessel_chartering`

### 2.5 Cargo Document Tracking

B/L, manifest, mate's receipt, cargo damage report disimpan sebagai record dengan nomor & tanggal — jadi basis pemicu invoice freight final di `vessel_chartering` (field `bl_qty`/`bl_date` di kontrak akan diisi dari sini di fase integrasi, MVP: manual cross-reference).

### 2.6 Delay & Event Log

Setiap kejadian yang menghambat voyage (weather, port congestion, breakdown, waiting cargo, dll) dicatat dengan durasi & kategori — dasar analisa akar keterlambatan armada per kapal/per rute.

### 2.7 Prinsip Desain Konektivitas

Kapal punya konektivitas terbatas. Semua form input dari kapal (noon report, delay event) didesain:
- Field minimal wajib, sisanya opsional
- Bisa diisi telat/batch (misal 3 hari noon report sekaligus setelah sinyal kembali) — sistem tidak memvalidasi "harus hari ini"
- Draft tersimpan sisi klien dulu bila pakai portal (di luar scope teknis modul — dicatat sebagai asumsi UX, lihat §11)

---

## 3. Desain Data Model

### 3.1 Diagram Relasi (ringkas)

```
vessel.voyage (jantung modul)
 ├── charter_contract_id → vessel.charter.contract (vessel_chartering)
 ├── vessel_id → fleet.vehicle
 ├── fleet_trip_id → fleet.vehicle.trip (fleet_fuel_log) — lihat keputusan §8
 ├── port_call_ids → vessel.port.call (1..n, sequence)
 ├── noon_report_ids → vessel.noon.report (1..n)
 ├── cargo_document_ids → vessel.cargo.document (1..n)
 ├── delay_event_ids → vessel.voyage.delay (1..n)
 └── analytic_account_id → account.analytic.account (related dari charter_contract_id, plan Voyage)

vessel.port.call
 ├── voyage_id → vessel.voyage
 ├── port_id → res.partner (is_port=True, dari vessel_chartering)
 ├── agent_id → res.partner (is_port_agent=True, baru)
 ├── disbursement_ids → vessel.port.disbursement (PDA & FDA sebagai 2 record beda type)
 └── clearance_line_ids → vessel.port.clearance.line

Master data (baru):
 vessel.delay.type            (weather, port congestion, breakdown, waiting cargo, ...)
 vessel.clearance.document.type (SPB, imigrasi, karantina, bea cukai, ...)
 vessel.disbursement.item.type  (pilotage, towage, mooring, port dues, agency fee, ...)
```

### 3.2 Model: `vessel.voyage`

`_name = 'vessel.voyage'`
`_inherit = ['mail.thread', 'mail.activity.mixin']`
`_order = 'date_departure desc, id desc'`

| Field | Type | Keterangan |
|---|---|---|
| `name` | Char, readonly | Nomor via `ir.sequence` — format `VOY/2026/0001` |
| `charter_contract_id` | Many2one `vessel.charter.contract` | Required saat state ≥ `fixed`; domain state in (`confirmed`,`in_progress`) |
| `vessel_id` | Many2one `fleet.vehicle`, related dari kontrak, store | Domain `is_vessel=True` |
| `tug_id` | Many2one `fleet.vehicle` | Related dari kontrak jika pairing tug-barge |
| `analytic_account_id` | Many2one, related dari kontrak, store | Plan Voyage — 1 sumber kebenaran, tidak duplikasi |
| `fleet_trip_id` | Many2one `fleet.vehicle.trip` | Optional bridge ke `fleet_fuel_log` — lihat §8 keputusan |
| `date_departure` / `date_arrival_final` | Datetime | Aktual berangkat dari port awal / tiba redelivery-completed |
| `origin_port_id` / `final_port_id` | Many2one `res.partner` (`is_port=True`) | Ringkasan awal-akhir; detail per singgah di `port_call_ids` |
| `port_call_ids` | One2many `vessel.port.call` | |
| `noon_report_ids` | One2many `vessel.noon.report` | |
| `cargo_document_ids` | One2many `vessel.cargo.document` | |
| `delay_event_ids` | One2many `vessel.voyage.delay` | |
| `total_distance_nm` | Float, compute | Sum `distance_run_nm` dari noon report |
| `total_delay_hours` | Float, compute | Sum durasi delay event |
| `state` | Selection | `draft` / `fixed` / `sailing` / `at_port` / `completed` / `cancelled` |
| `company_id`, `user_id` | | Standar |

#### Constraint
- `_check_dates`: `date_arrival_final >= date_departure` jika keduanya terisi
- Satu `charter_contract_id` hanya boleh punya 1 voyage aktif (state not in completed/cancelled) kecuali time charter dengan multi-voyage berurutan (`contract_type='time'` boleh >1 voyage sekaligus tidak overlap tanggal)

### 3.3 Model: `vessel.port.call`

`_name = 'vessel.port.call'`
`_order = 'voyage_id, sequence, id'`

| Field | Type | Keterangan |
|---|---|---|
| `voyage_id` | Many2one, required, ondelete=cascade | |
| `sequence` | Integer | Urutan singgah |
| `port_id` | Many2one `res.partner` (`is_port=True`) | required |
| `call_purpose` | Selection | `load` / `discharge` / `bunkering` / `transit` / `layup` / `other` |
| `agent_id` | Many2one `res.partner` (`is_port_agent=True`) | |
| `eta` / `etb` / `etd` | Datetime | Estimasi — Estimated Time of Arrival/Berthing/Departure |
| `ata` / `atb` / `atd` | Datetime | Aktual |
| `berth_name` | Char | Nama dermaga/anchorage |
| `cargo_ops_commenced` / `cargo_ops_completed` | Datetime | |
| `cargo_ops_rate_mt_day` | Float, compute | Qty cargo (dari `cargo_document_ids` terkait) / durasi ops |
| `disbursement_ids` | One2many `vessel.port.disbursement` | |
| `clearance_line_ids` | One2many `vessel.port.clearance.line` | |
| `notes` | Html | |

Constraint: `etb >= eta`, `etd >= etb` (jika terisi); sama untuk kolom aktual (warning bukan blokir — data lapangan kadang tidak ideal).

### 3.4 Model: `vessel.noon.report`

`_name = 'vessel.noon.report'`
`_inherit = ['mail.thread']`
`_order = 'report_datetime desc'`

| Field | Type | Keterangan |
|---|---|---|
| `voyage_id` | Many2one, required, ondelete=cascade | |
| `report_datetime` | Datetime, required | Waktu laporan (biasanya jam 12:00 waktu kapal) |
| `report_type` | Selection | `noon_at_sea` / `noon_in_port` / `arrival` / `departure` / `sosp_eosp` (start/end of sea passage) |
| `latitude` / `longitude` | Float, digits=(10,6) | |
| `course_deg` | Float | 0-360 |
| `speed_knots` | Float | |
| `distance_run_nm` | Float | Jarak 24 jam terakhir |
| `distance_to_go_nm` | Float | |
| **ROB** | | |
| `rob_fo` / `rob_do` / `rob_fw` / `rob_lube_oil` | Float | MT / KL sesuai UoM master |
| **Cuaca & performa** | | |
| `wind_force_bft` | Integer | Skala Beaufort 0-12 |
| `sea_state` | Selection | Calm / Slight / Moderate / Rough / Very Rough |
| `rpm` | Float | |
| `slip_pct` | Float | |
| **Approval** | | |
| `state` | Selection | `draft` / `submitted` / `approved` / `rejected` |
| `approved_by` / `approved_date` | Many2one/Datetime | Operations staff |
| `rejection_reason` | Char | |
| `source` | Selection | `portal` / `manual` / `email_parsed` (placeholder fase 2, §7.1 brainstorm) |

Constraint: kombinasi `voyage_id` + `report_datetime` unik (cegah duplikasi input); `latitude` dalam -90..90, `longitude` dalam -180..180.

### 3.5 Model: `vessel.port.disbursement`

Merepresentasikan **satu set biaya pelabuhan** — dipakai 2x per port call: sekali sebagai PDA (estimasi), sekali sebagai FDA (final), dibedakan field `disbursement_type`.

`_name = 'vessel.port.disbursement'`

| Field | Type | Keterangan |
|---|---|---|
| `port_call_id` | Many2one, required, ondelete=cascade | |
| `disbursement_type` | Selection | `pda` / `fda` |
| `agent_id` | Many2one, related dari port_call, store | |
| `currency_id` | Many2one `res.currency` | Default USD atau IDR sesuai kebiasaan agen |
| `line_ids` | One2many `vessel.port.disbursement.line` | |
| `total_amount` | Monetary, compute | Sum line |
| `variance_amount` | Monetary, compute | Hanya terisi di record `fda`: `fda.total - pda.total` (dicari via `port_call_id` + type=pda) |
| `variance_pct` | Float, compute | |
| `state` | Selection | `draft` / `confirmed` |
| `document_ids` | Many2many `ir.attachment` | Upload scan PDA/FDA dari agen |

### 3.6 Model: `vessel.port.disbursement.line`

| Field | Type | Keterangan |
|---|---|---|
| `disbursement_id` | Many2one, required, ondelete=cascade | |
| `item_type_id` | Many2one `vessel.disbursement.item.type` | Pilotage, towage, mooring, port dues, agency fee, dll |
| `description` | Char | |
| `amount` | Monetary | |

### 3.7 Model: `vessel.port.clearance.line`

Checklist dokumen clearance in/out per port call.

| Field | Type | Keterangan |
|---|---|---|
| `port_call_id` | Many2one, required, ondelete=cascade | |
| `document_type_id` | Many2one `vessel.clearance.document.type` | SPB/Port Clearance, Imigrasi, Karantina, Bea Cukai |
| `direction` | Selection | `in` / `out` (clearance masuk vs keluar pelabuhan) |
| `status` | Selection | `pending` / `submitted` / `cleared` / `rejected` |
| `cleared_date` | Datetime | |
| `document_number` | Char | |
| `attachment_ids` | Many2many `ir.attachment` | |

### 3.8 Model: `vessel.cargo.document`

| Field | Type | Keterangan |
|---|---|---|
| `voyage_id` | Many2one, required, ondelete=cascade | |
| `port_call_id` | Many2one | Opsional, link ke port call spesifik (mis. B/L terbit di load port) |
| `document_type` | Selection | `bl` (Bill of Lading) / `manifest` / `mate_receipt` / `cargo_damage_report` / `other` |
| `document_number` | Char | |
| `document_date` | Date | |
| `qty_mt` | Float | Qty yang tercantum di dokumen — basis silang-cek `bl_qty` di `vessel.charter.contract` |
| `attachment_ids` | Many2many `ir.attachment` | |
| `notes` | Html | Untuk cargo damage report: detail kerusakan |

### 3.9 Model: `vessel.voyage.delay`

| Field | Type | Keterangan |
|---|---|---|
| `voyage_id` | Many2one, required, ondelete=cascade | |
| `port_call_id` | Many2one | Opsional — delay bisa terjadi di laut (bukan di port tertentu) |
| `delay_type_id` | Many2one `vessel.delay.type` | Weather, port congestion, breakdown, waiting cargo, dll |
| `datetime_start` / `datetime_end` | Datetime | |
| `duration_hours` | Float, compute, store | |
| `description` | Char | |
| `impacts_laytime` | Boolean | Flag informasional — cross-check manual terhadap SOF di `vessel_chartering` (MVP: tidak otomatis sinkron, lihat §8) |

### 3.10 Master data baru

**`vessel.delay.type`**: name (Weather, Port Congestion, Breakdown, Waiting Cargo, Waiting Berth, Waiting Instruction, Other), `active`. Seed via data XML `noupdate="1"`.

**`vessel.clearance.document.type`**: name (SPB/Port Clearance, Imigrasi, Karantina, Bea Cukai, Lainnya), `active`.

**`vessel.disbursement.item.type`**: name (Pilotage, Towage, Mooring/Unmooring, Port Dues, Light Dues, Agency Fee, Garbage Disposal, Lainnya), `active`.

### 3.11 Extend model existing

**`res.partner`**:
| Field | Keterangan |
|---|---|
| `is_port_agent` | Boolean — filter partner sebagai agen pelabuhan (beda dari `is_port` milik pelabuhan itu sendiri) |

**`fleet.vehicle`**:
| Field | Keterangan |
|---|---|
| `voyage_ids` | One2many `vessel.voyage` — riwayat voyage kapal |
| `current_voyage_id` | Many2one, compute — voyage state in (`sailing`,`at_port`) |
| `current_position_lat` / `current_position_lng` | Float, compute — dari noon report terakhir approved milik `current_voyage_id`, untuk dashboard peta |

**`vessel.charter.contract`** (dari `vessel_chartering`):
| Field | Keterangan |
|---|---|
| `voyage_ids` | One2many `vessel.voyage`, inverse dari `charter_contract_id` |
| `voyage_count` | Integer, compute — smart button |

---

## 4. Workflow & Business Logic

### 4.1 State Machine `vessel.voyage`

```
draft → fixed → sailing → at_port → completed
                    ↑         ↓
                    └─────────┘ (loop N port call)
                          ↓
                      cancelled
```

| Transisi | Tombol | Logic |
|---|---|---|
| draft → fixed | "Fixed dari Kontrak" | Wajib pilih `charter_contract_id` (state confirmed+); auto-copy `vessel_id`, `analytic_account_id` |
| fixed → sailing | "Berangkat" | Isi `date_departure` & `origin_port_id`; boleh manual atau otomatis saat noon report pertama `report_type=departure` diapprove |
| sailing ↔ at_port | "Tiba di Port" / "Berangkat dari Port" | Toggle berdasarkan `atb`/`atd` di `port_call_id` aktif |
| at_port/sailing → completed | "Selesaikan Voyage" | Validasi: semua `port_call_ids` punya `atd` terisi (kecuali port terakhir tujuan final cukup `atb`), minimal 1 cargo document ber-tipe `bl` jika voyage charter |
| → cancelled | "Batalkan" | Wajib alasan (wizard); hanya dari draft/fixed |

### 4.2 Noon Report Approval Workflow

`draft` (Nakhoda submit) → `submitted` → Operations review → `approved` / `rejected` (wajib isi `rejection_reason`, Nakhoda bisa re-submit sebagai record baru — noon report yang sudah approved/rejected **read-only**, tidak diedit, demi audit trail).

Validasi saat approve:
- Warning (bukan blokir) jika gap dengan noon report approved sebelumnya > 30 jam (indikasi ada laporan terlewat)
- Warning jika `rob_fo`/`rob_do` naik dari laporan sebelumnya tanpa event bunkering tercatat di `port_call_ids` (bunkering) — sinyal awal untuk `vessel_bunker_management` fase depan, MVP cukup warning non-blokir

### 4.3 Port Call & Clearance

Saat `vessel.port.call` dibuat dengan `call_purpose` terisi, sistem auto-generate baris `clearance_line_ids` dari template `vessel.clearance.document.type` yang di-flag `default_required=True` (field tambahan di master), direction `in` dan `out` masing-masing. Operations tinggal update status per baris.

### 4.4 PDA → FDA Variance

- PDA dibuat manual (estimasi awal dari agen) sebelum/saat kapal sandar
- FDA dibuat setelah kapal berangkat (tagihan final dari agen)
- Saat FDA `state=confirmed`, compute `variance_amount` = FDA total − PDA total (by `port_call_id`)
- Variance > threshold (config, default 15%) → activity ke Chartering Manager & Finance untuk review

### 4.5 Cron Jobs

| Cron | Frekuensi | Fungsi |
|---|---|---|
| `_cron_noon_report_missing_alert` | Harian | Voyage state `sailing`/`at_port` tanpa noon report approved dalam 30 jam terakhir → activity ke Operations |
| `_cron_eta_reminder` | Harian | Port call dengan `eta` H-2/H-0 tanpa `ata` terisi → activity ke Operations + notifikasi agen (opsional email) |
| `_cron_clearance_pending_alert` | Harian | `clearance_line_ids` status `pending`/`submitted` > 2 hari sejak `atb` → activity ke Operations |
| `_cron_disbursement_variance_review` | Mingguan | FDA confirmed dengan variance belum direview (field `reviewed` Boolean) → reminder ke Finance |

### 4.6 Notifikasi

Email template: voyage fixed (internal), ETA reminder ke agen, noon report rejected (ke Nakhoda via portal), variance PDA/FDA tinggi (ke Finance & Chartering Manager). Mengikuti pola `mail.thread` modul existing.

---

## 5. Views & Menu

**Menu:** Fleet → **Voyage Operations** *(sejajar Chartering, Dokumen Legal, Fuel)*

```
Voyage Operations
├── Voyages
│   ├── Semua Voyage           (list, form, kanban by state, map view custom)
│   ├── Sedang Berlayar        (filter state in sailing, at_port)
│   └── Selesai                (filter state=completed)
├── Operasional
│   ├── Noon Reports           (list, form; filter Pending Approval untuk Operations)
│   ├── Port Calls             (list, calendar by eta)
│   └── Cargo Documents        (list)
├── Finansial Pendukung
│   ├── Disbursement (PDA/FDA) (list, filter by type)
│   └── Variance Report        (pivot: port call × PDA vs FDA)
├── Laporan
│   ├── Delay Analysis         (pivot/graph: delay type × kapal × durasi)
│   └── Dashboard Posisi Armada (peta OWL/leaflet — custom widget)
└── Konfigurasi (Manager only)
    ├── Tipe Delay
    ├── Tipe Dokumen Clearance
    └── Tipe Item Disbursement
```

**Form voyage** — notebook: Info Utama / Port Rotation (list inline `port_call_ids`) / Noon Reports (smart button + list) / Cargo Documents / Delay Log. Statusbar dengan tombol aksi. Smart buttons: Port Calls, Noon Reports, Cargo Documents, Delays, ke Kontrak Charter.

**Form noon report** — layout ringkas 1 halaman: header (voyage, datetime, type), section Posisi & Kecepatan, section ROB, section Cuaca & Performa. Read-only total setelah approved.

**Dashboard posisi armada** — custom OWL component, marker per kapal dari `current_position_lat/lng` di `fleet.vehicle`, warna marker sesuai `charter_status`.

---

## 6. Security

| Group | Hak |
|---|---|
| `group_voyage_ops_portal` (Nakhoda, portal user) | Create/write noon report milik voyage yang ditugaskan (record rule via `vessel.crew.assignment` aktif), read voyage & port call miliknya, tidak bisa approve, tidak lihat disbursement |
| `group_voyage_ops_user` (Operations) | RWC voyage, port call, cargo document, delay; approve/reject noon report; RWC disbursement & clearance (no unlink disbursement confirmed) |
| `group_voyage_ops_manager` | Full + konfigurasi master + override state voyage |
| Finance (`account.group_account_invoice`) | Read voyage & disbursement, tidak bisa ubah |

`ir.model.access.csv` — prefix modul `vessel_voyage_operations_*` pada semua xmlid group (checklist audit). Record rule portal: `[('voyage_id.vessel_id', 'in', user_assigned_vessel_ids)]` — dihitung dari `vessel.crew.assignment` state=`on_board` milik user terkait (butuh field link `user_id` di `vessel.seafarer`, cek dulu apakah sudah ada di `vessel_crew_management`; jika belum, tambahkan sebagai dependency ringan/soft check).

---

## 7. Integrasi Antar Modul

| Modul | Integrasi |
|---|---|
| `vessel_chartering` | `charter_contract_id` di voyage; `voyage_ids`/`voyage_count` extend di kontrak; port master (`is_port`) & `res.partner` di-reuse langsung (dependency **wajib**, beda dari fuel log yang soft) |
| `fleet_fuel_log` | `fleet_trip_id` opsional di voyage — jika modul `fleet_fuel_log` terinstall, tombol "Link ke Trip" muncul; jika tidak, field tersembunyi (dependency **soft**, cek `ir.module.module`, konsisten pola bridge di `vessel_chartering` §8) |
| `vessel_crew_management` | Record rule portal Nakhoda memakai `vessel.crew.assignment`; smart info manning tidak diubah — hanya baca |
| `fleet_document_id` | Tidak ada integrasi langsung di MVP; port clearance adalah dokumen pelabuhan (bukan dokumen kapal), model terpisah secara sengaja (lihat §8) |
| `mail`, `portal` | Chatter + akses portal Nakhoda |

---

## 8. Keputusan Desain & Alternatif yang Ditolak

| Keputusan | Alternatif ditolak | Alasan |
|---|---|---|
| `vessel.voyage` sebagai model baru, `fleet_trip_id` hanya bridge opsional | Extend `fleet.vehicle.trip` langsung jadi model voyage | `fleet.vehicle.trip` didesain untuk agregasi fuel log sederhana (planned/ongoing/done); voyage butuh state machine & relasi jauh lebih kaya (port rotation, noon report, cargo doc). Extend akan memaksa `fleet_fuel_log` naik kompleksitas di luar tanggung jawabnya. Opsi paralel (Option B, sesuai preseden disebut di brainstorm) dipilih: dua model hidup berdampingan, dihubungkan via `fleet_trip_id`, migrasi/deprecate diputuskan di fase 2 setelah lihat adopsi nyata |
| Dependency ke `vessel_chartering`: **wajib (hard dependency)** | Soft dependency seperti pola fuel log | Voyage tanpa kontrak charter tidak bermakna bisnis di solusi ini — voyage *selalu* berasal dari fixture; beda kasus dengan fuel log yang bisa dipakai kapal non-charter (mis. kapal milik sendiri untuk logistik internal) |
| Port clearance sebagai model terpisah (`vessel.port.clearance.line`), bukan reuse `fleet.vehicle.document` | Reuse dokumen legal kapal | Clearance adalah **dokumen transaksional per port call** (SPB baru tiap singgah), bukan sertifikat kapal jangka panjang (BKI, STCW) yang punya expiry — sifat siklus hidup beda total, memaksakan reuse akan mengotori model `fleet.vehicle.document` |
| PDA & FDA sebagai 1 model (`vessel.port.disbursement`) dibedakan field `disbursement_type` | Dua model terpisah `vessel.pda` & `vessel.fda` | Struktur line item identik; variance compute lebih mudah 1 model dengan query silang berdasarkan `port_call_id` + type — pola konsisten dengan keputusan direction di `vessel_chartering` |
| Noon report immutable setelah approved/rejected (re-submit = record baru) | Edit in-place dengan versioning field | Audit trail CII/MARPOL butuh histori utuh tanpa risiko data diubah setelah jadi basis laporan resmi |
| Delay log tidak otomatis sinkron ke SOF laytime (`vessel_chartering`) | Auto-create SOF line dari delay event | Delay operasional (breakdown mesin di laut) tidak selalu identik dengan interupsi laytime (yang spesifik di pelabuhan selama loading/discharge); auto-sync berisiko salah kaprah — MVP: cross-reference manual, evaluasi otomasi di fase 2 setelah pola pemakaian jelas |
| Dashboard posisi armada: custom OWL/leaflet ringan, bukan integrasi AIS live | Integrasi AIS provider (MarineTraffic dll) langsung di MVP | AIS API berbayar & per-klien (§7.4 brainstorm — opsional per klien); MVP cukup plot dari noon report (update tiap 24 jam) sudah jauh lebih baik dari status quo (WhatsApp) |

---

## 9. Rencana Fase & Estimasi Kompleksitas

| Fase | Deliverable | Kompleksitas |
|---|---|---|
| **MVP (fase ini)** | Model lengkap §3, workflow §4.1-§4.4, noon report + approval, port call + clearance checklist, PDA/FDA + variance, cargo document, delay log, dashboard posisi dasar, menu & views, security incl. portal Nakhoda, cron §4.5 | Tinggi — model relasional banyak, portal security jadi titik kritis |
| Fase 2 | Auto-sinkron delay ke SOF laytime (opsional/config), email-parsed noon report (fallback WA/email terstruktur sesuai §7.1 brainstorm), kalkulasi CII dasar dari data yang sudah tersimpan (§7.2 brainstorm — modul bisa jadi standalone `vessel_cii` atau extend di sini) | Sedang-Tinggi |
| Fase 3 | Integrasi AIS live feed (opsional per klien), weather routing provider, auto-trigger `bl_qty` di kontrak dari cargo document | Sedang |

---

## 10. Kriteria Penerimaan (Acceptance Criteria) MVP

1. Install bersih di Odoo 19 Enterprise tanpa error, tanpa konflik dengan `vessel_chartering` & 5 modul fleet existing
2. Buat voyage dari kontrak charter confirmed → `vessel_id` & `analytic_account_id` ter-copy otomatis
3. Tambah 3 port call berurutan (sequence 1-3) dengan ETA/ATA berbeda → tidak error, urutan tampil benar di list & form
4. Nakhoda (portal user, punya assignment aktif) submit noon report → hanya bisa lihat voyage kapalnya sendiri, tidak bisa lihat voyage kapal lain
5. Operations approve noon report → record menjadi read-only, muncul di compute `total_distance_nm` voyage
6. Noon report rejected → Nakhoda bisa buat record baru, record lama tetap tersimpan sebagai histori (tidak terhapus)
7. Buat PDA dengan 5 line item, lalu FDA dengan total lebih tinggi 20% → `variance_amount` & `variance_pct` terhitung benar, activity terkirim ke Finance (karena >15% threshold default)
8. Selesaikan voyage tanpa `atd` di salah satu port call → sistem block dengan pesan error jelas (constraint validasi §4.1)
9. Dashboard posisi armada menampilkan kapal dengan `current_position_lat/lng` sesuai noon report approved terakhir
10. Semua unit test `TransactionCase` untuk compute (`total_distance_nm`, `variance_amount`, `duration_hours`) lulus
11. Tidak ada penggunaan `display_name` sebagai field custom, `fields.Datetime.from_string`, atau `@api.depends()` kosong (checklist audit Odoo 19 — sama seperti modul lain)

---

## 11. Pertanyaan Terbuka (perlu keputusan sebelum coding)

1. **Frekuensi noon report** — selalu 24 jam sekali, atau perlu opsi 2x/hari untuk voyage pendek tug-barge domestik? Berpengaruh ke validasi gap 30 jam di §4.2.
2. **Record rule portal Nakhoda** — apakah `vessel_crew_management` sudah punya field `user_id` di `vessel.seafarer` yang terhubung ke `res.users`? Perlu konfirmasi sebelum desain final record rule §6.
3. **Threshold variance PDA/FDA** (default 15%) — apakah perlu configurable per klien/per pelabuhan, atau cukup satu setting global di `res.config.settings`?
4. **Sumber pertama CII** — apakah tim ingin MVP modul ini sudah expose data noon report dalam format siap-pakai (view/report) untuk perhitungan CII manual di Excel, sebelum modul CII resmi dibangun di fase 2?
5. **Offline-first portal** (§2.7) — perlu PWA dengan local storage & sync, atau cukup form web sederhana dengan asumsi Nakhoda re-attempt manual saat sinyal ada? Ini keputusan produk, bukan hanya data model, dan berpengaruh besar ke effort development portal.

---

## 12. Panduan Eksekusi Development (untuk Claude Code)

Bagian ini bukan bagian dari spesifikasi fungsional, tapi panduan praktis menjalankan pembangunan modul ini secara bertahap menggunakan Claude Code, berdasarkan checklist audit Odoo 19 yang sudah berlaku untuk modul lain di repo `odoo-shipping` (lihat §10 brainstorm & §10 tech spec `vessel_chartering`).

### 12.1 Struktur Direktori Modul (Odoo standar)

```
vessel_voyage_operations/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── vessel_voyage.py
│   ├── vessel_port_call.py
│   ├── vessel_noon_report.py
│   ├── vessel_port_disbursement.py
│   ├── vessel_port_clearance_line.py
│   ├── vessel_cargo_document.py
│   ├── vessel_voyage_delay.py
│   ├── vessel_delay_type.py
│   ├── vessel_clearance_document_type.py
│   ├── vessel_disbursement_item_type.py
│   ├── res_partner.py          # extend is_port_agent
│   └── fleet_vehicle.py        # extend voyage_ids, current_voyage_id, dsb.
├── wizards/
│   └── __init__.py             # (jika ada wizard sign-off/cancel — cek kebutuhan saat implementasi)
├── views/
│   ├── vessel_voyage_views.xml
│   ├── vessel_port_call_views.xml
│   ├── vessel_noon_report_views.xml
│   ├── vessel_port_disbursement_views.xml
│   ├── vessel_cargo_document_views.xml
│   ├── vessel_voyage_delay_views.xml
│   ├── res_partner_views.xml
│   ├── fleet_vehicle_views.xml
│   ├── dashboard_views.xml      # OWL component posisi armada
│   └── menu_views.xml
├── data/
│   ├── ir_sequence_data.xml
│   ├── vessel_delay_type_data.xml
│   ├── vessel_clearance_document_type_data.xml
│   ├── vessel_disbursement_item_type_data.xml
│   ├── mail_template_data.xml
│   └── ir_cron_data.xml
├── security/
│   ├── vessel_voyage_operations_groups.xml
│   ├── ir.model.access.csv
│   └── vessel_voyage_operations_security.xml   # record rules portal
├── static/
│   └── src/
│       ├── js/dashboard_map.js        # OWL component
│       ├── xml/dashboard_map.xml
│       └── scss/dashboard_map.scss
├── report/
│   └── (opsional, laporan PDF fase 2)
└── tests/
    ├── __init__.py
    ├── test_vessel_voyage.py
    ├── test_noon_report.py
    └── test_port_disbursement.py
```

### 12.2 Urutan Kerja yang Disarankan (todo list untuk Claude Code)

Jalankan sebagai langkah bertahap, commit per langkah, jangan lompat ke views sebelum model & security dasar solid:

1. **Skeleton modul** — `__manifest__.py` dengan depends `['fleet', 'mail', 'portal', 'vessel_chartering']` (+ soft-check `fleet_fuel_log` di kode, bukan di depends manifest), `__init__.py` kosong dulu
2. **Master data models** — `vessel.delay.type`, `vessel.clearance.document.type`, `vessel.disbursement.item.type` + seed data XML `noupdate="1"` + security dasar
3. **Model inti tanpa relasi ke UI dulu**: `vessel.voyage` (§3.2) → `vessel.port.call` (§3.3) → `vessel.noon.report` (§3.4) — implementasikan compute fields & constraint, tulis unit test **sebelum** lanjut ke model berikutnya
4. **Model finansial pendukung**: `vessel.port.disbursement` + `.line` (§3.5-3.6), `vessel.port.clearance.line` (§3.7) — termasuk logic variance compute
5. **Model pendukung sisa**: `vessel.cargo.document` (§3.8), `vessel.voyage.delay` (§3.9)
6. **Extend model existing**: `res.partner` (`is_port_agent`), `fleet.vehicle` (voyage fields), `vessel.charter.contract` (voyage_ids) — pastikan `vessel_chartering` sudah ter-install di environment dev sebelum langkah ini
7. **Security & access**: groups, `ir.model.access.csv` (prefix wajib), record rule portal Nakhoda — verifikasi dulu poin terbuka §11.2 (field `user_id` di `vessel.seafarer`)
8. **Workflow & state machine**: tombol aksi di model (§4.1-§4.4), validasi transisi state, jangan taruh logic di view/XML
9. **Cron jobs** (§4.5) + mail templates (§4.6)
10. **Views & menu** (§5) — list/form/kanban dulu, dashboard OWL peta (§5, custom widget) di paling akhir karena paling kompleks & tidak blocking modul lain
11. **Test end-to-end** mengikuti skenario Kriteria Penerimaan §10 satu per satu sebagai `TransactionCase`
12. **Audit checklist final** sebelum dianggap selesai — jalankan grep manual:
    - `grep -rn "display_name" models/` → pastikan tidak dipakai sebagai field custom
    - `grep -rn "fields.Datetime.from_string" .` → harus nihil
    - `grep -rn "@api.depends()" models/` → tidak boleh ada depends kosong
    - Cek setiap baris `ir.model.access.csv` memakai prefix `vessel_voyage_operations_`
    - Cek semua `<menuitem>` xmlid valid & tidak bentrok modul lain
    - Install ulang dari nol di database bersih (`-i vessel_voyage_operations --test-enable`) untuk memastikan zero-install-error

### 12.3 Dependency & Prasyarat Environment

- Modul `vessel_chartering` **harus** sudah terinstall (hard dependency, §8) — jika Claude Code menjalankan development di database yang belum punya modul ini, install dulu sebelum lanjut
- Modul `vessel_crew_management` disebut sebagai dependency ringan untuk record rule portal (§6, §11.2) — jika belum tersedia/dicommit di repo, implementasikan record rule dengan **placeholder** (`domain=[('voyage_id.vessel_id', 'in', [])]` + TODO comment) agar modul tetap bisa diinstall standalone, dan tandai eksplisit di PR/commit message bahwa ini menunggu integrasi
- `fleet_fuel_log` bersifat soft dependency — cek keberadaan modul via `self.env['ir.module.module'].search([('name','=','fleet_fuel_log'),('state','=','installed')])` sebelum expose field/tombol terkait `fleet_trip_id`, jangan taruh di `depends` manifest

### 12.4 Definisi "Selesai" untuk Modul Ini

Modul dianggap siap review jika: seluruh 11 poin Kriteria Penerimaan (§10) lulus sebagai automated test, checklist audit §12.2 poin 12 bersih, dan modul bisa diinstall di database yang sudah berisi 6 modul existing (5 fleet modules + `vessel_chartering`) tanpa error maupun warning dependency melingkar.
