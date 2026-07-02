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

Layer 2 (Komersial, **sedang dikembangkan**): `vessel_chartering` — lihat `TECH_SPEC_vessel_chartering.md` untuk spesifikasi lengkap.

Ringkasan fitur & tujuan bisnis tiap modul fleet: lihat `FLEET_MODULES_OVERVIEW.md`.

## Source Documentation
- Tech spec modul aktif: `TECH_SPEC_vessel_chartering.md`
- Overview modul fleet existing: `FLEET_MODULES_OVERVIEW.md`
- Pengetahuan Odoo 19 (ORM, views, security, dll): gunakan skill `odoo-19` jika tersedia

## Sprint Tracker
Status sprint saat ini tersimpan di: `sprints/.current_sprint`
- File berisi angka sprint yang sedang aktif (1-N)
- Jika file tidak ada, mulai dari Sprint 1
- Breakdown sprint: `sprints/sprint_NN.md`

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

**Email notifikasi**: tidak pakai AppleScript+Mail.app (macOS-only, tidak jalan di sini) — pakai Outlook desktop via PowerShell COM automation (`scripts/send_sprint_email.ps1`). Dikirim otomatis tiap sprint selesai (Langkah 12 di `.claude/commands/sprint.md`). Default: To `eliano@sunartha.co.id`, Cc `daru@sunartha.co.id`. Prasyarat: Outlook desktop harus running (script auto-launch jika belum).

## Konvensi Kode (Odoo Module Development)

- Python 3.12, ikuti pola yang sudah ada di 5 modul existing: `mail.thread`/`mail.activity.mixin` untuk model transaksional, state machine dengan tombol aksi eksplisit, `@api.depends` selalu terisi (jangan kosong), jangan pakai `display_name` sebagai nama field custom
- `ir.model.access.csv` — selalu pakai prefix modul pada xmlid group reference
- Field `company_id` wajib di model yang butuh multi-company
- Cron job untuk notifikasi proaktif (expiry, reminder) — pola sudah mapan di modul existing
- Jangan buat file dokumentasi/komentar berlebih kecuali diminta

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
```

`MSYS_NO_PATHCONV=1` wajib di-prefix untuk command `docker compose exec` di Git Bash Windows (mencegah path translation salah pada `/etc/...`, `/mnt/...`, dll).

## Penting
- Jika ada keputusan desain yang genuinely ambigu (bukan cuma detail implementasi), **tanya user** — jangan asumsi diam-diam, terutama untuk hal yang disebut "Pertanyaan Terbuka" di tech spec
- Data dummy/master data untuk testing wajib disertakan tiap sprint yang relevan (lihat instruksi user)

# userEmail
eliano@sunartha.co.id
