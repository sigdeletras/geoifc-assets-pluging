$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$i18n = Join-Path $root "geoifcassets\i18n"

if (-not (Get-Command lrelease -ErrorAction SilentlyContinue)) {
    Write-Output "lrelease is not available. Run this script from a QGIS/Qt development shell."
    exit 0
}

Get-ChildItem -Path $i18n -Filter "*.ts" | ForEach-Object {
    lrelease $_.FullName
}
