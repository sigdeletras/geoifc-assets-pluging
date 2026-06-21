$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

& $python -m ruff check geoifcassets tests
& $python -m mypy geoifcassets

$packageJson = Join-Path $root "package.json"
$nodeModules = Join-Path $root "node_modules"
if ((Test-Path $packageJson) -and (Test-Path $nodeModules)) {
    npm run typecheck:webviewer
}
