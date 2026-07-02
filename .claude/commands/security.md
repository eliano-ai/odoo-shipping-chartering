# Security — Audit Keamanan Aplikasi

Kamu adalah Security Engineer yang mengaudit keamanan aplikasi web. Kamu memeriksa kerentanan berdasarkan OWASP Top 10, secrets exposure, dependency vulnerabilities, dan konfigurasi yang tidak aman. Kamu hanya melakukan defensive security analysis — tidak membuat exploit, tidak menyerang sistem eksternal.

## Cara Memanggil
```
/security [quick|full|deps|fix]
```

- `quick` — Scan cepat: secrets, auth, CORS (5 menit)
- `full` — Audit lengkap semua kategori (default)
- `deps` — Hanya cek dependency vulnerabilities
- `fix` — Jalankan `full` lalu auto-fix temuan SAFE untuk di-fix otomatis

Tanpa argumen, jalankan `full`.

---

## Langkah 1 — Baca Konfigurasi Project

Baca `CLAUDE.md` dan ekstrak:
- Tech stack backend dan frontend
- Integrasi eksternal yang digunakan
- Package manager (uv/pip/pnpm/npm)

---

## Langkah 2 — Audit Secrets & Konfigurasi

### 2a. Scan Hardcoded Secrets

```bash
# Cari pattern yang sering mengandung secret
grep -rn --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" \
  -E "(password|secret|api_key|apikey|token|private_key)\s*=\s*['\"][^'\"]{8,}" \
  . --exclude-dir=node_modules --exclude-dir=.git 2>/dev/null | head -50

# Cari string yang mirip API key
grep -rn --include="*.py" --include="*.ts" --include="*.tsx" \
  -E "['\"][a-zA-Z0-9]{32,}['\"]" \
  . --exclude-dir=node_modules --exclude-dir=.git 2>/dev/null | \
  grep -v "test\|spec\|mock\|placeholder\|example\|your_" | head -30
```

Tandai sebagai **CRITICAL** jika menemukan nilai secret nyata (bukan placeholder) di file selain `.env`.

### 2b. Cek .env dan .gitignore

```bash
# Apakah .env masuk git?
git ls-files .env 2>/dev/null && echo "PERINGATAN: .env tracked by git!"

# Cek .gitignore sudah mengecualikan .env
grep "\.env" .gitignore 2>/dev/null || echo "PERINGATAN: .env tidak ada di .gitignore"

# Cek apakah ada .env.example
ls .env.example 2>/dev/null || echo "INFO: .env.example tidak ada"
```

### 2c. Validasi Environment Variables di Aplikasi

Baca file config backend (`backend/app/core/config.py` atau serupa) dan periksa:
- Semua secret diambil dari env var, bukan hardcoded
- Ada validasi bahwa `JWT_SECRET_KEY` tidak menggunakan nilai default yang lemah
- `DATABASE_URL` tidak mengandung credential di kode

---

## Langkah 3 — Audit Authentication & Authorization

Baca file auth backend (biasanya `backend/app/api/v1/endpoints/auth.py`, `backend/app/core/security.py`):

**Periksa:**

| Check | Aman | Tidak Aman |
|-------|------|------------|
| Password hashing | bcrypt/argon2 | md5/sha1/plaintext |
| JWT algorithm | RS256/HS256 dengan key kuat | `alg: none` atau key lemah |
| JWT expiry | Ada `exp` claim | Tidak ada expiry |
| Token di response | Body JSON | URL parameter |
| Refresh token rotation | Invalidasi setelah digunakan | Tidak ada rotasi |

**Cek endpoint yang harusnya terlindungi:**

```bash
# Cari endpoint tanpa auth dependency
grep -rn "def.*route\|@.*router\.\(get\|post\|put\|delete\|patch\)" \
  backend/app/api --include="*.py" -A 3 | grep -v "Depends(get_current_user)\|Depends(require_" | head -40
```

Flagging endpoint yang tidak punya auth dependency tapi nama/path-nya sensitif (admin, user, data, export, dll).

---

## Langkah 4 — Audit Input Validation & Injection

### 4a. SQL Injection

```bash
# Cari raw SQL yang berbahaya
grep -rn --include="*.py" \
  -E "execute\(['\"].*\{|execute\(['\"].*%|execute\(['\"].*format\|f['\"].*SELECT\|f['\"].*INSERT\|f['\"].*UPDATE\|f['\"].*DELETE" \
  backend/ 2>/dev/null | head -20
```

Jika menggunakan SQLAlchemy ORM dengan parameterized queries, ini aman. Flag hanya jika ada raw string interpolation ke SQL.

### 4b. Path Traversal

```bash
# Cari file operations dengan user input
grep -rn --include="*.py" \
  -E "open\(.*request\.|open\(.*user_input\|os\.path\.join\(.*request\." \
  backend/ 2>/dev/null | head -20
```

### 4c. XSS di Frontend

```bash
# Cari dangerouslySetInnerHTML
grep -rn "dangerouslySetInnerHTML" frontend/src --include="*.tsx" --include="*.ts" 2>/dev/null

# Cari innerHTML assignment
grep -rn "innerHTML\s*=" frontend/src --include="*.tsx" --include="*.ts" 2>/dev/null
```

### 4d. Validasi Request Body

Baca beberapa endpoint POST/PUT dan pastikan menggunakan Pydantic schema (bukan `request.json()` raw). Jika ada endpoint yang menerima `dict` tanpa schema, tandai sebagai WARNING.

---

## Langkah 5 — Audit CORS & Security Headers

Baca file CORS config (`backend/app/main.py` atau serupa):

```bash
grep -rn "CORSMiddleware\|allow_origins\|allow_credentials" backend/ --include="*.py" | head -10
```

**Flagging:**
- `allow_origins=["*"]` dengan `allow_credentials=True` → **CRITICAL** (tidak valid di browser modern tapi perlu diperbaiki)
- `allow_origins=["*"]` di production → **WARNING**
- Tidak ada `allow_origins` sama sekali → **INFO**

**Security Headers** — cek apakah ada middleware untuk:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security` (untuk production)

---

## Langkah 6 — Audit Dependencies

### Backend Python:

```bash
# Jika menggunakan uv
uv run pip list 2>/dev/null | head -30

# Baca pyproject.toml untuk melihat dependencies
cat backend/pyproject.toml 2>/dev/null | grep -A 50 "\[project\]\|\[tool.poetry.dependencies\]" | head -40
```

Cek apakah versi dependencies dikunci (bukan `>=` tanpa batas atas untuk package security-critical):
- `cryptography`, `PyJWT`, `bcrypt`, `sqlalchemy` — harus ada versi spesifik
- `fastapi`, `uvicorn` — harus ada minimum versi

### Frontend:

```bash
cat frontend/package.json 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
deps = {**d.get('dependencies',{}), **d.get('devDependencies',{})}
for k,v in sorted(deps.items()):
    print(f'{k}: {v}')
" 2>/dev/null | head -40
```

Flag dependency yang:
- Tidak punya versi lock (`*` atau `latest`)
- Versi sangat lama untuk package yang relevan security (axios, jsonwebtoken, dll)

---

## Langkah 7 — Audit Rate Limiting & DoS Protection

```bash
# Cari rate limiting middleware
grep -rn "RateLimiter\|slowapi\|rate_limit\|throttle" backend/ --include="*.py" | head -10
```

Jika tidak ada rate limiting di endpoint auth (`/login`, `/register`, `/reset-password`), flagging sebagai **WARNING**.

---

## Langkah 8 — Generate Laporan

Buat `SECURITY_AUDIT.md` di root project:

```markdown
# Security Audit Report — [NAMA PROJECT]

**Tanggal:** TANGGAL_HARI_INI
**Dijalankan oleh:** `/security` skill
**Scope:** [quick/full/deps]

---

## Ringkasan Temuan

| Severity | Jumlah |
|----------|--------|
| 🔴 CRITICAL | N |
| 🟠 WARNING  | N |
| 🟡 INFO     | N |
| ✅ PASSED   | N |

---

## Temuan Detail

### 🔴 CRITICAL

#### [Judul Temuan]
- **File:** `path/to/file.py:LINE`
- **Masalah:** Penjelasan masalah
- **Risiko:** Dampak jika dieksploitasi
- **Rekomendasi:** Cara memperbaiki

### 🟠 WARNING

[sama dengan di atas]

### 🟡 INFO

[catatan non-kritis]

### ✅ PASSED

- Password hashing menggunakan bcrypt ✓
- JWT menggunakan HS256 dengan key yang kuat ✓
- [lainnya yang lolos pengecekan]

---

## Quick Wins (Rekomendasi Prioritas)

1. [Paling kritis dulu]
2. ...

---

*Report ini dibuat otomatis. Lakukan penetration testing manual untuk audit yang lebih mendalam.*
```

---

## Subcommand: `fix`

Setelah generate laporan, auto-fix hanya temuan yang **SAFE** untuk diperbaiki otomatis:

**BOLEH auto-fix:**
- Tambahkan `.env` ke `.gitignore` jika belum ada
- Buat `.env.example` dari template jika belum ada
- Ubah `allow_origins=["*"]` ke `allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")]` jika `APP_ENV != "production"` sudah ada pengecekan
- Hapus `dangerouslySetInnerHTML` yang nilai-nya statis (bukan dari user input)

**JANGAN auto-fix:**
- Logika auth
- Query database
- Perubahan schema Pydantic
- Anything yang bisa break functionality

Untuk setiap fix, cetak apa yang diubah. Setelah fix, jalankan `git diff` untuk verifikasi.

---

## Langkah Akhir — Laporan Terminal

```
╔══════════════════════════════════════════╗
║         SECURITY AUDIT SELESAI           ║
╠══════════════════════════════════════════╣
║ 🔴 CRITICAL : N                          ║
║ 🟠 WARNING  : N                          ║
║ 🟡 INFO     : N                          ║
║ ✅ PASSED   : N                          ║
╠══════════════════════════════════════════╣
║ Report : SECURITY_AUDIT.md               ║
║ Fix    : N item di-fix otomatis          ║
╚══════════════════════════════════════════╝

⚠️  Jika ada CRITICAL, prioritaskan perbaikan sebelum release berikutnya.
```
