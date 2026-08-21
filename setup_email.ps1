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
        [Environment]::SetEnvironmentVariable(
            $setting.Key,
            $setting.Value,
            "User"
        )
        Set-Item -Path "Env:$($setting.Key)" -Value $setting.Value
    }

    & "$PSScriptRoot\.venv\Scripts\python.exe" `
        "$PSScriptRoot\src\send_latest_report.py"

    if ($LASTEXITCODE -ne 0) {
        throw "Test email failed with exit code $LASTEXITCODE."
    }

    Write-Host "Email settings saved for this Windows user."
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    Remove-Variable smtpPassword -ErrorAction SilentlyContinue
}
