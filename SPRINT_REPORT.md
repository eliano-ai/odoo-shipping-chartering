# Sprint Report — vessel_chartering

Log kronologis progress development modul `vessel_chartering`. Entry baru ditambahkan di **bawah**.

---

## Sprint 0 — Environment Setup — 2026-07-02

**Status**: ✅ Done

### Task Selesai
- [x] Docker Compose (Odoo 19.0 Community + PostgreSQL 16) — `docker-compose.yml`
- [x] Database dev `shipping_dev` dibuat, semua 5 modul fleet existing + `vessel_crew_management` install bersih
- [x] `CLAUDE.md` dibuat untuk konteks project (dibaca oleh `/sprint` dan `/retro`)
- [x] Command `/sprint` dan `/retro` diadaptasi dari `sunartha-claude-skills-dev` ke konteks Odoo (mode checkpoint, tanpa email, pre-flight Docker/Odoo)
- [x] Git fresh-start: orphan branch `chartering-dev` → pushed ke `https://github.com/eliano-ai/odoo-shipping-chartering` (branch `main`). Remote `origin` (GitLab company) tidak disentuh.
- [x] Breakdown 7 sprint untuk MVP `vessel_chartering` (`sprints/sprint_01.md` s.d. `sprint_07.md`) berdasarkan `TECH_SPEC_vessel_chartering.md`

### Blocker & Resolusi
- **`vessel_crew_management` depends ke `hr_payroll`** (Enterprise-only, tidak ada di Community) → install gagal. Dicek: tidak ada satupun kode yang benar-benar pakai model/field `hr.payroll`, dependency ditambahkan speculative untuk integrasi masa depan yang belum diimplementasi. **Resolusi**: hapus `hr_payroll` dari `depends` di `vessel_crew_management/__manifest__.py`. Install ulang sukses.
- **Git identity belum terkonfigurasi** (local maupun global) → commit pertama gagal. **Resolusi**: set `git config user.name/email` scope local (bukan global) sesuai konfirmasi user.
- **Repo GitHub baru berisi 1 commit auto-generated** (README default) yang konflik dengan fresh-start push. **Resolusi**: konfirmasi ke user, force-push (`--force-with-lease`) menimpa placeholder tsb.
- **`docker compose exec` di Git Bash Windows mentranslate path Unix** (`/etc/odoo/odoo.conf` dsb jadi path Windows) → perlu prefix `MSYS_NO_PATHCONV=1` di semua command exec.

### Verifikasi
- ✅ `docker compose ps` — kedua container healthy
- ✅ `curl http://localhost:8069/web/login` → HTTP 200
- ✅ 5 modul fleet + vessel_crew_management: `state=installed` di `ir_module_module`
- ✅ Tidak ada ERROR/CRITICAL di log install (warning `compute_sudo` inconsistency di `vessel.seafarer` dicatat sebagai item minor untuk retro, bukan blocker)

### Catatan
- Odoo edition: **Community** (bukan Enterprise seperti target awal tech spec) — scope MVP `vessel_chartering` tidak butuh app Enterprise (documents/approvals disebut opsional di tech spec)
- Keputusan atas 4 "Pertanyaan Terbuka" tech spec §11 didokumentasikan di `sprints/sprint_06.md` (akan dikonfirmasi ulang ke user sebelum Sprint 6 dieksekusi)
- Item minor untuk backlog (bukan blocking): `vessel.seafarer.cert_expiring_count`/`cert_expired_count`/`has_critical_cert_issue` punya inconsistent `compute_sudo`/`store` — warning saat load registry, tidak menyebabkan error fungsional

---

## Sprint 1 — Module Foundation & Master Data — 2026-07-02

**Status**: ✅ Done

### Task Selesai
- [x] Skeleton modul `vessel_chartering/` (manifest depends: fleet, fleet_document_id, account, analytic, mail)
- [x] Security groups `group_chartering_user` / `group_chartering_manager` + access rights
- [x] Model `vessel.cargo.type` + views + menu Konfigurasi
- [x] Model `vessel.charter.terms` + views + menu Konfigurasi
- [x] Model `vessel.laytime.interruption.type` + views + menu + seed data (6 tipe: Hujan, Shifting, Equipment Breakdown Shore/Vessel, Waiting Berth, Force Majeure)
- [x] Extend `res.partner`: `is_port`, `unlocode` + view list Pelabuhan terfilter
- [x] 2 Analytic Plans (`account_analytic_plan_vessel`, `account_analytic_plan_voyage`) — idempotent, dikonfirmasi tidak duplikat setelah `-u` kedua kali
- [x] Extend `fleet.vehicle`: `analytic_account_id` dengan auto-create logic di `create()`/`write()` — **diverifikasi end-to-end** via test vessel di Odoo shell (analytic account otomatis terbentuk & terhubung ke plan Vessel)
- [x] Menu root "Chartering" (sequence 18, sejajar modul fleet lain) + submenu Konfigurasi
- [x] Dummy data: 3 cargo type, 2 charter terms, 5 port (Tanjung Priok, Balikpapan, Tarahan, Satui, Singapore)

### Blocker & Resolusi
- **Field `gt`/`dwt` berpotensi duplikat** — dicek dulu sebelum implementasi, ternyata `fleet_document_id` sudah punya `gross_tonnage`/`deadweight_tonnage`. **Resolusi**: tidak buat field baru, cukup depends ke `fleet_document_id` dan reuse field existing.
- **`charter_contract_ids`/`active_charter_id`/`charter_status` di `fleet.vehicle` di-skip dari Sprint 1** (beda dari rencana awal sprint file yang sempat menyebut "declare sekarang dengan forward-reference") — One2many ke model `vessel.charter.contract` yang belum ada akan membuat registry gagal load saat startup. **Resolusi**: field-field ini dipindah murni ke Sprint 2 saat model kontraknya sudah ada.
- **Demo data tidak ter-load meski `--without-demo=False`** — database `shipping_dev` dibuat awal dengan `--without-demo=True`, sehingga sticky secara database-level dan tidak bisa di-override per modul belakangan. **Resolusi**: pindahkan `data/vessel_chartering_demo.xml` dari key `demo` ke key `data` manifest (selalu load, tidak bergantung mode demo) — sesuai instruksi eksplisit user bahwa master data dummy wajib ada di environment dev ini.
- **Query psql manual salah** untuk field translatable (`translate=True`) — field `name` di beberapa model tersimpan sebagai jsonb (`{"en_US": "..."}`), bukan plain text. Perlu `->>'en_US'` di query verifikasi manual (tidak mempengaruhi kode modul, cuma cara saya cek data).

### Verifikasi
- ✅ Install bersih tanpa ERROR/CRITICAL (`Module vessel_chartering loaded in 1.6s`)
- ✅ Update (`-u`) kedua kali tidak duplikat — analytic plan count tetap 1, cargo type count tetap 3
- ✅ Semua master data dummy muncul di database (cargo type, charter terms, interruption type, port)
- ✅ Tidak ada field `gt`/`dwt` duplikat
- ✅ Menu "Chartering" muncul sejajar Fleet/Dokumen Legal/Fuel/Maintenance/Spareparts/Crew Management
- ✅ Analytic account auto-create terverifikasi end-to-end via test vessel di Odoo shell (dibuat & dihapus lagi setelah verifikasi, tidak masuk dummy data permanen)

### Catatan
- Keputusan menyimpang dari `sprints/sprint_01.md` (charter_contract_ids dkk digeser ke Sprint 2) dicatat di sini supaya Sprint 2 tahu field itu perlu ditambahkan dari awal, bukan sekadar "sudah ada tinggal diisi logic"

---

## Setup Tambahan — Email Notifikasi Sprint (Outlook COM) — 2026-07-02

Ditambahkan di luar scope sprint file resmi, atas permintaan user setelah melihat contoh email `/pm`/`/sprint` dari project lain (`wicara`, memakai AppleScript+Mail.app macOS).

- `scripts/send_sprint_email.ps1` — kirim email via Outlook desktop COM automation (bukan AppleScript, karena environment ini Windows)
- Auto-launch Outlook + tunggu 15 detik jika belum running (root cause kegagalan pertama: `E_ABORT` saat Outlook belum jalan)
- Default recipient: To `eliano@sunartha.co.id`, Cc `daru@sunartha.co.id` (dikonfirmasi user)
- Diuji sukses kirim email test sebelum di-wire ke workflow
- `.claude/commands/sprint.md` diupdate: Langkah 12 baru (kirim email), Langkah 13 lama jadi laporan akhir

---

## Sprint 2 — Core Charter Contract Model & State Machine — 2026-07-02

**Status**: ✅ Done

### Task Selesai
- [x] Model `vessel.charter.contract` — semua field §3.2 (Umum, Voyage, Time Charter, COA, Compute/Monitoring)
- [x] `ir.sequence` CHO/%(year)s (out) & CHI/%(year)s (in), dipilih otomatis berdasar `direction` di `create()`
- [x] Constraints: `_check_dates`, `_check_coa_no_direct_laytime`, `_check_vessel_overlap` (warning, bukan blokir kecuali overlap penuh dgn in_progress)
- [x] State machine lengkap: draft→negotiation→confirmed→in_progress→completed→closed + cancelled, **diverifikasi end-to-end** via shell (termasuk auto-create analytic account saat confirm, freight_amount_final terhitung benar saat complete)
- [x] Wizard `vessel.charter.cancel.wizard` — **diverifikasi** alur cancel via shell
- [x] Extend `fleet.vehicle`: `charter_contract_ids`, `active_charter_id`, `charter_status` (compute) — **diverifikasi** vessel dengan kontrak in_progress menampilkan status benar (on_time_charter/on_voyage_charter/chartered_in)
- [x] COA: `shipment_ids`, `qty_shipped`/`qty_remaining` — **diverifikasi** agregasi dari 2 shipment child benar (13000 shipped, 87000 remaining dari komitmen 100000)
- [x] Security access untuk `vessel.charter.contract` & wizard cancel
- [x] Views form (notebook: Komersial, COA-Shipment, Estimate/Laytime/Hire/Invoicing placeholder, Lainnya), list, kanban (by state), calendar (by laycan), search (filter + group by)
- [x] Menu Fixtures/Kontrak: Semua Kontrak, Charter Out, Charter In, COA
- [x] Dummy data: 3 voyage charter (2 out beda state draft/confirmed, 1 in), 1 time charter in_progress, 1 COA + 2 shipment completed — plus demo vessel (tug/barge/MV) & demo partner karena belum ada data fleet.vehicle sama sekali di database

### Blocker & Resolusi
- **`decoration-secondary` invalid** di RNG schema Odoo 19 untuk list view (`Invalid attribute decoration-secondary for element field`) — schema Odoo 19 cuma kenal `muted`/`info`/`warning`/`success`/`danger`, tidak ada `secondary`. **Resolusi**: ganti ke `decoration-muted`.
- **`<group expand="0" string="Group By">` invalid** di search view RNG schema Odoo 19 (`Invalid attribute expand for element group`) — pola classic Odoo <17 ini tidak lagi valid; schema search view group cuma izinkan `colspan/rowspan/fill/height/width/name/color/invisible`. **Resolusi**: hapus atribut `string`/`expand`, cukup `<group>` polos membungkus filter group-by.
- **Tidak ada data `fleet.vehicle` sama sekali** di database (dicek — 0 rows) — tidak bisa buat dummy kontrak tanpa kapal. **Resolusi**: buat demo vessel (brand + model + 3 kapal: tug, barge, MV) sebagai bagian dummy data modul ini, di luar scope awal task 10 tapi diperlukan supaya dummy data kontrak realistis & bisa dipakai testing sprint berikutnya.

### Verifikasi
- ✅ Install/upgrade bersih tanpa ERROR/CRITICAL setelah 2 fix RNG schema di atas
- ✅ Idempotent — re-run `-u` kedua kali, count kontrak tetap 7, tidak ada error
- ✅ Full state machine cycle (draft→...→closed) sukses via shell, di-rollback (tidak ubah demo data permanen)
- ✅ Analytic account voyage auto-terbentuk saat action_confirm, terverifikasi nama & keberadaannya
- ✅ freight_amount_final terhitung benar (12.5 × 7400 = 92500) saat action_complete
- ✅ Constraint COA (tidak boleh vessel_id langsung) — raise ValidationError terverifikasi
- ✅ Cancel wizard — alur lengkap terverifikasi, state jadi cancelled
- ✅ COA qty_shipped/qty_remaining — 13000/87000 dari komitmen 100000, sesuai 2 shipment completed
- ✅ fleet.vehicle.charter_status — vessel dengan kontrak in_progress tampil "on_time_charter" dengan active_charter_id benar

### Catatan
- Smart button Estimates/Laytime/Invoices di form kontrak sudah ada tombolnya tapi invisible (count selalu 0 di sprint ini) — method action_view_estimates/action_view_laytime mereferensikan model yang belum ada (`vessel.voyage.estimate`, `vessel.laytime.calculation`), aman karena tidak pernah diklik selama count=0; akan diisi Sprint 3/4
- Field-level restriction "chartering_user tidak lihat COA nilai total" (§6 tech spec) belum diimplementasi — dicatat untuk Sprint 7 (task security review)
- **Pelajaran RNG schema Odoo 19** (dicatat untuk sprint berikutnya): hindari `decoration-secondary`, hindari `string`/`expand` di `<group>` search view — beda dari kebiasaan Odoo versi lama

---

## Setup Tambahan — Permission Allowlist (.claude/settings.json) — 2026-07-02

Atas permintaan user untuk mempercepat alur sprint (kurangi prompt izin berulang). Dibuat `.claude/settings.json` (project-level, ikut ter-commit):
- **Allow luas**: docker/docker compose, git read-ops + `git push github *` (hanya remote personal), python, grep/find/sed/cat/ls, script PowerShell di `scripts/`, skill `sprint`/`retro`
- **Ask** (tetap prompt): dropdb, pg_terminate_backend, `docker compose down/restart`
- **Deny total**: force-push, **`git push origin *`** (remote GitLab company — sengaja diblok permanen supaya tidak pernah ke-push otomatis dari workflow sprint), `git reset --hard`, `rm -rf`, `docker compose down -v` (hapus volume database dev), PowerShell destruktif (Remove-Item -Recurse, Stop-Process)

---

## Sprint 3 — Voyage Estimate — 2026-07-02

**Status**: ✅ Done

### Task Selesai
- [x] Model `vessel.voyage.estimate` — semua field §3.3 (jarak/kecepatan, bunker section dual-currency, cost lain, hasil/TCE)
- [x] Business rule single-selected — constraint `_check_single_selected`, **diverifikasi**: `action_select_baseline` otomatis un-select revisi lain, force-write manual ke `selected` kedua kali raise ValidationError
- [x] Compute `usd_rate` default dari `res.currency.rate` (fallback 0.0 jika rate tidak ada / currency sama)
- [x] Views form (grouped by section) + list (decoration selected)
- [x] `estimate_ids` One2many ditambahkan ke kontrak, `_compute_smart_button_counts` sekarang pakai count asli (bukan hardcode 0)
- [x] Tombol "Buat Estimate Baru" (`action_create_estimate`) + "Pilih sebagai Baseline" (`action_select_baseline`) — **diverifikasi** end-to-end via shell, termasuk auto-generate nomor revisi EST-001/EST-002
- [x] Security access untuk `vessel.voyage.estimate`
- [x] Dummy data: 2 revisi estimate untuk `demo_contract_voyage_out_1` (beda harga bunker FO 650→720, DO 900→950), rev2 di-set `selected`

### Blocker & Resolusi
Tidak ada blocker baru di sprint ini — proses lancar berkat pelajaran RNG schema dari Sprint 2.

### Verifikasi
- ✅ Install/upgrade bersih tanpa ERROR/CRITICAL
- ✅ Idempotent — re-run `-u`, count estimate tetap 2
- ✅ `total_voyage_days` terhitung benar: 350nm/(8kn×24) + 2 + 1.5 = 5.323 hari
- ✅ `revenue_estimate` terhitung benar dari `contract_id.freight_amount_estimate` (12.5 × 7500 = 93750)
- ✅ `tce_per_day` masuk akal (~16.6k USD/day), beda tipis antar revisi sesuai perbedaan harga bunker
- ✅ Constraint single-selected — `action_select_baseline` swap otomatis benar, force-write manual kedua kali raise error
- ✅ `action_create_estimate` dari kontrak — auto-generate nomor revisi benar (EST-001 untuk kontrak yang belum punya estimate)

### Catatan
- `usd_rate` default menggunakan asumsi representasi `res.currency.rate.rate` = company_currency per unit foreign currency (invers) — perlu dicek ulang saat company currency benar-benar IDR di data produksi nyata (saat ini `My Company` default currency masih USD di database dev, jadi `_default_usd_rate` return 0.0 karena `usd == company_currency`). **Update: sudah diperbaiki di entry "Setup Tambahan — Lokalisasi Indonesia" di bawah.**

---

## Setup Tambahan — Lokalisasi Indonesia (Currency IDR + CoA) — 2026-07-02

Atas instruksi user: company default currency diubah ke IDR, dan modul terkait accounting pakai default Indonesia.

- `res.company` (My Company): `country_id` → Indonesia, `currency_id` → IDR (sebelumnya USD/United States, default Odoo demo)
- Install modul `l10n_id` (Chart of Accounts Indonesia, tersedia di Community)
- Load chart template `id` via `account.chart.template.try_loading('id', ...)` — 51 akun generic lama dihapus otomatis, diganti 118 akun CoA Indonesia + 16 tax + 8 journal
- Seed dummy kurs USD/IDR (`res.currency.rate`, rate 1 USD = 16.250 IDR, sesuai angka contoh acceptance criteria §10.5 tech spec) — dipindah ke `data/vessel_chartering_demo.xml` (xmlid `demo_currency_rate_usd`) supaya reproducible & idempotent, bukan cuma perubahan ad-hoc di database

### Verifikasi
- ✅ `vessel_chartering` tetap install/upgrade bersih setelah perubahan currency & CoA
- ✅ `_default_usd_rate()` di `vessel.voyage.estimate` sekarang mengembalikan nilai riil (16250.0) alih-alih 0.0 — dites dengan create estimate baru, lalu rollback
- ✅ Idempotent — re-run `-u`, jumlah currency rate USD tetap 1 (tidak duplikat)

### Catatan
- Perubahan currency/CoA ini di level **database/environment**, bukan di level kode modul (`vessel.company`/`account.chart.template` bukan tanggung jawab `vessel_chartering`) — tidak ada file baru di modul untuk ini kecuali seed rate dummy
- Field `currency_id` di `vessel.charter.contract` tetap default **USD** (bukan ikut company currency) — sengaja, sesuai §2.4 tech spec: "Freight rate, hire rate, demurrage rate dalam USD (praktik pasar)" — ini keputusan bisnis charter party, independen dari currency fungsional perusahaan

---

## Sprint 4 — Laytime, SOF & Demurrage/Despatch Calculator — 2026-07-02

**Status**: ✅ Done — bagian paling kompleks tech spec, semua acceptance criteria §10.3/§10.4/§10.9 terpenuhi.

### Task Selesai
- [x] Model `vessel.sof.line` — datetime_start/end, duration_hours (compute), interruption_type_id, is_counting (compute), constraint dates + overlap warning (bukan blokir)
- [x] Model `vessel.laytime.calculation` — NOR tendered/accepted, laytime_commenced (compute editable-override dari nor_accepted+turn_time), laytime_allowed_hours (default via onchange sesuai port_call_type), state draft→submitted→approved
- [x] **Compute `laytime_used_hours`** — implementasi presisi aturan "once on demurrage, always on demurrage": iterasi SOF terurut waktu, exclude non-counting SEBELUM threshold tercapai, sertakan SEMUA waktu (termasuk non-counting) SETELAH threshold tercapai
- [x] Compute `balance_hours`, `time_on_demurrage_hours`, `demurrage_amount`, `despatch_amount`
- [x] State machine: submit (siapa saja) → approve (**hanya Chartering Manager**, dicek via `has_group`)
- [x] Reversible laytime: agregasi di kontrak level (`_compute_demurrage_despatch_totals`) — jika `laytime_reversible=True` dan >1 record approved, gabung balance load+discharge dulu sebelum hitung $; jika tidak, sum langsung per-record
- [x] `laytime_ids` di kontrak, smart button count real, tab Laytime di form kontrak (list + tombol Buat Laytime Baru + total agregasi)
- [x] Security access untuk `vessel.laytime.calculation` & `vessel.sof.line`
- [x] Views: form dengan SOF inline editable list + panel ringkasan, list view, menu Operasional → Laytime Calculations
- [x] Dummy data: skenario **persis replikasi acceptance criteria §10.3/10.4** — allowed=96h, SOF 6 baris termasuk 2 interupsi hujan (satu sebelum, satu sesudah titik on-demurrage), hasil used=132h, balance=-36h, demurrage=USD 15.000 (rate 10.000/day)
- [x] **4 unit test `TransactionCase`** (`tests/test_laytime_calculation.py`), semua pass 0 failed/0 error:
  1. Tanpa interupsi — used=durasi total, balance & demurrage benar
  2. Interupsi sebelum on-demurrage — dikecualikan dari used
  3. Interupsi sesudah on-demurrage — **tetap dihitung** (once-on-demurrage), demurrage_amount persis USD 15.000
  4. Agregasi kontrak non-reversible — `demurrage_amount_total` match

### Blocker & Resolusi
- **`decoration-secondary` kepakai lagi tanpa sadar** di list view laytime (lupa pelajaran Sprint 2) — ketemu & fix sebelum install (bukan dari error install, dari review manual). Dicatat lagi supaya benar-benar melekat.
- **`docker compose exec odoo odoo --test-enable ...` gagal "Address already in use" (port 8069)** — container utama sudah bind port itu; command test terpisah juga mencoba bind port yang sama meski pakai `--stop-after-init`. **Resolusi**: tambahkan `--http-port=8070` khusus untuk run test/one-off command yang tidak perlu HTTP.
- **`res.users.groups_id` AttributeError** — field ini di-rename jadi **`group_ids`** di Odoo 19 (breaking change dari versi lama). Test yang assign group ke `env.user` gagal sampai field name diperbaiki.
- **`assertAlmostEqual` gagal karena Monetary rounding** — field Monetary Odoo otomatis dibulatkan ke presisi currency (2 desimal USD), sedangkan raw Python float division punya lebih banyak desimal. **Resolusi**: tambahkan `places=2` di assertion yang membandingkan nilai Monetary.

### Verifikasi
- ✅ Install/upgrade bersih tanpa ERROR/CRITICAL
- ✅ Idempotent — re-run `-u`, count laytime tetap 1, SOF line tetap 6
- ✅ Dummy data database: `laytime_used=132, balance=-36, time_on_demurrage=36, demurrage_amount=15000.00` — **persis** acceptance criteria §10.4
- ✅ 4/4 unit test pass (0 failed, 0 error) — acceptance criteria §10.3 (3 test case) dan §10.9 (semua test lulus) terpenuhi
- ✅ `action_approve` hanya bisa oleh Chartering Manager — diverifikasi via test (perlu grant group eksplisit ke test user karena TransactionCase default user tidak otomatis anggota custom group)

### Catatan
- **Pelajaran baru dicatat untuk sprint berikutnya**: (1) Odoo 19 rename `res.users.groups_id` → `group_ids`; (2) test run one-off perlu `--http-port` custom untuk hindari port conflict dengan container utama; (3) `decoration-secondary` masih harus diwaspadai — pertimbangkan audit grep di Sprint 7 untuk pastikan tidak kepakai lagi di file manapun

---

## Sprint 5 — Time Charter: Hire Statement & Off-hire — 2026-07-02

**Status**: ✅ Done

### Task Selesai
- [x] Model `vessel.offhire.event` — duration_hours (compute), reason (breakdown/drydock/crew/deficiency/other), fuel_deduction
- [x] Model `vessel.hire.statement.line` — days_in_period, offhire_hours (compute dengan **partial overlap proportional**, bukan all-or-nothing), net_hire_days, hire_amount, cve_amount (pro-rata basis 30 hari), bunker_adjustment (manual), total_amount
- [x] Update kontrak: `offhire_ids`, `hire_statement_ids`, `total_offhire_hours` (compute real, sebelumnya placeholder 0.0 dari Sprint 2)
- [x] `action_generate_hire_statement` — periode lanjut otomatis dari statement terakhir (atau delivery_date/date_start jika belum ada), constraint `_check_no_duplicate_period` cegah duplikat
- [x] Security access untuk 2 model baru
- [x] Views: tab "Hire & Off-hire" di form kontrak (offhire inline editable + hire statement list read-only + tombol generate)
- [x] Dummy data: **persis replikasi acceptance criteria §10.6** — hire statement 15 hari (27 Jun - 12 Jul), off-hire 12 jam penuh di dalam periode → net_hire_days = 14.5
- [x] **3 unit test `TransactionCase`** (`tests/test_hire_statement.py`), semua pass:
  1. net_hire_days = 14.5 persis (acceptance criteria §10.6)
  2. Off-hire partial overlap (event mulai sebelum periode, berakhir di dalam periode) → hanya porsi overlap (6 dari 12 jam) yang dihitung, bukan all-or-nothing
  3. `action_generate_hire_statement` — periode berurutan otomatis benar, constraint tolak duplikat periode

### Blocker & Resolusi
Tidak ada blocker baru — pelajaran dari Sprint 2/4 (RNG schema, `group_ids`, `--http-port` test) diterapkan sejak awal, proses lancar tanpa iterasi ulang.

### Verifikasi
- ✅ Install/upgrade bersih tanpa ERROR/CRITICAL
- ✅ Idempotent — re-run `-u`, count hire statement & offhire tetap 1
- ✅ Dummy data database: `days_in_period=15, offhire_hours=12, net_hire_days=14.5, hire_amount=116000.00` (14.5 × 8000) — **persis** acceptance criteria §10.6
- ✅ 7/7 unit test pass (0 failed, 0 error) — gabungan Sprint 4 (4 test) + Sprint 5 (3 test), tidak ada regresi

### Catatan
- `cve_amount` pro-rata pakai basis 30 hari (bukan 30.44 hari/bulan rata-rata kalender) — simplifikasi MVP, cukup akurat untuk keperluan estimasi
- Tidak ada form view terpisah untuk `vessel.hire.statement.line`/`vessel.offhire.event` (cuma inline di tab kontrak) — sesuai scope sprint file, Odoo auto-generate form generik jika user klik row

---
