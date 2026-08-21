$ErrorActionPreference = "Stop"

$smtpHost = Read-Host "SMTP host [smtp.gmail.com]"
if ([string]::IsNullOrWhiteSpace($smtpHost)) { $smtpHost = "smtp.gmail.com" }

$smtpPort = Read-Host "SMTP port [587]"
if ([string]::IsNullOrWhiteSpace($smtpPort)) { $smtpPort = "587" }

$smtpUser = Read-Host "Sender email address"
$emailTo = Read-Host "Recipient email address [$smtpUser]"
if ([string]::IsNullOrWhiteSpace($emailTo)) { $emailTo = $smtpUser }

$securePassword = Read-Host "Email app password (hidden)" -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$emailConfigured = $false

try {
    $smtpPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)

    $settings = @{
        STONKS_SMTP_HOST = $smtpHost
        STONKS_SMTP_PORT = $smtpPort
        STONKS_SMTP_USER = $smtpUser
        STONKS_SMTP_PASSWORD = $smtpPassword
        STONKS_EMAIL_TO = $emailTo
    }

    foreach ($setting in $settings.GetEnumerator()) {
        Set-Item -Path "Env:$($setting.Key)" -Value $setting.Value
    }

    & "$PSScriptRoot\.venv\Scripts\python.exe" `
        "$PSScriptRoot\src\send_latest_report.py"

    if ($LASTEXITCODE -ne 0) {
        throw "Test email failed with exit code $LASTEXITCODE."
    }

    foreach ($setting in $settings.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable(
            $setting.Key,
            $setting.Value,
            "User"
        )
    }

    $emailConfigured = $true
    Write-Host "Email settings saved for this Windows user."
}
finally {
    if (-not $emailConfigured) {
        foreach ($settingName in @(
            "STONKS_SMTP_HOST",
            "STONKS_SMTP_PORT",
            "STONKS_SMTP_USER",
            "STONKS_SMTP_PASSWORD",
            "STONKS_EMAIL_TO"
        )) {
            Remove-Item -Path "Env:$settingName" -ErrorAction SilentlyContinue
        }
    }
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    Remove-Variable smtpPassword -ErrorAction SilentlyContinue
}
