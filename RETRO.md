# Retro Log
<!-- Dikelola otomatis oleh Retro Agent. Entry baru ditambahkan di atas. -->

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
