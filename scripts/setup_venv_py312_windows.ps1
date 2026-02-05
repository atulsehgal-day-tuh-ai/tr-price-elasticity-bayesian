$ErrorActionPreference = "Stop"

function Write-Step($msg) {
  Write-Host ""
  Write-Host "==> $msg"
}

function Assert-LastExitCodeOk([string] $what) {
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed ($what) with exit code $LASTEXITCODE"
  }
}

# Allow the Windows Python launcher (py.exe) to install missing runtimes via winget
# (py prints a hint about this when a requested version isn't available)
$env:PYLAUNCHER_ALLOW_INSTALL = "1"

Write-Step "Moving to repo root (this script assumes it lives in scripts/)"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$venvDir = Join-Path $repoRoot "venv312"

Write-Step "Checking for Python 3.12 via py launcher"
$pyver = & py -3.12 -c "import sys; print(sys.version)"
if ($LASTEXITCODE -ne 0) {
  Write-Host "Python 3.12 not found via 'py -3.12'."
  Write-Host "Detected Python environments (py -0p):"
  & py -0p

  $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $wingetCmd) {
    throw "winget is not available, so automatic install can't proceed. Install Python 3.12.3 from python.org, then re-run this script."
  }

  Write-Host "Attempting to install Python 3.12.3 via winget..."
  & winget install --id Python.Python.3.12 --version 3.12.3 --accept-source-agreements --accept-package-agreements --silent
  if ($LASTEXITCODE -ne 0) {
    Write-Host "First winget attempt failed; retrying with --scope user..."
    & winget install --id Python.Python.3.12 --version 3.12.3 --scope user --accept-source-agreements --accept-package-agreements --silent
    Assert-LastExitCodeOk "winget install Python.Python.3.12 3.12.3 (--scope user)"
  }

  Write-Host "Re-checking Python 3.12 via py launcher..."
  $pyver = & py -3.12 -c "import sys; print(sys.version)"
  if ($LASTEXITCODE -ne 0) {
    throw "Python 3.12 still isn't available via 'py -3.12' after installation. Close/reopen the terminal (or restart Cursor) and re-run this script."
  }
}
Write-Host "Found Python 3.12: $pyver"

Write-Step "Creating venv at $venvDir"
if (Test-Path $venvDir) {
  Remove-Item -Recurse -Force $venvDir
}
& py -3.12 -m venv $venvDir
Assert-LastExitCodeOk "py -3.12 -m venv"

$python = Join-Path $venvDir "Scripts\\python.exe"
$pip = Join-Path $venvDir "Scripts\\pip.exe"

if (-not (Test-Path $python)) {
  throw "venv python not found at: $python. venv creation did not complete successfully."
}

Write-Step "Upgrading pip and installing requirements"
& $python -m pip install --upgrade pip
Assert-LastExitCodeOk "pip upgrade"
& $pip install -r requirements.txt
Assert-LastExitCodeOk "pip install requirements"

Write-Step "Optional: register Jupyter kernel (safe if Jupyter is installed)"
try {
  & $python -m ipykernel install --user --name tr-price-elasticity-py312 --display-name "Price Elasticity (Py312)"
} catch {
  Write-Host "Skipping ipykernel registration (ipykernel not installed yet)."
}

Write-Step "Done"
Write-Host "To activate: .\\venv312\\Scripts\\Activate.ps1"
Write-Host 'To verify:   .\venv312\Scripts\python.exe -c "import sys; print(sys.version)"'

