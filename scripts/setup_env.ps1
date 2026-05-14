$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

. (Join-Path $PSScriptRoot "common.ps1")

$venvVersion = Ensure-ProjectVenv
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host ""
Write-Host "Project environment ready: $root\.venv"
Write-Host "Python: $venvVersion"
Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
