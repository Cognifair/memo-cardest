$ErrorActionPreference = "Continue"
$taskName = "MemoCardestSync"
schtasks /delete /tn $taskName /f 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removed scheduled task: $taskName"
} else {
    Write-Host "Task not found: $taskName"
}
