# Development-only unsigned Windows build; run from the repository root.
# Never distribute as a secure production installer.
$ErrorActionPreference = "Stop"
if ($env:OS -ne "Windows_NT") { throw "Only Windows builds are supported." }
if (-not (Test-Path ".venv")) { py -3.12 -m venv .venv }
$python = ".\.venv\Scripts\python.exe"
$deploy = ".\.venv\Scripts\pyside6-deploy.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -e ".[desktop]"
if (-not (Test-Path $deploy)) { throw "pyside6-deploy is not installed; see the official Qt for Python docs." }
& $deploy run_windows.py --mode onefile
Write-Host "Development artifact built. Check deployment output and test on a clean Windows VM."
