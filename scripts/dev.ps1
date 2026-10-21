# Start SciReader and open it in its own app window.
#   ./scripts/dev.ps1            build the UI if needed, start the backend, open the app window
#   ./scripts/dev.ps1 -Rebuild   rebuild the UI first
#   ./scripts/dev.ps1 -Hot       also start the Vite dev server (hot reload) and open that instead
param(
    [switch]$Rebuild,
    [switch]$Hot,
    [int]$Port = 8765
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not $Hot -and ($Rebuild -or -not (Test-Path (Join-Path $root "frontend\dist\index.html")))) {
    Write-Host "Building the UI..."
    npm --prefix (Join-Path $root "frontend") run build
    if ($LASTEXITCODE -ne 0) { throw "UI build failed" }
}

Write-Host "Starting the backend on port $Port..."
$backend = Start-Process -FilePath "uv" -PassThru -NoNewWindow -ArgumentList @(
    "run", "--directory", (Join-Path $root "backend"),
    "uvicorn", "scireader.main:app", "--host", "127.0.0.1", "--port", "$Port")

$frontend = $null
$url = "http://localhost:$Port"
if ($Hot) {
    $frontend = Start-Process -FilePath "npm" -PassThru -NoNewWindow -ArgumentList @("--prefix", (Join-Path $root "frontend"), "run", "dev")
    $url = "http://localhost:5173"
}

# Wait for the API.
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health" -TimeoutSec 2 | Out-Null
        break
    } catch { Start-Sleep -Milliseconds 500 }
}

# Borderless app window: Edge (ships with Windows 11), then Chrome, then the default browser.
$candidates = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$browser = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if ($browser) {
    Start-Process -FilePath $browser -ArgumentList @("--app=$url", "--window-size=1440,900")
} else {
    Start-Process $url
}
Write-Host "SciReader is running at $url (Ctrl+C to stop)."
try {
    Wait-Process -Id $backend.Id
} finally {
    if ($frontend -and -not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
    if (-not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
}
