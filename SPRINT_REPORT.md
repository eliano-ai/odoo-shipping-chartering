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
