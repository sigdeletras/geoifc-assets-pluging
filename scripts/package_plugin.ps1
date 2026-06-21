$ErrorActionPreference = "Stop"

$pluginName = "geoifcassets"
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root $pluginName
$dist = Join-Path $root "dist"
$zip = Join-Path $dist "$pluginName.zip"

New-Item -ItemType Directory -Force -Path $dist | Out-Null
if (Test-Path $zip) {
    Remove-Item -LiteralPath $zip -Force
}

Compress-Archive -Path $source -DestinationPath $zip
Write-Output "Created $zip"
