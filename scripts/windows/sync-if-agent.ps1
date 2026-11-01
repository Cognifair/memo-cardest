$ErrorActionPreference = "Continue"
$logDir = Join-Path $env:LOCALAPPDATA "MemoCardest"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "sync.log"

function Write-Log([string]$message) {
    Add-Content -Path $log -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $message) -Encoding UTF8
}

Write-Log "run: sync all installed Memo roots"

$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $python) {
    $python = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.*\python.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $python) {
    $python = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $python -or -not (Test-Path $python)) {
    Write-Log "error: python executable not found"
    exit 1
}

$roots = @(
    (Join-Path $env:USERPROFILE ".agents\skills"),
    (Join-Path $env:USERPROFILE ".codex\skills"),
    (Join-Path $env:USERPROFILE ".claude\skills"),
    (Join-Path $env:USERPROFILE ".workbuddy\skills")
)

foreach ($root in $roots) {
    $script = Join-Path $root "memo-cardest\scripts\check_updates.py"
    if (-not (Test-Path $script)) {
        Write-Log "skip: $root has no memo-cardest"
        continue
    }
    Write-Log "sync: $root"
    & $python -B $script --root $root sync 2>&1 | Out-File -FilePath $log -Append -Encoding Unicode
    Write-Log "exit: $root -> $LASTEXITCODE"
}
