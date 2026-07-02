# fleet_document_id — Deployment Guide
**Odoo 19 Enterprise | Self-hosted Linux (bare metal)**
Sunartha ERP Consulting — fleet.document.id v19.0.1.0.0

---

## Prerequisites

| Item | Requirement |
|------|-------------|
| Odoo version | 19.0 Enterprise |
| Python | 3.11+ |
| Depends | `fleet`, `hr`, `account`, `mail` |
| Access | SSH ke server, sudo atau odoo user |

---

## 1. Salin modul ke addons path

```bash
# Cari addons path server Odoo kamu
grep addons_path /etc/odoo/odoo.conf
# Contoh output: addons_path = /opt/odoo/addons,/opt/odoo/custom_addons

# Salin folder modul
sudo cp -r fleet_document_id/ /opt/odoo/custom_addons/

# Pastikan ownership benar
sudo chown -R odoo:odoo /opt/odoo/custom_addons/fleet_document_id
sudo chmod -R 755 /opt/odoo/custom_addons/fleet_document_id
```

---

## 2. Update addons_path (jika custom_addons belum terdaftar)

```bash
sudo nano /etc/odoo/odoo.conf
```

Tambahkan path:
```ini
addons_path = /opt/odoo/addons,/opt/odoo/enterprise,/opt/odoo/custom_addons
```

---

## 3. Restart Odoo service

```bash
sudo systemctl restart odoo
# Atau jika pakai nama service berbeda:
sudo systemctl restart odoo-server
```

Cek log untuk memastikan tidak ada error saat startup:
```bash
sudo journalctl -u odoo -f --since "1 min ago"
# Tidak boleh ada Python ImportError atau XML parse error
```

---

## 4. Install modul di Odoo

1. Login sebagai Administrator
2. Aktifkan **Developer Mode**: Settings → General Settings → scroll bawah → Activate Developer Mode
3. Buka **Apps** → klik **Update Apps List** (tombol di atas)
4. Cari: `Fleet Document Management ID`
5. Klik **Install**
6. Tunggu hingga selesai — Odoo akan membuat semua tabel dan load data default

---

## 5. Verifikasi instalasi

Setelah install berhasil, cek:

```
✅ Menu baru: Fleet → Dokumen Legal → Semua Dokumen
✅ Menu baru: Fleet → Dokumen Legal → Dashboard Compliance
✅ Form kendaraan: ada tab "Dokumen Legal" dan smart button dokumen
✅ Cron aktif: Settings → Technical → Scheduled Actions → 
   cari "Fleet: Cek Expired Dokumen Kendaraan Harian"
```

---

## 6. Konfigurasi awal (post-install)

### 6a. Set PIC perpanjangan per dokumen
Buka setiap kendaraan → tab Dokumen Legal → tambahkan dokumen dan assign PIC.

### 6b. Tes cron manual
```
Settings → Technical → Scheduled Actions →
"Fleet: Cek Expired Dokumen Kendaraan Harian" → Run Manually
```

### 6c. Tes email alert
1. Buat dokumen dengan `expiry_date = hari ini + 7`
2. Jalankan cron manual
3. Cek inbox PIC — email template `fleet_doc_alert_7` harus terkirim

### 6d. Konfigurasi outgoing mail
Pastikan SMTP sudah dikonfigurasi:
```
Settings → Technical → Outgoing Mail Servers
```

---

## 7. Data migration — isi dokumen existing

Gunakan import template Excel untuk bulk upload dokumen kendaraan yang sudah ada.
Download template dari: **Fleet → Dokumen Legal → Semua Dokumen → Import**

Kolom yang diperlukan:
```
vehicle_id/license_plate | doc_type | doc_number | expiry_date | renewal_pic_id/login
```

---

## 8. Upgrade modul (jika ada update kode)

```bash
# Salin versi baru ke server
sudo cp -r fleet_document_id/ /opt/odoo/custom_addons/

# Upgrade dengan flag -u
sudo systemctl stop odoo
sudo -u odoo /opt/odoo/venv/bin/python /opt/odoo/odoo-bin \
    -c /etc/odoo/odoo.conf \
    -d NAMA_DATABASE \
    -u fleet_document_id \
    --stop-after-init

sudo systemctl start odoo
```

---

## 9. Rollback (jika diperlukan)

```bash
# Uninstall dari Odoo UI dulu:
# Apps → Fleet Document Management ID → Uninstall

# Hapus folder modul
sudo rm -rf /opt/odoo/custom_addons/fleet_document_id

sudo systemctl restart odoo
```

---

## 10. Troubleshooting

| Error | Kemungkinan Penyebab | Solusi |
|-------|----------------------|--------|
| `ModuleNotFoundError` | Path tidak terdaftar di `addons_path` | Cek `/etc/odoo/odoo.conf` |
| `XMLSyntaxError` | File XML korup | Validasi dengan `xmllint file.xml` |
| `KeyError: fleet_group_user` | Modul `fleet` belum terinstall | Install modul Fleet dulu |
| Email tidak terkirim | SMTP belum dikonfigurasi | Setup outgoing mail server |
| `ir.model.access` error | CSV access rights tidak ter-load | Restart + upgrade modul |

---

## Struktur File Modul

```
fleet_document_id/
├── __init__.py
├── __manifest__.py                    ← versi, dependencies, file list
├── models/
│   ├── __init__.py
│   ├── fleet_vehicle_document.py      ← model utama + cron logic
│   ├── fleet_vehicle.py               ← extend fleet.vehicle + SIM validation
│   └── fleet_document_renewal_log.py  ← audit trail perpanjangan
├── wizards/
│   ├── __init__.py
│   ├── fleet_document_renewal_wizard.py       ← business logic wizard
│   └── fleet_document_renewal_wizard_views.xml
├── views/
│   ├── fleet_vehicle_document_views.xml  ← list, form, kanban, search
│   ├── fleet_vehicle_views.xml           ← inject tab + smart button
│   ├── fleet_document_dashboard_views.xml
│   └── fleet_document_menus.xml
├── report/
│   ├── fleet_document_compliance_report.xml   ← report actions
│   └── fleet_document_compliance_template.xml ← QWeb PDF templates
├── data/
│   ├── fleet_document_data.xml       ← expense product master
│   ├── fleet_document_cron.xml       ← scheduled action
│   └── fleet_document_mail_template.xml  ← 4 email templates
├── security/
│   ├── ir.model.access.csv           ← CRUD per group
│   └── fleet_document_security.xml   ← record rules
└── static/
    └── src/
        ├── css/fleet_document.css
        └── js/fleet_document_widget.js
```

---

*Sunartha ERP Consulting | sunartha.co.id | v19.0.1.0.0*
