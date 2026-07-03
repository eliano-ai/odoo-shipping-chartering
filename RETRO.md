# Retro Log
<!-- Dikelola otomatis oleh Retro Agent. Entry baru ditambahkan di atas. -->

---

## 2026-07-03 — Retrospektif Sprint 15–28 (MVP `vessel_voyage_pnl` + `vessel_bunker_management` complete)

**Project**: Odoo Shipping Vertical Solution — modul `vessel_voyage_pnl` (Sprint 15-21) DAN `vessel_bunker_management` (Sprint 22-28)
**Scope**: Sprint 15 sampai Sprint 28 (14 sprint, roadmap Layer 3 Finansial #3 dan #4)
**Reviewed**: 2026-07-03
**Reviewed by**: Claude Code Retro Agent

**Catatan penting soal scope**: retro ini seharusnya dijalankan 2x terpisah (setelah Sprint 21 dan setelah Sprint 28), tapi retro untuk Sprint 15-21 **ternyata terlewat** — `learning_log.json` berhenti di Sprint 14 dan `RETRO.md` tidak punya entry Sprint 15-21 sebelum retro ini dijalankan (`sprint_27.md` bahkan sempat mereferensikan "pelajaran retro vessel_voyage_pnl Sprint 15-21" yang sebenarnya tidak pernah ada sebagai retro tertulis — kemungkinan tercampur dengan narasi `SPRINT_REPORT.md`, bukan retro artifact sungguhan). Retro ini menggabungkan kedua cakupan sekaligus untuk menutup gap tersebut. **Lihat Gap #0 di bawah untuk analisis kenapa ini bisa terlewat dan cara mencegahnya.**

### 📊 Ringkasan Kuantitatif

| Metric | Nilai |
|--------|-------|
| Sprint dianalisis | 14 (Sprint 15-21 `vessel_voyage_pnl`, Sprint 22-28 `vessel_bunker_management`) |
| Total tasks (approx, dari checklist "Task Selesai" tiap entry SPRINT_REPORT.md) | ~112 |
| Fix/revert commits | 0 (grep word-boundary bersih di seluruh git log) |
| Unique blocker entries | 24 mention di SPRINT_REPORT.md, 4 kategori adalah pola berulang (≥2 kejadian) |
| Recurring blockers baru ditambahkan ke learning_log.json | 7 kategori baru |
| Skill gap terdeteksi | 1 gap proses besar (retro yang terlewat) + 3 gap command coverage |

### 🔁 Pola Blocker Sistemik

#### 0. Retro siklus modul (`vessel_voyage_pnl` Sprint 15-21) tidak pernah benar-benar dijalankan
- **Severity**: HIGH (meta-level, bukan bug kode — tapi merusak keandalan proses pembelajaran)
- **Kejadian konkret**: Sprint 21's closing note (`sprint_21.md`) mengarahkan untuk "jalankan `/retro` setelah selesai", dan `SPRINT_REPORT.md` mencatat MVP selesai — tapi baik `RETRO.md` maupun `learning_log.json` tidak pernah mendapat entry untuk Sprint 15-21. `sprint_27.md` (ditulis untuk `vessel_bunker_management`) bahkan mereferensikan "pelajaran retro vessel_voyage_pnl Sprint 15-21" seolah-olah retro itu ada — kemungkinan besar penulis sprint breakdown (diri sendiri, sesi sebelumnya) mengasumsikan retro akan/sudah dijalankan karena polanya konsisten di modul 1 & 2, tapi tidak benar-benar memverifikasi file `RETRO.md` sebelum menulis referensi itu.
- **Root cause**: instruksi "jalankan /retro setelah MVP selesai" ada di catatan sprint (`sprint_21.md`), tapi tidak ada ENFORCEMENT — kalau sesi berikutnya langsung lanjut ke tech spec modul baru tanpa retro (yang persis terjadi: user minta lanjut ke `vessel_bunker_management` segera setelah `vessel_voyage_pnl` selesai), retro bisa terlewat tanpa ada yang notice, karena tidak ada gate/checklist yang secara eksplisit MEWAJIBKAN cek "apakah RETRO.md sudah punya entry untuk siklus yang baru selesai" sebelum mulai sprint breakdown modul berikutnya.
- **Skill yang perlu diupdate**: `sprint.md` (bagian penutup MVP) dan/atau proses breakdown sprint modul baru
- **Saran perbaikan**: tambah pre-flight check di awal proses "buat sprint breakdown modul baru" — cek apakah `RETRO.md` sudah punya entry untuk modul yang BARU SAJA selesai (grep nama modul sebelumnya di `RETRO.md`); kalau belum, jalankan retro dulu SEBELUM lanjut menulis sprint breakdown modul baru. Ini mencegah retro "keburu terlewat" karena momentum autonomous mode yang langsung lanjut ke modul berikutnya tanpa jeda alami untuk retro.

#### 1. `has_group()` gagal di context demo-data/install (`env.user` = `__system__`, bukan `base.user_admin`) — 3 kejadian lintas 2 modul
- **Severity**: HIGH
- **Kejadian konkret**:
  1. `vessel_voyage_pnl` Sprint 17: action method guard `has_group()` gagal dipanggil dari demo setup.
  2. `vessel_bunker_management` Sprint 24: `action_resolve_dispute()` sama persis.
  3. `vessel_bunker_management` Sprint 26: `action_settle()` sama persis lagi.
- **Root cause**: user yang menjalankan `-i`/`-u` (termasuk saat load demo data) adalah superuser/`__system__` (uid=1), yang TIDAK otomatis member semua grup kecuali eksplisit ditambahkan (`base.user_admin` di-assign eksplisit ke `group_bunker_manager` dkk, tapi `__system__` sendiri tidak). Pola fix-nya sudah konsisten dan cepat ditemukan tiap kali (demo tulis field target langsung, bukan panggil action method yang guarded), TAPI selalu ditemukan REAKTIF (kena `UserError` dulu), bukan proaktif dicegah dari awal penulisan demo code.
- **Skill yang perlu diupdate**: `sprint.md` (Pre-flight Check) dan/atau `CLAUDE.md` Konvensi Kode
- **Saran perbaikan**: tambah catatan eksplisit di `CLAUDE.md` (dan pre-flight `sprint.md`): "kalau demo/dummy data perlu memanggil action method yang guard `has_group()`, JANGAN panggil method itu langsung — tulis field/state target secara langsung via `write()`/assignment, method asli tetap simpan guard-nya (diuji lewat `with_user()` di unit test)". Ini sudah jadi tacit knowledge (3x diterapkan benar), tinggal dituliskan eksplisit supaya modul ke-5 tidak menemukan ulang dari nol.

#### 2. Odoo 19 API/behavior baru ditemukan reaktif — 2 pola baru (beda dari retro sebelumnya)
- **Severity**: HIGH
- **Kejadian konkret**:
  1. `vessel_bunker_management` Sprint 23: `<function>` tag di dalam `<odoo noupdate="1">` tidak pernah re-run tiap `-u` — noupdate menekan `<function>` juga, bukan cuma `<record>` (asumsi awal salah).
  2. `vessel_bunker_management` Sprint 24: `<record>` XML re-declare field milik module LAIN yang xmlid-nya noupdate-protected oleh module ASAL — di-skip diam-diam (noupdate yang berlaku adalah punya module asal, bukan file sendiri).
  3. `vessel_bunker_management` Sprint 24: `stock.move.name` dihapus di Odoo 19 (`description_picking` sebagai gantinya) — sekaligus menyingkap bug laten IDENTIK di `fleet_fuel_log._create_stock_move()` (pre-existing, luput karena guard `product_id` kosong selalu kena duluan).
- **Root cause**: sama seperti pola di retro sebelumnya — pengetahuan Odoo API dari versi lama/asumsi umum XML `noupdate` semantics ternyata tidak selengkap perilaku aktual Odoo 19.
- **Skill yang perlu diupdate**: sudah masuk ke `CLAUDE.md` Checklist Odoo 19 Gotcha (3 baris baru) — **tapi belum disinkronkan ke pre-flight grep list `sprint.md`** (gap yang SAMA seperti yang diidentifikasi retro Sprint 8-14, poin ini ternyata TERULANG: dokumentasi bertambah tapi grep executable tidak ikut diperbarui secara rutin).
- **Saran perbaikan**: sinkronkan 3 gotcha baru ini ke grep list `sprint.md` Pre-flight — dan pertimbangkan proses yang lebih tegas: setiap kali baris baru masuk CLAUDE.md Gotcha table, item itu dianggap "belum selesai" sampai baris grep yang sesuai juga ditambahkan ke `sprint.md` di commit yang sama (bukan cuma rekomendasi, tapi bagian dari Definition of Done sprint yang menambah gotcha itu).

#### 3. Stored compute field yang depend pada `search()` lintas model tidak auto-recompute saat data sumber berubah belakangan — 2 kejadian
- **Severity**: MED
- **Kejadian konkret**: `vessel_bunker_management` Sprint 25 dan Sprint 26, keduanya: fix bug data source lalu record yang SUDAH dibuat sebelumnya masih membawa nilai lama (basi) karena `@api.depends` tidak bisa bereaksi ke hasil `search()` dinamis.
- **Root cause**: keterbatasan arsitektural ORM Odoo (bukan bug), sudah diketahui sejak `vessel_voyage_pnl` juga tapi belum pernah ditulis sebagai "known limitation" yang eksplisit di `CLAUDE.md`.
- **Skill yang perlu diupdate**: `CLAUDE.md` Konvensi Kode
- **Saran perbaikan**: tulis eksplisit sebagai catatan permanen — "compute field yang depend ke hasil `search()` cross-model TIDAK auto-recompute kalau data sumbernya berubah setelah record dibuat; kalau demo data perlu di-fix ulang, `unlink()` record lama lalu `-u` ulang, jangan mengandalkan auto-recompute".

#### 4. Test regresi berulang akibat demo data lifecycle terus berkembang antar sprint — 3 kejadian
- **Severity**: MED
- **Kejadian konkret**: `vessel_bunker_management` Sprint 24 (2x: `assertRaises` tuple-form tidak didukung Odoo test framework, dan hardcode `state == 'nominated'` break setelah demo lanjut ke `delivered`), Sprint 26 (test baru pakai `period_start` yang collide dengan punya demo, sempat disangka error `ir_cron` lock transient duluan).
- **Root cause**: demo data yang terus di-extend antar sprint dalam modul yang sama membuat asumsi test lama (state persis, tanggal persis) menjadi stale, tapi test itu tidak selalu di-rerun ulang setelah demo data berubah pada sprint yang SAMA.
- **Skill yang perlu diupdate**: `sprint.md` Langkah 8 (Jalankan Verifikasi Sprint)
- **Saran perbaikan**: tambah catatan eksplisit — kalau sprint yang sama mengubah/memperpanjang demo data (`data/*_demo.xml`), WAJIB jalankan ulang SELURUH unit test suite (bukan cuma test yang baru ditulis sprint ini) sebelum menganggap sprint selesai, karena demo data shared lintas test class.

### 🐛 Pola Git (Masalah Kode)

- **Zero commit fix/revert/hotfix** di 14 sprint (`vessel_voyage_pnl` + `vessel_bunker_management`) — grep word-boundary bersih, konsisten dengan 2 retro sebelumnya.
- **1 commit breakdown non-sprint per modul** (`9f844b2` untuk `vessel_voyage_pnl`, `389ef90` untuk `vessel_bunker_management`) — wajar, pola konsisten sejak modul pertama.
- File sering diubah ulang: `SPRINT_REPORT.md`, `sprints/.current_sprint`, `vessel_bunker_management/data/vessel_bunker_management_demo.xml` (5×), `vessel_bunker_management/__manifest__.py` (7×), `vessel_bunker_management/views/vessel_bunker_management_menus.xml` (7×) — semua wajar (bertumbuh tiap sprint by design, sama pola modul sebelumnya).

### 🕳️ Gap Skill Coverage

1. **Retro tidak dijalankan untuk siklus Sprint 15-21 sebelum lanjut ke modul baru** (Pola #0) — gap proses paling signifikan sesi ini.
2. **`sprint.md` Pre-flight grep list belum sinkron dengan 3 gotcha Odoo 19 baru** yang ditambahkan ke `CLAUDE.md` selama Sprint 23-24 (Pola #2) — pola gap yang SAMA persis dengan temuan retro Sprint 8-14 poin 1, menandakan saran perbaikan retro sebelumnya belum ditindaklanjuti secara permanen/proses.
3. **Tidak ada pre-flight/guidance untuk pola `has_group()` di demo-context** (Pola #1) meski sudah terjadi 3x lintas 2 modul berbeda.
4. **Tidak ada instruksi eksplisit "rerun semua test setelah demo data berubah"** di `sprint.md` Langkah 8 (Pola #4).

### ✅ Yang Berjalan Baik

- **Zero commit fix/revert sungguhan di 14 sprint** — pola bersih berlanjut dari 2 retro sebelumnya.
- **33/33 unit test pass** (14 `vessel_voyage_pnl` + 19 `vessel_bunker_management`), tidak ada regresi permanen (semua regresi transient ditemukan & diperbaiki dalam sprint yang sama).
- **11/11 acceptance criteria §10 tech spec lulus untuk KEDUA modul**, seluruhnya dengan nilai eksak sesuai spec (bukan aproksimasi) — `vessel_voyage_pnl` (10 penuh + 1 keterbatasan tooling didokumentasikan transparan) dan `vessel_bunker_management` (11/11 penuh).
- **Fresh-install test dari database kosong dijalankan di kedua modul** sebagai bukti struktural, dengan trade-off yang didokumentasikan transparan (tanpa `--test-enable` untuk `vessel_bunker_management` demi waktu, sesuai lesson learned dari `vessel_voyage_pnl` Sprint 21 yang ditulis proaktif ke `sprint_28.md` SEBELUM sprint itu dimulai — bukti bahwa lesson learned lintas-modul benar-benar dipakai, bukan cuma didokumentasikan).
- **Arah dependency satu-arah dijaga ketat** — `vessel_bunker_management` extend `vessel.charter.contract`/`vessel.hire.statement.line` tanpa pernah mengubah `vessel_chartering` sendiri, dicek ulang eksplisit di Sprint 28 sebagai bagian audit final.
- **Keputusan desain ambigu tetap ditanyakan ke user** — 4 pertanyaan terstruktur di awal `vessel_bunker_management` (portal surveyor, threshold scope, BOD/BOR scope, approval matrix), semua dijawab sebelum sprint pertama dimulai.
- **Bug laten pre-existing (`fleet_fuel_log._create_stock_move()`) ditemukan sebagai efek samping**, didokumentasikan transparan sebagai known issue di luar scope alih-alih diam-diam diabaikan.

### 🔧 Kandidat Perbaikan Skill

| Prioritas | Skill File | Masalah | Saran Perbaikan | Status |
|-----------|-----------|---------|-----------------|--------|
| HIGH | Proses (belum ada skill file spesifik) | Retro siklus modul bisa terlewat kalau sesi langsung lanjut ke modul baru tanpa jeda (Pola #0) | Tambah gate check: sebelum menulis sprint breakdown modul baru, cek `RETRO.md` sudah punya entry modul sebelumnya | ⬜ pending |
| HIGH | `sprint.md` (Pre-flight) | Grep list Pola Odoo 19 Terlarang belum sinkron dengan 3 gotcha baru (function-in-noupdate, cross-module noupdate skip, stock.move.name) | Tambah 3 pola ke grep list `sprint.md` | ⬜ pending |
| HIGH | `CLAUDE.md` Konvensi Kode | Tidak ada guidance tertulis soal `has_group()` gagal di demo-context (3x kejadian) | Tambah catatan eksplisit: demo code tulis field/state langsung, jangan panggil action method guarded | ⬜ pending |
| MED | `CLAUDE.md` Konvensi Kode | Tidak ada catatan "known limitation" compute field depend search() lintas model tidak auto-recompute | Tambah catatan permanen + solusi (unlink + reinstall) | ⬜ pending |
| MED | `sprint.md` (Langkah 8) | Tidak ada instruksi eksplisit rerun semua test setelah demo data berubah dalam sprint yang sama | Tambah catatan di Langkah 8 | ⬜ pending |

### 💡 Rekomendasi untuk Siklus Berikutnya

1. **Jalankan `/improve` sekarang** (sebelum modul roadmap berikutnya, kalau ada, dimulai) — 5 kandidat di atas semuanya TIER 1/2 (aman, tidak mengubah alur utama), cocok untuk auto-apply.
2. **Prioritaskan HIGH #1 (gate retro)** dulu — ini meta-level, tapi kalau tidak diperbaiki, retro modul ke-5 berpotensi terlewat lagi dengan pola yang sama persis (autonomous mode yang langsung lompat ke modul berikutnya).
3. Modul roadmap berikutnya (kalau ada) akan mewarisi 24 baris `recurring_blockers` di `learning_log.json` — cukup kaya untuk jadi referensi cepat, tapi pastikan pre-flight `sprint.md` benar-benar meng-grep semuanya, bukan cuma menyimpan sebagai dokumentasi pasif (poin ini adalah inti dari Pola #2 dan Gap #2 di atas, sudah 2x muncul di 2 retro berturut-turut).

---

## 2026-07-03 — Retrospektif Sprint 8–14 (MVP `vessel_voyage_operations` complete)

**Project**: Odoo Shipping Vertical Solution — modul `vessel_voyage_operations` (+ restrukturisasi app `maritime`, + 3 calendar view tambahan di `vessel_chartering`)
**Scope**: Sprint 8 sampai Sprint 14 (7 sprint, roadmap Layer 2 Komersial #2)
**Reviewed**: 2026-07-03
**Reviewed by**: Claude Code Retro Agent

### 📊 Ringkasan Kuantitatif

| Metric | Nilai |
|--------|-------|
| Sprint dianalisis | 7 (Sprint 8-14) + 1 restrukturisasi mid-cycle (app Maritime) |
| Total tasks (approx, dari checklist tiap sprint) | ~68 |
| Fix/revert commits | 0 (grep word-boundary bersih, tidak ada false positive kali ini) |
| Unique blocker entries | 10 mention, 4 di antaranya pola berulang (≥2 kejadian) |
| Recurring blockers baru (kategori sama >1x, di luar yang sudah resolved dari retro Sprint 1-7) | 3 kategori baru, 1 kategori lanjutan dari retro sebelumnya |
| Skill gap terdeteksi | 5 (4 baru + 1 lanjutan proses sinkronisasi) |

### 🔁 Pola Blocker Sistemik

#### 1. Odoo 19 API rename/removal — lanjutan pola dari retro Sprint 1-7, 2 kejadian baru
- **Severity**: HIGH
- **Kejadian konkret**:
  1. Sprint 11: `_sql_constraints = [(name, sql, message), ...]` (list attribute klasik) ternyata **silent no-op** di Odoo 19 — tidak ada error, tidak ada warning, constraint database memang tidak pernah ter-apply. Baru ketahuan karena unit test yang sengaja menguji constraint itu gagal (`IntegrityError not raised`). Ganti ke `models.Constraint('sql...', 'message')` sebagai atribut kelas terpisah.
  2. Sprint 12: `res.groups.users` (ambil anggota grup) sudah tidak ada — rename jadi `res.groups.user_ids`. Kali ini **langsung ketahuan** sebagai `ParseError` saat load demo data (bukan silent seperti kejadian #1), karena dipanggil dari `<function>` XML tag.
- **Root cause**: sama seperti retro Sprint 1-7 — pengetahuan API Odoo dari versi lebih lama, Odoo 19 breaking change tanpa deprecation warning yang konsisten (kadang silent no-op seperti `_sql_constraints`, kadang `AttributeError` jelas seperti `res.groups.users`).
- **Skill yang perlu diupdate**: `sprint.md` (Pre-flight Check) — **gap penting**: kedua pola ini SUDAH masuk `CLAUDE.md` Checklist Odoo 19 Gotcha (dokumentasi manual saat ditemukan), TAPI belum pernah disinkronkan ke grep list otomatis di `sprint.md` Langkah 4 (yang masih berhenti di 3 pola dari retro Sprint 1-7: `decoration-secondary`, `<group string=/expand=>`, `.groups_id`).
- **Saran perbaikan**: tambah 2 pola baru ke grep list `sprint.md`, DAN tambahkan aturan proses eksplisit — setiap kali baris baru masuk ke `CLAUDE.md` Gotcha table, WAJIB sinkron ke grep list `sprint.md` di commit yang sama. Kalau tidak, pola "dokumentasi ada tapi tidak di-grep aktif" — persis masalah yang sudah dipecahkan retro Sprint 1-7 — akan terulang terus untuk tiap gotcha baru.

#### 2. Model baru lupa `mail.thread`/`mail.activity.mixin` — pola baru, 1 kejadian jadi bug laten 3 sprint
- **Severity**: HIGH
- **Kejadian konkret**:
  1. Sprint 12: `vessel.port.disbursement` pakai `activity_schedule()` di `_check_variance_threshold()` tapi model tidak `_inherit` mixin apapun — `AttributeError` langsung ketahuan saat install (karena `_check_variance_threshold` dipanggil dari demo data via `<function>` tag).
  2. Sprint 13 (tapi bug-nya lahir Sprint 10): `vessel.port.call` pakai `message_post()` di `_check_estimated_actual_sequence()` sejak Sprint 10, TIDAK pernah `_inherit mail.thread`. Constraint itu tidak pernah benar-benar ter-trigger oleh dummy data selama Sprint 10-12 (kondisi ETA/ATA inconsistent tidak pernah muncul di skenario test), jadi bug ini **tidur selama 3 sprint** tanpa terdeteksi. Baru ketahuan Sprint 13 saat cron `_cron_eta_reminder`/`_cron_clearance_pending_alert` (fitur baru yang butuh `activity_schedule()`) pertama kali benar-benar mengeksekusi jalur kode itu.
- **Root cause**: bukan Odoo 19 breaking change — murni disiplin coding sendiri (lupa satu baris `_inherit`). Tapi **jauh lebih berbahaya** dari typo biasa karena bisa lolos review dan testing berminggu-minggu kalau code path yang memicu error jarang dieksekusi oleh dummy data/test yang ada.
- **Skill yang perlu diupdate**: `sprint.md` (Pre-flight Check)
- **Saran perbaikan**: tambah pre-flight check baru — untuk tiap model baru di modul yang disentuh sprint, grep apakah file model itu memanggil `message_post`/`activity_schedule`; kalau ya, verifikasi `_inherit` model tsb benar-benar mengandung `mail.thread` atau `mail.activity.mixin` sebelum install.

#### 3. Demo data idempotency break dari write()-override / action-method-via-XML — pola baru, sudah teratasi sendiri
- **Severity**: MED
- **Kejadian konkret**:
  1. Sprint 11: override `write()` di `vessel.noon.report` untuk block edit record `approved`/`rejected` — ternyata memblokir ORM data loader sendiri (demo data XML re-write field yang sama saat `-u` kedua kali → `UserError` karena state sudah bukan draft → **install gagal total**). Diperbaiki dengan menghapus override, pindah ke view-level `readonly` attribute.
  2. Sprint 12: belajar dari kejadian #1, sengaja set `state=confirmed` via `<field>` langsung di demo data (bukan panggil `action_confirm()` yang state-transition-guarded), lalu trigger side-effect (`_check_variance_threshold`) terpisah lewat `<function>` XML tag yang idempotent-guarded sendiri.
- **Root cause**: pola umum di banyak project Odoo (proteksi "read-only setelah approved" secara naive di level model), tapi berbenturan dengan cara Odoo me-reload demo data XML setiap `-u` (selalu re-write, bukan cuma create sekali).
- **Skill yang perlu diupdate**: `sprint.md` (Aturan Implementasi)
- **Saran perbaikan**: tambah guidance eksplisit — kalau butuh "read-only setelah state tertentu", implementasi di level VIEW (`readonly="state in (...)"`), BUKAN override `write()` Python. Pola ini sudah dipahami & konsisten dihindari sejak Sprint 12, tapi belum ada tulisan eksplisit di skill file supaya tidak perlu ditemukan ulang di sprint/modul berikutnya.

#### 4. Security group reference tidak di-cross-check ke tabel §6 tech spec — 1 kejadian, mirip pola §10 dari retro sebelumnya
- **Severity**: MED
- **Kejadian konkret**: Sprint 12 pakai `account.group_account_manager` untuk notifikasi "Finance" tanpa cross-check ke tabel §6 tech spec, yang sebenarnya eksplisit menyebut `account.group_account_invoice`. Ketahuan & diperbaiki Sprint 13 saat security lengkap di-review sistematis.
- **Root cause**: sama persis pola "cross-check acceptance criteria §10 cuma di sprint terakhir" dari retro Sprint 1-7 — kali ini untuk tabel security §6, bukan §10.
- **Skill yang perlu diupdate**: `sprint.md`
- **Saran perbaikan**: perluas guidance cross-check yang sudah ada (§10) supaya juga cover §6 (security group references) — kalau sprint task menyentuh group dari modul lain, cross-check dulu xmlid persis ke tech spec, jangan asumsi nama yang "kedengaran benar" (pola gagal yang sama seperti xpath `res.config.settings` di retro Sprint 1-7).

### 🐛 Pola Git (Masalah Kode)

- **File sering diubah ulang**: `SPRINT_REPORT.md`, `sprints/.current_sprint`, `CLAUDE.md`, `vessel_voyage_operations/views/vessel_voyage_operations_menus.xml` (7×), `vessel_voyage_operations/__manifest__.py` (7×), `vessel_chartering/data/vessel_chartering_demo.xml` (7×) — semua wajar (file yang memang bertumbuh tiap sprint by design).
- **Commit masalah**: **tidak ada** commit fix/revert/hotfix sungguhan di 7 sprint (grep word-boundary bersih, tidak ada false positive kali ini — perbaikan retro Sprint 1-7 terbukti bekerja).
- **1 commit di luar pola sprint biasa**: `6af4d05` (restrukturisasi app Maritime) — bukan "commit masalah", tapi commit non-sprint mid-cycle atas permintaan user, didokumentasikan terpisah di `SPRINT_REPORT.md` sesuai konvensi.

### 🕳️ Gap Skill Coverage

1. **`sprint.md` Pre-flight grep list Pola Odoo 19 Terlarang tidak sinkron dengan `CLAUDE.md` Gotcha table** — 2 baris baru masuk dokumentasi tapi tidak masuk grep aktif (lihat Pola #1 di atas). Ini gap proses, bukan cuma gap satu command file.
2. **Tidak ada pre-flight check untuk kelengkapan `mail.thread`/`mail.activity.mixin`** pada model baru yang pakai `message_post`/`activity_schedule` (Pola #2).
3. **Tidak ada guidance tertulis soal anti-pattern write()-override untuk "read-only after state"** (Pola #3) — sudah dipahami tim (yaitu saya sendiri, tapi across sprints) secara tacit, belum eksplisit di skill file.
4. **Tidak ada cross-check security group (§6) sepadan dengan cross-check acceptance criteria (§10) yang sudah ada** (Pola #4).
5. **Command file (`sprint.md`) tidak punya mekanisme "sinkronisasi wajib" antara `CLAUDE.md` (dokumentasi) dan grep list-nya sendiri (executable check)** — meta-gap yang mendasari Pola #1: menambah baris ke tabel dokumentasi TIDAK otomatis berarti pola itu benar-benar di-enforce oleh pre-flight.

### ✅ Yang Berjalan Baik

- **Zero commit fix/revert sungguhan di 7 sprint** — sama seperti Sprint 1-7, semua masalah diselesaikan sebelum commit.
- **22/22 unit test pass** (12 `vessel_chartering` + 10 `vessel_voyage_operations`), tidak ada regresi sepanjang 7 sprint + restrukturisasi Maritime.
- **Fresh-install test 8 modul bareng** (5 fleet + `vessel_chartering` + `vessel_voyage_operations` + `maritime`) dijalankan eksplisit di Sprint 14 sebagai bagian audit final — bukan cuma "setiap sprint `-u` bersih" seperti Sprint 1-7, tapi benar-benar database kosong dari nol, kemudian di-drop lagi (tidak ada residu).
- **Idempotency selalu diverifikasi eksplisit tiap sprint**, termasuk kasus non-trivial: jumlah `mail.activity` tidak dobel setelah 2× `-u` (Sprint 12), yang butuh guard eksplisit di kode (bukan cuma count record biasa).
- **Blocker tidak pernah dibiarkan carry-over** — semua 4 pola di atas ditemukan & diperbaiki dalam sprint yang sama atau sprint berikutnya, tidak pernah menumpuk.
- **Keputusan desain ambigu selalu ditanyakan ke user**, bukan diasumsikan diam-diam — 2 contoh eksplisit sprint ini: 4 opsi nama app (Maritime dipilih user) dan 3 opsi cakupan calendar view (per-model dipilih user), keduanya via pertanyaan terstruktur dengan preview konkret sebelum eksekusi.
- **Technical debt didokumentasikan secara sadar, bukan disembunyikan** — `fleet_trip_id` (Sprint 9) dan `assigned_user_ids` compute chain (Sprint 13) sama-sama soft-dependency ke modul lain yang "diasumsikan selalu terinstall di environment ini", ditulis eksplisit sebagai keputusan trade-off di kode & SPRINT_REPORT, bukan menyembunyikan risikonya.

### 🔧 Kandidat Perbaikan Skill

| Prioritas | Skill File | Masalah | Saran Perbaikan | Status |
|-----------|-----------|---------|-----------------|--------|
| HIGH | `sprint.md` (Pre-flight) | Grep list Pola Odoo 19 Terlarang tidak sinkron dengan CLAUDE.md Gotcha table (2 pola baru: `_sql_constraints=`, `res.groups.users`) | Tambah 2 pola ke grep list + aturan proses "setiap baris baru CLAUDE.md Gotcha WAJIB sinkron ke grep list sprint.md di commit yang sama" | ✅ applied (2026-07-03) |
| HIGH | `sprint.md` (Pre-flight) | Tidak ada check kelengkapan mail.thread/mail.activity.mixin untuk model baru yang pakai message_post/activity_schedule | Tambah pre-flight: grep model baru yang pakai message_post/activity_schedule, verifikasi _inherit mixin ada | ✅ applied (2026-07-03) |
| MED | `sprint.md` (Aturan Implementasi) | Tidak ada guidance tertulis anti-pattern write()-override untuk "read-only after state" (break demo data idempotency) | Tambah catatan eksplisit: read-only-after-state via view attribute, bukan override write() Python | ✅ applied (2026-07-03) |
| MED | `sprint.md` | Cross-check security group (§6) tidak seketat cross-check acceptance criteria (§10) yang sudah ada | Perluas guidance cross-check existing supaya cover §6 juga | ✅ applied (2026-07-03) |

### 💡 Rekomendasi untuk Siklus Berikutnya

1. Terapkan HIGH #1 dan #2 duluan — sama-sama berpotensi jadi silent/laten bug yang lolos berminggu-minggu tanpa error jelas.
2. Untuk modul ketiga (`vessel_voyage_pnl`, roadmap #3), mulai dengan checklist Odoo 19 gotcha + mixin-check yang sudah lengkap dari retro ini — jangan mulai dari nol, dan pastikan `/improve` benar-benar dijalankan sebelum sprint pertama dimulai (bukan cuma didokumentasikan di retro).
3. `vessel_voyage_pnl` punya kompleksitas baru yang belum pernah dihadapi 2 modul sebelumnya: agregasi lintas-modul (query `account.move.line` by `analytic_distribution`) dan alokasi biaya tidak langsung (`vessel.cost.allocation.rule`) — pertimbangkan sprint breakdown yang lebih granular untuk model inti (`vessel.voyage.pnl`) mengikuti saran tech spec §12.2 poin 3 (revenue dulu, baru direct cost, baru allocated cost — jangan sekaligus).

---

## 2026-07-02 — Retrospektif Sprint 1–7 (MVP `vessel_chartering` complete)

**Project**: Odoo Shipping Vertical Solution — modul `vessel_chartering`
**Scope**: Sprint 1 sampai Sprint 7 (+ Sprint 0 environment setup)
**Reviewed**: 2026-07-02
**Reviewed by**: Claude Code Retro Agent

### 📊 Ringkasan Kuantitatif

| Metric | Nilai |
|--------|-------|
| Sprint dianalisis | 7 (+ Sprint 0 setup) |
| Total tasks (approx, dari checklist tiap sprint) | ~71 |
| Fix/revert commits | 0 real (2 false-positive dari grep naive — lihat Gap Command Coverage) |
| Unique blocker entries | 21 mention, ~6 di antaranya satu kategori berulang |
| Recurring blockers (kategori sama >1x) | 1 kategori besar (Odoo 19 API/schema drift), 6 kejadian |
| Skill gap terdeteksi | 5 |

### 🔁 Pola Blocker Sistemik

#### Odoo 19 API/schema drift dari pengetahuan Odoo versi lama — muncul 6 kali (Sprint 2, 2, 4, 4, 6, 6)
- **Severity**: HIGH
- **Kejadian konkret**:
  1. Sprint 2: `decoration-secondary` invalid di RNG schema list view (cuma `muted/info/warning/success/danger`)
  2. Sprint 2: `<group expand="0" string="...">` invalid di search view RNG schema (pola classic Odoo <17)
  3. Sprint 4: `decoration-secondary` **kepakai lagi** — persis kesalahan yang sama, tertulis eksplisit "lupa pelajaran Sprint 2" di SPRINT_REPORT
  4. Sprint 4: `res.users.groups_id` → rename jadi `group_ids` di Odoo 19
  5. Sprint 6: `invoice_policy` bukan field core `product.product` (punya modul `sale`)
  6. Sprint 6: xpath tebakan salah untuk `res.config.settings` (`invoicing_policy` vs `invoicing_settings` yang benar)
- **Root cause**: pengetahuan pola Odoo (nama field, attribute view, xpath target) berasal dari versi Odoo lebih lama, sementara Odoo 19 banyak melakukan breaking change tanpa deprecation warning yang jelas di level penulisan kode — baru ketahuan saat load registry/install.
- **Skill yang perlu diupdate**: `sprint.md` (Pre-flight Check)
- **Saran perbaikan**: kejadian #3 adalah bukti paling kuat bahwa catatan "pelajaran" di SPRINT_REPORT.md (prosa naratif) **tidak cukup** — perlu diubah jadi checklist yang benar-benar di-grep sebelum install, bukan diandalkan dari ingatan/baca ulang manual.

### 🐛 Pola Git (Masalah Kode)

- **File sering diubah ulang**: `SPRINT_REPORT.md` (9×), `sprints/.current_sprint` (8×), `vessel_chartering_demo.xml` (7×), `CLAUDE.md` (7×), `vessel_charter_contract_views.xml` (6×), `ir.model.access.csv` (6×), `vessel_charter_contract.py` (6×) — semua wajar (file yang memang di-update tiap sprint by design: report, tracker, demo data yang terus bertambah, model kontrak sebagai pusat gravitasi seluruh fitur).
- **Commit masalah**: **tidak ada commit fix/revert/hotfix sungguhan** di 7 sprint. Grep pattern retro.md sendiri sempat menandai `4476be8` dan `9afe1df` sebagai "commit masalah" — ternyata false positive: kata "fix" ketemu di substring **"pre-fixture"**, kata "patch" ketemu di substring **"despatch"** (keduanya istilah domain maritim yang legit, bukan indikasi bug).
- **Root cause pola positif ini**: semua iterasi/percobaan-ulang terjadi **sebelum commit** (loop tulis-kode → syntax check → install → cek log ERROR → fix kalau ada → baru commit), bukan sesudahnya. Disiplin ini konsisten di semua 7 sprint.

### 🕳️ Gap Skill Coverage

1. **`sprint.md` Pre-flight Check tidak grep pola RNG/API Odoo 19 yang sudah diketahui bermasalah** — padahal pola yang sama (`decoration-secondary`) sudah kejadian 2×. Pre-flight saat ini cuma cek syntax Python/XML generik, tidak cek pola spesifik yang riwayat project ini sendiri sudah buktikan sering salah.
2. **Tidak ada langkah "verifikasi field/xpath exists di source sebelum dipakai"** untuk kasus extend model dari modul lain (`product.product`, `res.config.settings`) — baru dicek reaktif setelah install gagal (Sprint 6), padahal bisa proaktif via grep container sebelum nulis XML (yang justru sudah dilakukan untuk RNG schema di kejadian lain, tapi tidak dijadikan langkah standar).
3. **Cross-check acceptance criteria tech spec §10 cuma dilakukan sistematis di Sprint 7 (terakhir)** — gap §10.8 (COA butuh 3 shipment, dummy data cuma 2) baru ketahuan di ujung, bukan saat Sprint 2 (saat COA pertama kali diimplementasi). Kalau setiap sprint yang menyentuh nomor acceptance criteria tertentu langsung cross-check ke tabel §10, gap ini ketahuan lebih awal.
4. **Tidak ada langkah "jalankan test satu-satu segera setelah ditulis"** — Sprint 6 menulis seluruh test suite baru dulu (4 test), baru dijalankan, hasilnya 3 fail + 4 error sekaligus perlu di-debug bareng. Kalau tiap test dijalankan segera setelah ditulis, iterasi jadi lebih kecil dan cepat ketemu akar masalah.
5. **`retro.md` sendiri**: pattern grep fix/revert/patch di Langkah 3 pakai substring match polos, rawan false positive di project dengan istilah domain yang kebetulan mengandung kata itu (`pre-fixture`, `despatch`). Perlu word-boundary regex (`\bfix\b`, `\bpatch\b`, dst).

### ✅ Yang Berjalan Baik

- **Zero commit fix/revert sungguhan di 7 sprint** — semua masalah diselesaikan sebelum commit, bukan sesudahnya.
- **Idempotency check konsisten tanpa pernah dilewatkan** — tiap sprint selalu re-run `-u` kedua kali + cek count tidak duplikat, disiplin yang tidak pernah bolong.
- **Verifikasi manual end-to-end via Odoo shell** (bukan cuma unit test) di titik-titik kritis (Sprint 1 analytic account, Sprint 2 full state machine cycle, Sprint 6 invoice generation dari dummy data asli) — dan selalu `env.cr.rollback()` supaya tidak mengotori dummy data permanen.
- **Blocker tidak pernah carry-over ke sprint berikutnya** — tiap sprint yang punya blocker langsung menyelesaikannya sebelum sprint ditutup.
- **Dummy data dirancang presisi mereplikasi acceptance criteria** (bukan angka acak) — Sprint 4, 5, 6 semua punya skenario dummy data yang sengaja dihitung supaya hasilnya persis sama dengan angka acceptance criteria tech spec, sehingga verifikasi manual = verifikasi acceptance criteria sekaligus.
- **Proaktif menutup gap di sprint terakhir** (§10.8) alih-alih deklarasi selesai prematur — menjalankan checklist acceptance criteria secara sistematis sebagai gate akhir, bukan asumsi "kalau semua sprint sudah jalan berarti semua kriteria terpenuhi".

### 🔧 Kandidat Perbaikan Skill

| Prioritas | Skill File | Masalah | Saran Perbaikan | Status |
|-----------|-----------|---------|-----------------|--------|
| HIGH | `sprint.md` (Pre-flight) | Tidak grep pola RNG/API Odoo 19 yang sudah 2× kejadian (`decoration-secondary` dll) | Tambah langkah grep eksplisit untuk daftar pola terlarang sebelum tiap install: `decoration-secondary`, `<group ... string=/expand=>` di search view, `.groups_id` (harus `.group_ids`) | ✅ applied (2026-07-03) |
| HIGH | `sprint.md` | Extend field/xpath dari modul lain (product, res.config.settings dst) dicek reaktif, bukan proaktif | Tambah langkah: sebelum nulis field/xpath yang menyentuh model modul lain, grep dulu source model itu di container untuk konfirmasi field/block id benar-benar ada | ✅ applied (2026-07-03) |
| MED | `sprint.md` | Cross-check acceptance criteria tech spec cuma di sprint terakhir | Tiap sprint yang tasknya eksplisit menyebut nomor acceptance criteria (§10.x dst), tambahkan sub-langkah "cross-check ke tabel acceptance criteria lengkap", bukan ditunda ke sprint penutup | ✅ applied (2026-07-03) |
| MED | `sprint.md` | Test ditulis sekaligus lalu di-debug massal (3 fail+4 error bareng di Sprint 6) | Tambah guidance: jalankan tiap test individual segera setelah ditulis (`--test-tags module:Class.test_name`) sebelum lanjut test berikutnya | ✅ applied (2026-07-03) |
| LOW | `retro.md` | Grep fix/revert/patch substring polos, false positive di "pre-fixture"/"despatch" | Ganti ke word-boundary regex (`\bfix\b`, `\bpatch\b`, dst) | ✅ applied (2026-07-03) |
| LOW | `CLAUDE.md` | "Pelajaran" Odoo 19 cuma prosa naratif di SPRINT_REPORT, gampang lupa (terbukti dari kejadian #3 di atas) | Pindahkan ke checklist grep-able terpisah di CLAUDE.md (bukan cuma narasi), supaya bisa langsung dijalankan sebagai command, bukan diandalkan dari ingatan | ✅ applied (2026-07-03) |

### 💡 Rekomendasi untuk Siklus Berikutnya

1. Terapkan HIGH #1 dan #2 duluan — keduanya langsung menyasar pola blocker sistemik paling sering (6 dari ~10 blocker riil sepanjang project ini berasal dari 2 kategori itu).
2. Kalau lanjut ke modul berikutnya (`vessel_voyage_operations`, `vessel_voyage_pnl`, dst sesuai roadmap Fase 2/3 tech spec), mulai dengan checklist Odoo 19 gotcha yang sudah terkumpul dari project ini — jangan mulai dari nol lagi.
3. Pertimbangkan menjadikan "cross-check acceptance criteria per sprint" sebagai bagian permanen dari template sprint file (`sprints/sprint_NN.md`), bukan cuma di Definition of Done sprint terakhir.

---
