$ErrorActionPreference = "Stop"

$pluginName = "geoifcassets"
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root $pluginName
$dist = Join-Path $root "dist"
$zip = Join-Path $dist "$pluginName.zip"
$stageRoot = Join-Path $dist "_package"
$stagePlugin = Join-Path $stageRoot $pluginName
$packageJson = Join-Path $root "package.json"
$nodeModules = Join-Path $root "node_modules"

if ((Test-Path $packageJson) -and (Test-Path $nodeModules)) {
    npm run build:webviewer
}

New-Item -ItemType Directory -Force -Path $dist | Out-Null
if (Test-Path $zip) {
    Remove-Item -LiteralPath $zip -Force
}

if (Test-Path $stageRoot) {
    $resolvedStage = (Resolve-Path -LiteralPath $stageRoot).Path
    $resolvedDist = (Resolve-Path -LiteralPath $dist).Path
    if (-not $resolvedStage.StartsWith($resolvedDist)) {
        throw "Refusing to remove staging directory outside dist: $resolvedStage"
    }
    Remove-Item -LiteralPath $stageRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
Copy-Item -LiteralPath $source -Destination $stageRoot -Recurse

Get-ChildItem -Path $stagePlugin -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
Get-ChildItem -Path $stagePlugin -Recurse -File -Include "*.pyc", "*.pyo" |
    Remove-Item -Force

Compress-Archive -Path $stagePlugin -DestinationPath $zip
Remove-Item -LiteralPath $stageRoot -Recurse -Force
Write-Output "Created $zip"
