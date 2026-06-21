$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

$baseTemp = Join-Path $root ".pytest_tmp"
& $python -m pytest tests/unit -p no:pytestqt --basetemp $baseTemp
