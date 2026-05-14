$ProjectPythonVersion = (Get-Content ".python-version" -Raw).Trim()
$ProjectPythonMajorMinor = (($ProjectPythonVersion -split "\.")[0..1] -join ".")
$VenvPython = ".\.venv\Scripts\python.exe"

function Test-CommandAvailable {
    param([string] $Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-PythonVersionMatch {
    param([string] $Version)
    return $Version -like "$ProjectPythonMajorMinor.*"
}

function Get-InterpreterVersion {
    param(
        [string] $Command,
        [string[]] $PrefixArgs = @()
    )

    try {
        $version = & $Command @PrefixArgs -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $version) {
            return $version.Trim()
        }
    }
    catch {
        return $null
    }
    return $null
}

function Find-ProjectPython {
    if (Test-CommandAvailable "pyenv") {
        try {
            pyenv local $ProjectPythonVersion | Out-Null
        }
        catch {
        }

        $version = Get-InterpreterVersion "pyenv" @("exec", "python")
        if ($version -and (Test-PythonVersionMatch $version)) {
            return [PSCustomObject]@{
                Command = "pyenv"
                Args = @("exec", "python")
                Version = $version
                Label = "pyenv Python $version"
            }
        }
    }

    if (Test-CommandAvailable "py") {
        $version = Get-InterpreterVersion "py" @("-$ProjectPythonMajorMinor")
        if ($version -and (Test-PythonVersionMatch $version)) {
            return [PSCustomObject]@{
                Command = "py"
                Args = @("-$ProjectPythonMajorMinor")
                Version = $version
                Label = "Python Launcher $version"
            }
        }
    }

    if (Test-CommandAvailable "python") {
        $version = Get-InterpreterVersion "python"
        if ($version -and (Test-PythonVersionMatch $version)) {
            return [PSCustomObject]@{
                Command = "python"
                Args = @()
                Version = $version
                Label = "python $version"
            }
        }
    }

    throw "Python $ProjectPythonMajorMinor.x was not found. Install Python $ProjectPythonMajorMinor, or install pyenv/pyenv-win with $ProjectPythonVersion."
}

function Assert-ProjectVenv {
    if (-not (Test-Path $VenvPython)) {
        throw ".venv was not found. Run scripts\setup_env.ps1 first."
    }

    $venvVersion = & $VenvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    if (-not (Test-PythonVersionMatch $venvVersion)) {
        throw ".venv uses Python $venvVersion, expected Python $ProjectPythonMajorMinor.x. Remove .venv and run scripts\setup_env.ps1 again."
    }
    return $venvVersion
}

function Ensure-ProjectVenv {
    if (-not (Test-Path ".venv")) {
        $python = Find-ProjectPython
        Write-Host "Creating .venv with $($python.Label)"
        & $python.Command @($python.Args + @("-m", "venv", ".venv"))
    }

    return Assert-ProjectVenv
}
