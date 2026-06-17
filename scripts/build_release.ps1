#Requires -Version 5.1
<#
.SYNOPSIS
  Build compressed Jekyll & Hyde install archive.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$Py = Join-Path $Root ".venv-train\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

Write-Host "Optimizing storage..."
& $Py -m safety_eval.storage.optimizer | Out-Null

Write-Host "Building install packages (compresslevel=9, live progress every 3s)..."
Write-Host "Model compression may take 30-90 minutes — progress lines will print continuously."
& $Py -m safety_eval.storage.packager

$Zip = Join-Path $Root "dist\JekyllHyde-1.2.1-win64.zip"
if (Test-Path $Zip) {
    $Mb = [math]::Round((Get-Item $Zip).Length / 1MB, 1)
    Write-Host "Done: $Zip ($Mb MB)"
}
