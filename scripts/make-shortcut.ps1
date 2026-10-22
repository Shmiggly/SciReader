# Put a SciReader shortcut on the desktop: double-click it to start SciReader in its own window.
#   ./scripts/make-shortcut.ps1                  on the desktop
#   ./scripts/make-shortcut.ps1 -Folder <path>   somewhere else
# The shortcut runs scripts/dev.ps1 in a minimized console that holds the backend; close that console to stop SciReader.
param(
    [string]$Folder = [Environment]::GetFolderPath("Desktop")
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$link = Join-Path $Folder "SciReader.lnk"
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($link)
$shortcut.TargetPath = (Get-Command powershell.exe).Source
$shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot 'dev.ps1')`""
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = "$(Join-Path $PSScriptRoot 'scireader.ico'),0"
$shortcut.WindowStyle = 7  # minimized
$shortcut.Description = "SciReader: listen to scientific papers, offline"
$shortcut.Save()
Write-Host "Created $link"
