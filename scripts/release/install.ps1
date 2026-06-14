#Requires -Version 5.1
<#
.SYNOPSIS
  Install Jekyll & Hyde from extracted release folder.
#>
param(
    [switch]$SkipVenv
)

$ErrorActionPreference = "Stop"
$InstallRoot = $PSScriptRoot
Set-Location $InstallRoot

Write-Host "Jekyll & Hyde installer v1.0.0"
Write-Host "Install path: $InstallRoot"

if (-not $SkipVenv) {
    $Venv = Join-Path $InstallRoot ".venv"
    if (-not (Test-Path $Venv)) {
        Write-Host "Creating virtual environment..."
        python -m venv $Venv
    }
    $Py = Join-Path $Venv "Scripts\python.exe"
    & $Py -m pip install --upgrade pip
    & $Py -m pip install -e ".[train,quant,mcp]"
} else {
    $Py = "python"
}

Write-Host "Creating desktop shortcut..."
$Vbs = Join-Path $InstallRoot "scripts\JekyllHyde.vbs"
if (Test-Path $Vbs) {
    $Desktop = [Environment]::GetFolderPath("Desktop")
    $Shortcut = Join-Path $Desktop "Jekyll & Hyde.lnk"
    $Wsh = New-Object -ComObject WScript.Shell
    $Lnk = $Wsh.CreateShortcut($Shortcut)
    $Lnk.TargetPath = $Vbs
    $Lnk.WorkingDirectory = $InstallRoot
    $Lnk.Description = "Jekyll & Hyde Platform"
    $Lnk.Save()
    Write-Host "Shortcut: $Shortcut"
}

Write-Host ""
Write-Host "Install complete. Double-click 'Jekyll & Hyde' on Desktop or run:"
Write-Host "  scripts\start.bat"
Write-Host "  http://127.0.0.1:8080"
