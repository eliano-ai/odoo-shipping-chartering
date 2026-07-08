# QA Status

**Last Check**: 2026-07-08 (audit 2026-07-03, update setelah `/qa write` isi 2 gap HIGH)
**Project**: Odoo Shipping Vertical Solution
**Metode**: `/qa audit` — cross-reference statis (grep), tidak menjalankan test/mengubah database

## Update 2026-07-08 — `/qa write`

2 gap HIGH dari audit 2026-07-03 sudah diisi dan diverifikasi (test individual + full suite modul terkait, 0 regresi):

1. **`test_05_action_approve_requires_manager_group`** ditambahkan ke `vessel_chartering/tests/test_laytime_calculation.py` — user tanpa `group_chartering_manager` dikonfirmasi ditolak `UserError` saat `action_approve()`. `vessel_chartering`: 12 → **13 test method, 13/13 pass**.
2. **`test_price_reference_uses_most_recent_before_date`** ditambahkan ke `vessel_bunker_management/tests/test_bunker_procurement.py` — dibuktikan dengan 2 baris `vessel.bunker.price.reference` (500 di H-60, 600 di H-10) bahwa `_compute_price_vs_market_pct()` benar-benar pakai baris TERDEKAT sebelum tanggal (`order='date desc', limit=1`), bukan baris pertama yang ditemukan. `vessel_bunker_management`: 19 → **20 test method, 20/20 pass**.

Belum dikerjakan (Prioritas MED/LOW, lihat Rekomendasi di bawah — masih valid, belum disentuh): `vessel.voyage.estimate`, `vessel.cost.allocation.rule`/`vessel.pnl.cost.category`, dan 5 modul Layer 1 tanpa `tests/` sama sekali.

## Update 2026-07-08 — `shopify_connector_v19` dihapus dari repo

Modul ini dihapus (tidak spesifik shipping, tidak pernah `installed` di database — cuma `uninstalled` di `ir_module_module`, aman dihapus tanpa cleanup DB). Semua baris/referensi ke modul ini di tabel bawah sudah tidak relevan lagi.

## Summary per Modul

| Modul | Model Files | Test Files | Test Methods | Model Tanpa Referensi Test* |
|-------|------------|-----------|---------------|-------------------------------|
| `fleet_document_id` | 4 | 0 | 0 | 3 (semua) |
| `fleet_fuel_log` | 4 | 0 | 0 | 3 (semua) |
| `fleet_maintenance_schedule` | 2 | 0 | 0 | 1 (semua) |
| `fleet_model_sparepart` | 3 | 0 | 0 | 1 (semua) |
| `vessel_crew_management` | 5 | 0 | 0 | 4 (semua) |
| `acc_id_multicurrency_report` | 7 | 2 | 24 | 2 |
| `maritime` | 0 (app container, tanpa model) | 0 | 0 | – |
| `vessel_chartering` | 13 | 4 | **13** (was 12) | 3 (lihat catatan false-positive di bawah) — guard `action_approve()` sudah teratasi |
| `vessel_voyage_operations` | 15 | 3 | 10 | 3 (lihat catatan false-positive di bawah) |
| `vessel_voyage_pnl` | 10 | 3 | 14 | 3 |
| `vessel_bunker_management` | 12 | 4 | **20** (was 19) | 2 false-positive — `vessel.bunker.price.reference` sudah teratasi |

\* Heuristik grep nama model literal di file test — lihat "Catatan Metodologi" di bawah untuk kenapa sebagian ini false-positive.

## Modul Tanpa Folder `tests/` Sama Sekali (gap pre-existing, BUKAN regresi)

`fleet_document_id`, `fleet_fuel_log`, `fleet_maintenance_schedule`, `fleet_model_sparepart`, `vessel_crew_management` — 5 dari 11 modul custom. Semua dikembangkan **sebelum** roadmap sprint terstruktur (Sprint 1+) dimulai, jadi tidak pernah masuk siklus "tulis test per sprint" yang berlaku sejak `vessel_chartering`. Ini backlog test debt pre-existing, bukan sesuatu yang rusak baru-baru ini.

`maritime` wajar tanpa test — app container murni tanpa model sendiri.

## Gap Nyata (dikonfirmasi manual, bukan cuma hasil grep otomatis)

1. **`vessel.bunker.price.reference`** (`vessel_bunker_management`) — tidak ada satupun test yang membuat/query model ini secara langsung. Dipakai secara TIDAK LANGSUNG lewat `_get_price_for_source()` (BOD/BOR) dan `_compute_price_vs_market_pct()` (quote), tapi logika intrinsiknya sendiri (mis. pengambilan harga referensi terbaru sebelum tanggal tertentu, `order='date desc', limit=1`) tidak pernah diuji langsung dengan lebih dari 1 baris data harga historis.
2. **`vessel.voyage.estimate`, `vessel.cargo.type`, `vessel.charter.terms`** (`vessel_chartering`) — genuinely tidak direferensikan sama sekali di test manapun (dicek manual by class name & field name, bukan cuma model string), termasuk `vessel.voyage.estimate` yang merupakan model inti Sprint 3 module ini.
3. **`vessel.cargo.document`, `vessel.clearance.document.type`, `vessel.port.clearance.line`** (`vessel_voyage_operations`) — sama, tidak ada referensi test sama sekali.
4. **`vessel.cost.allocation.rule`, `vessel.pnl.cost.category`, `vessel.voyage.pnl.line`** (`vessel_voyage_pnl`) — sama.
5. **`action_approve()` di `vessel.laytime.calculation`** (`vessel_chartering`) — di-guard `has_group('vessel_chartering.group_chartering_manager')`, tapi **tidak ada test `with_user()` yang memverifikasi user non-manager ditolak**. 4 test existing di `test_laytime_calculation.py` semuanya fokus ke logika interruption/demurrage, bukan security guard-nya. Ini satu-satunya kejadian pola "guard tanpa test" project ini yang berada di modul yang PUNYA test suite aktif (2 kejadian lain — `fleet_fuel_log`, `acc_id_multicurrency_report` — sudah tercakup di poin "tidak ada folder tests/ sama sekali").

## Acceptance Criteria §10 Tanpa Referensi Docstring Eksplisit

Konvensi menulis `"""§10.N acceptance criteria — ..."""` di docstring test baru konsisten dipakai **mulai `vessel_voyage_pnl` dan `vessel_bunker_management`** (modul ke-3 dan ke-4). Modul ke-1/ke-2 (`vessel_chartering`, `vessel_voyage_operations`) ditulis SEBELUM konvensi ini established, jadi banyak poin "tidak disebut" di bawah **bukan berarti tidak diuji** — skenarionya seringkali ADA test-nya, cuma docstring tidak mengutip nomor section tech spec secara eksplisit (diverifikasi manual untuk beberapa: `test_02_rejected_report_keeps_history` jelas menguji §10.6 `vessel_voyage_operations` — noon report rejected tetap simpan histori — meski tidak mengutip "§10.6" secara harfiah).

| Modul | Poin §10 Total | Ada Referensi Eksplisit | Catatan |
|-------|----------------|--------------------------|---------|
| `vessel_chartering` | 10 | 6/10 (§10.3-§10.8) | §10.1 (install), §10.9-10.10 (meta: unit test/audit) wajar tidak dikutip per-test; §10.2 perlu dicek manual |
| `vessel_voyage_operations` | 11 | 4/11 (§10.4,5,7 + parsial) | Ditulis sebelum konvensi §10.N ada — scenario §10.2/3/4/6/8 kemungkinan besar ADA test-nya tanpa kutipan literal (dikonfirmasi utk §10.4 & §10.6) |
| `vessel_voyage_pnl` | 11 | 7/11 | §10.1 (install), §10.6, §10.11 (meta) wajar tidak dikutip |
| `vessel_bunker_management` | 11 | 9/11 | Paling lengkap — hanya §10.1 (install, meta) dan §10.10/§10.11 (meta: unit test/audit) tidak dikutip, sesuai ekspektasi |

## Rekomendasi

**Prioritas HIGH** (business-critical, mudah diperbaiki):
1. Tambah test `with_user()` untuk `action_approve()` di `vessel.laytime.calculation` (`vessel_chartering`) — pola sudah established di 3 modul lain, tinggal direplikasi.
2. Tambah test langsung untuk `vessel.bunker.price.reference` — minimal 1 test yang membuktikan lookup "harga referensi terbaru sebelum tanggal X" benar dengan >1 baris data historis.

**Prioritas MED**:
3. Model inti tanpa test sama sekali: `vessel.voyage.estimate` (`vessel_chartering`), `vessel.cost.allocation.rule`/`vessel.pnl.cost.category` (`vessel_voyage_pnl`) — semuanya model dengan business logic (bukan cuma master data statis), layak diprioritaskan lebih dulu dari model master-data murni (`vessel.cargo.type`, `vessel.charter.terms`, `vessel.clearance.document.type`).

**Prioritas LOW / backlog jangka panjang**:
4. 5 modul Layer 1 tanpa test sama sekali (`fleet_document_id`, `fleet_fuel_log`, `fleet_maintenance_schedule`, `fleet_model_sparepart`, `vessel_crew_management`) — test debt pre-existing dari sebelum roadmap sprint dimulai. Realistis butuh sprint/inisiatif terpisah, bukan quick-fix `/qa write`.

Jalankan `/qa write` untuk mulai isi 2 gap HIGH di atas.

## Catatan Metodologi

Audit ini pakai heuristik grep nama model literal (`_name = 'xxx'` dicari sebagai substring di file test) untuk deteksi cepat model tanpa test. **Heuristik ini punya false-positive rate cukup tinggi** di modul yang test-nya reuse demo data via `self.env.ref('module.demo_xmlid')` (pola dominan di `vessel_bunker_management`) — 2 dari 3 item yang awalnya di-flag untuk modul itu (`vessel.bunker.inquiry`, `vessel.bunker.quote`) ternyata SUDAH diuji ekstensif di `test_bunker_procurement.py`, cuma diakses lewat record demo, bukan literal string nama model. Semua item di "Gap Nyata" di atas sudah diverifikasi manual (bukan cuma hasil grep mentah) sebelum dimasukkan daftar.
