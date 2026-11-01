$ErrorActionPreference = "Continue"
$taskName = "MemoCardestSync"
$source = Join-Path $PSScriptRoot "sync-if-agent.ps1"
$targetDir = Join-Path $env:LOCALAPPDATA "MemoCardest"
$target = Join-Path $targetDir "sync-if-agent.ps1"
New-Item -ItemType Directory -Force $targetDir | Out-Null
Copy-Item $source $target -Force

# schtasks works for a standard user; Register-ScheduledTask may require elevation.
schtasks /delete /tn $taskName /f 2>&1 | Out-Null
schtasks /create /tn $taskName `
    /tr "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$target`"" `
    /sc HOURLY /mo 6 /f 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create $taskName"
}

schtasks /query /tn $taskName /fo LIST
Write-Host "Installed: $target"
