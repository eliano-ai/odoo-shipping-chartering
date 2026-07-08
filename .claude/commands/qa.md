# QA — Quality Assurance Agent (Odoo Module Dev)

Kamu adalah Senior QA Engineer yang memastikan seluruh modul Odoo custom teruji dengan baik. Jalankan semua langkah tanpa menunggu konfirmasi, KECUALI Langkah 7 (Git Commit) yang wajib tanya dulu — ini bukan mode autonomous sprint.

Diadaptasi dari `sunartha-claude-skills-dev` (`D:\Sunartha Claude Skills\commands\qa.md`) untuk konteks Odoo module dev — versi asli asumsi backend FastAPI+pytest+uv dan frontend React+Vitest+pnpm, **tidak ada satupun yang berlaku di project ini**. Test di sini adalah `odoo.tests.TransactionCase`/`tagged` per modul, dijalankan via `docker compose exec` — tidak ada `coverage.py`/`pytest-cov` yang terintegrasi.

## Cara Memanggil

```
/qa run       → Jalankan seluruh unit test tiap modul custom yang punya folder tests/, laporkan hasil
/qa audit     → Audit kondisi test suite tanpa menjalankan test (cross-reference model vs test coverage)
/qa write     → Tulis TransactionCase test untuk model/action method yang belum tercover (dari hasil audit)
```

Jika dipanggil tanpa argumen (`/qa`), jalankan `audit` (bukan `run` — audit tidak menyentuh docker/database, jauh lebih cepat dan aman sebagai default).

`/qa coverage` dan `/qa e2e` dari versi asli **tidak diadaptasi** — tidak ada tooling coverage terintegrasi untuk Odoo di environment ini, dan tidak ada E2E test framework terpasang (Odoo Enterprise `hoot`/tour test butuh setup terpisah, di luar scope). Kalau user minta salah satunya, jelaskan gap ini dan tawarkan `audit` sebagai pendekatan manual terdekat.

---

## Langkah 1 — Baca Konfigurasi Project & Daftar Modul

Baca `CLAUDE.md`. Daftar modul custom di project ini (Layer 1 Asset Management + Layer 2 Komersial + Layer 3 Finansial):

```bash
MODULES="fleet_document_id fleet_fuel_log fleet_maintenance_schedule fleet_model_sparepart vessel_crew_management acc_id_multicurrency_report shopify_connector_v19 maritime vessel_chartering vessel_voyage_operations vessel_voyage_pnl vessel_bunker_management"

for m in $MODULES; do
  echo "=== $m ==="
  ls "$m/tests/" 2>/dev/null || echo "  (tidak ada folder tests/)"
done
```

Modul Layer 1 (`fleet_document_id`, `fleet_fuel_log`, `fleet_maintenance_schedule`, `fleet_model_sparepart`, `vessel_crew_management`) dan 2 modul generik (`acc_id_multicurrency_report` — tidak spesifik shipping, `shopify_connector_v19`) dikembangkan **sebelum** roadmap sprint terstruktur project ini dimulai — kemungkinan besar tidak punya `tests/` sama sekali kecuali `acc_id_multicurrency_report`. Ini bukan kesalahan sprint manapun, cukup dicatat sebagai gap pre-existing di laporan, jangan diperlakukan sebagai "regresi".

---

## Langkah 2 — Subcommand: `run`

**Tujuan**: Jalankan seluruh unit test modul yang punya folder `tests/`, tampilkan hasil lengkap per modul.

```bash
docker compose ps
curl -s -o /dev/null -w "Odoo HTTP: %{http_code}\n" http://localhost:8069/web/login
```

Jika container tidak running, `docker compose up -d` dan tunggu healthy dulu.

**WAJIB sekuensial, satu modul per satu command** — semua share `--http-port=8070` dan database `shipping_dev` yang sama; menjalankan paralel berisiko row-lock contention (`could not serialize access due to concurrent update` pada `ir_cron`, pernah terjadi di sesi `vessel_bunker_management` Sprint 26).

```bash
for m in <daftar modul yang punya folder tests/>; do
  echo "=== $m ==="
  MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
    --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
    --http-port=8070 --test-enable --test-tags $m -u $m 2>&1 | grep -E "FAIL|ERROR|tests when loading"
done
```

Jika ada test **failed**/**error**:
1. Baca traceback lengkap (cari baris `File ".../<modul>/tests/..."`)
2. Cari root cause — cek dulu apakah ini regresi demo-data lifecycle (pola sudah dikenal project ini, lihat CLAUDE.md/RETRO.md: hardcode state/period yang stale karena demo data terus berkembang antar sprint) sebelum menyimpulkan bug baru
3. Perbaiki jika penyebabnya jelas
4. Jika butuh perubahan logic signifikan atau keputusan desain, catat sebagai temuan di laporan akhir, **jangan ubah tanpa konfirmasi** (beda dari mode autonomous sprint)

---

## Langkah 3 — Subcommand: `audit`

**Tujuan**: Laporan kondisi test suite tanpa menjalankan test atau mengubah kode/database — aman dan cepat, tidak butuh docker exec sama sekali kecuali untuk menghitung file.

### 3.1 — Statistik per Modul

```bash
for m in $MODULES; do
  n_models=$(find "$m/models" -name "*.py" ! -name "__init__.py" 2>/dev/null | wc -l | tr -d ' ')
  n_test_files=$(find "$m/tests" -name "test_*.py" 2>/dev/null | wc -l | tr -d ' ')
  n_test_methods=$(grep -rh "def test_" "$m/tests/"*.py 2>/dev/null | wc -l | tr -d ' ')
  echo "$m: $n_models model file(s), $n_test_files test file(s), $n_test_methods test method(s)"
done
```

### 3.2 — Cross-Reference Model vs Test Coverage

Untuk tiap model **custom** (bukan model core Odoo yang cuma di-`_inherit`), cek apakah nama model itu disebut minimal sekali di test file modul yang sama:

```bash
for m in $MODULES; do
  for model_file in "$m"/models/*.py; do
    [ "$(basename "$model_file")" = "__init__.py" ] && continue
    model_name=$(grep -oP "_name\s*=\s*'\K[^']+" "$model_file" | head -1)
    [ -z "$model_name" ] && continue  # file cuma _inherit tanpa _name baru, skip
    if ! grep -rq "$model_name" "$m"/tests/*.py 2>/dev/null; then
      echo "NO TEST COVERAGE: $m / $model_name ($(basename $model_file))"
    fi
  done
done
```

Catatan: ini heuristik kasar (cek model NAME disebut, bukan tiap method/compute field) — cukup untuk identifikasi gap besar (model tanpa test sama sekali), bukan pengganti code review mendalam.

### 3.3 — Cross-Check Acceptance Criteria vs Test Docstring

Untuk modul yang punya tech spec dengan §10 Kriteria Penerimaan (`vessel_chartering`, `vessel_voyage_operations`, `vessel_voyage_pnl`, `vessel_bunker_management`), pola project ini SELALU menulis referensi `§10.X` di docstring test yang relevan — cross-check tiap poin acceptance criteria benar-benar disebut minimal satu test:

```bash
for m in vessel_chartering vessel_voyage_operations vessel_voyage_pnl vessel_bunker_management; do
  echo "=== $m ==="
  grep -oP "§10\.\d+" TECH_SPEC_$m.md 2>/dev/null | sort -u | while read -r poin; do
    grep -rq "$poin" "$m"/tests/*.py 2>/dev/null && echo "  $poin: OK" || echo "  $poin: TIDAK DISEBUT DI TEST MANAPUN"
  done
done
```

### 3.4 — Action Method Group-Gated Tanpa Test `with_user()`

Pola established project ini: action method yang di-guard `has_group(...)` wajib diuji minimal 1x dengan `with_user()` memverifikasi user tanpa grup dapat `UserError`/`AccessError` (lihat CLAUDE.md soal `has_group()` gagal di demo-context). Cek model dengan `has_group` di kode tapi tidak ada `with_user` di test:

```bash
for m in $MODULES; do
  for model_file in "$m"/models/*.py; do
    if grep -q "has_group(" "$model_file" 2>/dev/null; then
      if ! grep -rq "with_user" "$m"/tests/*.py 2>/dev/null; then
        echo "GUARD TANPA TEST with_user(): $m / $(basename $model_file)"
      fi
    fi
  done
done
```

### 3.5 — Tulis/Update `QA_STATUS.md`

```markdown
# QA Status
**Last Check**: [tanggal]
**Project**: Odoo Shipping Vertical Solution

## Summary per Modul

| Modul | Model Files | Test Files | Test Methods | Model Tanpa Test |
|-------|------------|-----------|--------------|-------------------|
| vessel_bunker_management | N | N | N | 0 |
| ... | | | | |

## Gap Kritis (model tanpa test sama sekali)
- [list dari 3.2]

## Acceptance Criteria Tanpa Referensi Test
- [list dari 3.3, kalau ada]

## Action Method Guard Tanpa Test with_user()
- [list dari 3.4, kalau ada]

## Modul Tanpa Folder tests/ Sama Sekali
- [list — biasanya modul Layer 1 pre-existing, catat sebagai gap pre-existing bukan regresi]

## Rekomendasi
Jalankan `/qa run` untuk eksekusi test yang sudah ada, atau `/qa write` untuk isi gap di atas.
```

---

## Langkah 4 — Subcommand: `write`

**Tujuan**: Tulis test `TransactionCase` baru untuk model/method yang di-flag `audit` sebagai tanpa coverage, mengikuti pola project existing — **bukan** template pytest/FastAPI generik.

### 4.1 — Identifikasi Target

Ambil hasil Langkah 3.2/3.4 (`audit`), prioritaskan: model dengan constraint/compute field kompleks, action method dengan state machine, action method group-gated.

### 4.2 — Pola Test yang Sudah Mapan di Project Ini

Baca 1-2 file test existing di modul yang sama dulu untuk konsistensi gaya (`setUp` biasanya `self.env.ref(...)` ke demo data, bukan bikin fixture generik dari nol):

```python
# <modul>/tests/test_<nama>.py
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class Test<Nama>(TransactionCase):

    def setUp(self):
        super().setUp()
        # Reuse demo data via self.env.ref(...) kalau ada, baru create() manual
        # untuk skenario yang butuh state awal berbeda dari demo.

    def test_constraint_<nama>(self):
        """Constraint <nama> - <alasan constraint ada>."""
        with self.assertRaises(ValidationError):
            self.env['<model>'].create({...})  # data yang seharusnya melanggar constraint

    def test_action_<nama>_group_guard(self):
        """§10.X (kalau ada referensi acceptance criteria) - group_xxx_user tidak
        boleh <aksi>."""
        test_user = self.env['res.users'].create({
            'name': 'Test User', 'login': 'test_qa_user',
            'group_ids': [(6, 0, [self.env.ref('<modul>.group_xxx_user').id, self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(UserError):
            record.with_user(test_user).action_<nama>()
```

**Wajib cover untuk tiap model baru**:
1. Constraint (kalau ada `models.Constraint`/`@api.constrains`) — kasus yang melanggar HARUS raise
2. Compute field kunci (formula bisnis, mis. variance/settlement amount) — nilai eksak, bukan cuma "tidak error"
3. Action method state transition (state awal salah → `UserError`)
4. Action method group-gated → `with_user()` non-member harus gagal

### 4.3 — Jalankan Test Satu-Per-Satu Saat Ditulis

Sama seperti aturan `sprint.md` — tulis SATU test, jalankan (`--test-tags <modul>`), baru lanjut ke berikutnya. Jangan tulis seluruh batch dulu lalu debug massal.

---

## Langkah 5 — Verifikasi Akhir

Setelah menulis test baru, jalankan ULANG SELURUH suite modul yang disentuh (bukan cuma test baru) — demo data yang di-extend antar sprint di project ini sudah beberapa kali membuat test lama jadi stale:

```bash
MSYS_NO_PATHCONV=1 docker compose exec odoo odoo --stop-after-init -d shipping_dev \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo \
  --http-port=8070 --test-enable --test-tags <modul> -u <modul> 2>&1 | grep -E "FAIL|ERROR|tests when loading"
```

---

## Langkah 6 — Git Commit (WAJIB TANYA DULU, jangan auto-commit)

Beda dari versi generic skill ini (yang auto-commit) — project ini pakai aturan global: **jangan commit kecuali user eksplisit minta**. `/qa audit` (read-only, cuma tulis `QA_STATUS.md`) dan `/qa run` (tidak mengubah kode) TIDAK perlu commit sama sekali kecuali user minta `QA_STATUS.md` disimpan ke git. `/qa write` (nulis test baru) baru relevan untuk commit — tapi tetap tanya dulu, jangan asumsi.

Kalau user setuju commit:
```bash
git add <path test file yang ditulis> QA_STATUS.md
git commit -m "test(qa): [ringkasan — misal: tambah test coverage vessel.bunker.survey constraint & group guard]

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Langkah 7 — Laporan ke User

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧪 QA REPORT — [SUBCOMMAND]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Modul dianalisis  : N
Test files        : N total, N method
Model tanpa test  : N (lihat detail di bawah/QA_STATUS.md)
Acceptance crit.  : N/N poin §10 punya referensi test (kalau audit mencakup ini)

Gap kritis:
• [list model/method paling penting tanpa test]

QA_STATUS.md ✓ diupdate (kalau subcommand audit)

Langkah selanjutnya:
• /qa write   → tulis test untuk gap di atas
• /qa run     → eksekusi seluruh test yang sudah ada
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Catatan Reusability

Skill ini bekerja selama:
1. Project pakai struktur modul Odoo standar (folder per modul dengan `models/`, `tests/`, `__manifest__.py`)
2. Test pakai `odoo.tests.TransactionCase`/`tagged`, dijalankan via `docker compose exec odoo ... --test-tags`
3. Ada `CLAUDE.md` dengan daftar modul & konvensi kode

Tidak butuh `backend/`/`frontend/` folder split, `pytest`/`Vitest`, atau `uv`/`pnpm` — semuanya digantikan pola Odoo native di atas.