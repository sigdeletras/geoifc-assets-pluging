$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$plugin = Join-Path $root "geoifcassets"
$i18n = Join-Path $plugin "i18n"

if (-not (Get-Command pylupdate5 -ErrorAction SilentlyContinue)) {
    Write-Output "pylupdate5 is not available. Run this script from a QGIS/Qt development shell."
    exit 0
}

pylupdate5 $plugin -ts (Join-Path $i18n "geoifcassets_en.ts") (Join-Path $i18n "geoifcassets_es.ts")
