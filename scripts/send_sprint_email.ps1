<#
.SYNOPSIS
    Kirim email notifikasi sprint via Outlook desktop (COM automation).
    Pengganti Windows untuk scripts/pm_email.applescript (macOS-only, Mail.app)
    dari sunartha-claude-skills-dev.

.PARAMETER Subject
    Subjek email.

.PARAMETER BodyFile
    Path ke file teks berisi isi email (plain text).

.PARAMETER To
    Alamat email penerima utama. Default: eliano@sunartha.co.id

.PARAMETER Cc
    Alamat email CC. Default: daru@sunartha.co.id

.EXAMPLE
    powershell -File scripts\send_sprint_email.ps1 -Subject "[Sprint 2/7] Odoo Shipping selesai" -BodyFile sprint_email_body.txt
#>
param(
    [Parameter(Mandatory = $true)][string]$Subject,
    [Parameter(Mandatory = $true)][string]$BodyFile,
    [string]$To = "eliano@sunartha.co.id",
    [string]$Cc = "daru@sunartha.co.id"
)

if (-not (Test-Path $BodyFile)) {
    Write-Error "BodyFile tidak ditemukan: $BodyFile"
    exit 1
}

$body = Get-Content -Path $BodyFile -Raw -Encoding UTF8

# Outlook COM (CreateItem) gagal dengan E_ABORT jika proses OUTLOOK.EXE belum
# berjalan. Auto-launch dan tunggu sebentar sebelum connect.
if (-not (Get-Process OUTLOOK -ErrorAction SilentlyContinue)) {
    Start-Process outlook.exe
    Start-Sleep -Seconds 15
}

try {
    $outlook = New-Object -ComObject Outlook.Application
    $mail = $outlook.CreateItem(0)  # olMailItem
    $mail.To = $To
    $mail.CC = $Cc
    $mail.Subject = $Subject
    $mail.Body = $body
    $mail.Send()
    Write-Output "EMAIL_SENT_OK to=$To cc=$Cc subject=$Subject"
}
catch {
    Write-Error "Gagal kirim email via Outlook COM: $($_.Exception.Message)"
    exit 1
}
