# Odoo Shipping Vertical Solution — Odoo untuk industri pelayaran Indonesia

## Project Overview
Odoo Shipping adalah kumpulan modul custom Odoo 19 untuk perusahaan pelayaran/fleet Indonesia (kendaraan darat & kapal laut) — coal/cargo shipping, chartering, dan asset management armada. Dikembangkan Sunartha ERP Consulting sebagai vertical solution generik, bukan untuk satu klien spesifik.

- **Platform**: Odoo 19.0 **Community** (lokal), Python 3.12
- **Database**: PostgreSQL 16
- **Runtime lokal**: Docker Compose (`docker-compose.yml` di root) — `docker compose up -d`, akses di `http://localhost:8069`, database dev: `shipping_dev`
- **Company & Accounting**: company default = Indonesia, currency **IDR**, Chart of Accounts `l10n_id` (118 akun, 16 tax, 8 journal). Kontrak charter (`vessel.charter.contract.currency_id`) tetap default **USD** — sengaja beda dari company currency, sesuai praktik pasar charter party (§2.4 tech spec). Ada dummy kurs USD/IDR (16.250) di demo data `vessel_chartering` untuk testing.
- **Package manager**: tidak ada (struktur modul Odoo standar — folder per modul dengan `__manifest__.py`)
- **Lisensi modul**: LGPL-3

## Struktur Modul (Layer 1 — Asset Management, sudah ada)
| Modul | Fungsi |
|---|---|
| `fleet_document_id` | Dokumen legal kendaraan darat & kapal (STNK, BKI, Sijil, dll) |
| `fleet_fuel_log` | Pencatatan BBM & konsumsi, trip/voyage |
| `fleet_maintenance_schedule` | Jadwal maintenance armada |
| `fleet_model_sparepart` | Master sparepart kapal |
| `vessel_crew_management` | Manajemen ABK — sign on/off, STCW, crew scheduling |
| `acc_id_multicurrency_report` | Laporan keuangan dual-currency IDR/USD (tidak spesifik shipping) |
| `shopify_connector_v19` | Integrasi Shopify (tidak spesifik shipping) |

Layer 2 (Komersial):
- `vessel_chartering` — **selesai** (MVP 7 sprint, lihat `TECH_SPEC_vessel_chartering.md`)
- `vessel_voyage_operations` — **sedang dikembangkan** (roadmap #2, setelah `vessel_chartering`), lihat `TECH_SPEC_vessel_voyage_operations.md`. Hard dependency ke `vessel_chartering`.

Ringkasan fitur & tujuan bisnis tiap modul fleet: lihat `FLEET_MODULES_OVERVIEW.md`.

## Source Documentation
- Tech spec `vessel_chartering`: `TECH_SPEC_vessel_chartering.md`
- Tech spec `vessel_voyage_operations`: `TECH_SPEC_vessel_voyage_operations.md`
- Overview modul fleet existing: `FLEET_MODULES_OVERVIEW.md`
- Pengetahuan Odoo 19 (ORM, views, security, dll): gunakan skill `odoo-19` jika tersedia

## Sprint Tracker
Status sprint saat ini tersimpan di: `sprints/.current_sprint`
- File berisi angka sprint yang sedang aktif (1-N)
- Jika file tidak ada, mulai dari Sprint 1
- Breakdown sprint: `sprints/sprint_NN.md`

## Command Sunartha (.claude/commands/)

Semua command dari `D:\Sunartha Claude Skills\commands\` (`sunartha-claude-skills-dev`) sudah di-install ke `.claude/commands/` project ini. **Mulai sekarang pakai versi lokal ini, jangan lagi rujuk path eksternal.**

- `sprint.md`, `retro.md` — **sudah diadaptasi** untuk konteks Odoo/Windows (lihat isi file, beda dari sumber asli)
- `devops.md`, `docs.md`, `improve.md`, `pm.md`, `qa.md`, `release.md`, `review.md`, `security.md`, `ux.md` — **masih raw/belum diadaptasi**, di-copy apa adanya dari sumber. Sebelum benar-benar dipakai, cek dulu apakah pre-flight check/asumsi tech stack-nya cocok (kemungkinan besar tidak — sama seperti `sprint.md`/`retro.md` sebelum diadaptasi: asumsi `backend/`+`uv`+pytest, `frontend/`+pnpm, email via AppleScript+Mail.app macOS). `ux.md` kemungkinan besar **tidak relevan sama sekali** untuk project ini (Odoo backend module dev, bukan custom frontend web app).

## Mode Eksekusi Sprint: CHECKPOINT (bukan autonomous)

Berbeda dari default `/sprint` skill (yang jalan tanpa henti sampai semua sprint selesai), project ini pakai mode **checkpoint per sprint**:
1. Jalankan seluruh task di satu file `sprints/sprint_NN.md`
2. Jalankan verifikasi & Definition of Done
3. Update `SPRINT_REPORT.md` (bukan email — lihat bagian Reporting di bawah)
4. Commit ke git
5. **Berhenti, tunggu review/approval user sebelum lanjut ke sprint berikutnya** — jangan auto-lanjut

## Reporting

Setiap sprint selesai (atau ada progress signifikan), update `SPRINT_REPORT.md` di root:
- Tambahkan entry baru di **bawah** (kronologis, bukan di atas)
- Format: nama sprint, tanggal, task selesai, blocker ditemukan (+ cara resolve), hasil verifikasi

**Email notifikasi**: tidak pakai AppleScript+Mail.app (macOS-only, tidak jalan di sini) — pakai Outlook desktop via PowerShell COM automation (`scripts/send_sprint_email.ps1`). Default: To `eliano@sunartha.co.id`, Cc `daru@sunartha.co.id`. Prasyarat: Outlook desktop harus running (script auto-launch jika belum).

**PENTING — jangan kirim email otomatis, dan urutan tanya ke user WAJIB: email dulu, baru lanjut sprint.** Siapkan body email & laporkan sprint selesai ke user via chat, lalu tanya dua hal secara terpisah dan berurutan: (1) apakah email mau dikirim sekarang, (2) baru setelah itu apakah mau lanjut ke sprint berikutnya. Jangan gabung jadi satu pertanyaan, dan jangan lompat ke pertanyaan lanjut-sprint sebelum urusan email selesai ditanyakan. Ini dikoreksi user setelah Sprint 4 (awalnya email dikirim otomatis) dan Sprint 5 (urutan tanya diperjelas).

## Konvensi Kode (Odoo Module Development)

- Python 3.12, ikuti pola yang sudah ada di 5 modul existing: `mail.thread`/`mail.activity.mixin` untuk model transaksional, state machine dengan tombol aksi eksplisit, `@api.depends` selalu terisi (jangan kosong), jangan pakai `display_name` sebagai nama field custom
- `ir.model.access.csv` — selalu pakai prefix modul pada xmlid group reference
- Field `company_id` wajib di model yang butuh multi-company
- Cron job untuk notifikasi proaktif (expiry, reminder) — pola sudah mapan di modul existing
- Jangan buat file dokumentasi/komentar berlebih kecuali diminta

### Checklist Odoo 19 Gotcha (WAJIB grep sebelum install, bukan diandalkan dari ingatan)
<!-- improved: retro Sprint 1-7 vessel_chartering — "pelajaran" yang cuma ditulis sebagai prosa di
     SPRINT_REPORT.md terbukti gampang lupa (decoration-secondary kepakai lagi persis di Sprint 4
     padahal sudah jadi blocker di Sprint 2). Checklist ini dimaksud untuk di-grep aktif via
     Pre-flight sprint.md, bukan cuma dibaca (2026-07-03) -->

| Pola lama (Odoo <19 / kebiasaan lama) | Yang benar di Odoo 19 |
|---|---|
| `decoration-secondary` di list/kanban view | Tidak valid — cuma `muted`/`info`/`warning`/`success`/`danger` |
| `<group expand="0" string="Group By">` di search view | Atribut `string`/`expand` tidak valid di `<group>` search view — hapus, cukup `<group>` polos |
| `res.users.groups_id` | Rename jadi `res.users.group_ids` |
| Field custom modul lain diasumsikan ada tanpa dicek | Grep dulu source model di container sebelum pakai (`docker compose exec odoo grep ...`) — pernah salah asumsi `invoice_policy` ada di core `product.product` (padahal punya modul `sale`) |
| Xpath target `res.config.settings` ditebak dari nama block yang "masuk akal" | Grep dulu `<block ... id="...">` di source view sebelum nulis xpath — pernah salah tebak `invoicing_policy` (harusnya `invoicing_settings`) |
| `_sql_constraints = [(name, sql, message), ...]` (list attribute) | **Silent no-op di Odoo 19** — tidak error, tidak warning, constraint DB memang tidak pernah ter-apply. Ganti `models.Constraint('sql...', 'message')` sebagai atribut kelas terpisah (lihat `odoo/addons/base/models/res_lang.py` untuk contoh). Ditemukan Sprint 11 `vessel_voyage_operations` — juga terbukti mengenai `vessel_seafarer.py` (`vessel_crew_management`, pre-existing, belum diperbaiki — di luar scope sprint ini). **Paling berbahaya di tabel ini karena tidak muncul di log sama sekali** — hanya ketahuan lewat unit test yang sengaja menguji constraint-nya. |

Kalau nemu pola baru yang bikin blocker berulang (≥2x kejadian), tambahkan baris baru ke tabel ini — jangan cuma catat di SPRINT_REPORT.md.

## Git

- Remote: repo GitHub pribadi (fresh start, tanpa histori GitLab lama) — lihat commit awal untuk baseline
- Commit setelah setiap sprint selesai (bukan per task kecil)
- Format commit: `feat(sprint-N): [deskripsi]`
- **Jangan pernah force-push atau amend commit yang sudah ada tanpa izin eksplisit**

## Docker

```bash
docker compose up -d          # start Odoo + Postgres
docker compose logs odoo -f   # lihat log
docker compose exec odoo odoo --stop-after-init -d shipping_dev --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo -i <module1>,<module2> --without-demo=True   # install/update modul
docker compose exec db psql -U odoo -d shipping_dev   # akses database langsung
docker compose exec odoo odoo --stop-after-init -d shipping_dev --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo --http-port=8070 --test-enable --test-tags <module> -u <module>   # run unit test — WAJIB --http-port beda (container utama sudah pakai 8069, port conflict kalau tidak)
```

`MSYS_NO_PATHCONV=1` wajib di-prefix untuk command `docker compose exec` di Git Bash Windows (mencegah path translation salah pada `/etc/...`, `/mnt/...`, dll).

## Penting
- Jika ada keputusan desain yang genuinely ambigu (bukan cuma detail implementasi), **tanya user** — jangan asumsi diam-diam, terutama untuk hal yang disebut "Pertanyaan Terbuka" di tech spec
- Data dummy/master data untuk testing wajib disertakan tiap sprint yang relevan (lihat instruksi user)

# userEmail
eliano@sunartha.co.id
