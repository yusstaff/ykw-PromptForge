$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$PythonVersion = "3.12.10"

pyenv local $PythonVersion

if (-not (Test-Path ".venv")) {
    pyenv exec python -m venv .venv
}

$venvVersion = & ".\.venv\Scripts\python.exe" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
if ($venvVersion -ne $PythonVersion) {
    throw ".venv uses Python $venvVersion, expected $PythonVersion. Remove .venv and run this script again."
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host ""
Write-Host "Project environment ready: $root\.venv"
Write-Host "Python: $venvVersion"
Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
