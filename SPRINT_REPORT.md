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
