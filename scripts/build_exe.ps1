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
    throw ".venv uses Python $venvVersion, expected $PythonVersion. Remove .venv and run scripts\setup_env.ps1 again."
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

$distApp = Join-Path $root "dist\PromptForge"
$distExe = Join-Path $distApp "PromptForge.exe"
$dataDir = Join-Path $distApp "PromptForgeData"
$preservedDataDir = Join-Path $root "build\PromptForgeData.preserved"

$running = Get-Process -Name "PromptForge" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $distExe }
if ($running) {
    throw "PromptForge.exe is running. Close it before building: $distExe"
}

if (Test-Path $preservedDataDir) {
    Remove-Item -LiteralPath $preservedDataDir -Recurse -Force
}
if (Test-Path $dataDir) {
    Copy-Item -LiteralPath $dataDir -Destination $preservedDataDir -Recurse -Force
}

& ".\.venv\Scripts\python.exe" -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name PromptForge `
    ".\run_promptforge.py"

if (Test-Path $preservedDataDir) {
    $restoredDataDir = Join-Path $distApp "PromptForgeData"
    if (Test-Path $restoredDataDir) {
        Remove-Item -LiteralPath $restoredDataDir -Recurse -Force
    }
    Copy-Item -LiteralPath $preservedDataDir -Destination $restoredDataDir -Recurse -Force
    Remove-Item -LiteralPath $preservedDataDir -Recurse -Force
}

Write-Host ""
Write-Host "Build complete: $root\dist\PromptForge\PromptForge.exe"
Write-Host "Runtime data will be stored beside the exe in: dist\PromptForge\PromptForgeData"
