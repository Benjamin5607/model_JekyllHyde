#Requires -Version 5.1
param(
    [string]$ModelPartsDir = "",
    [switch]$SkipVenv
)

$ErrorActionPreference = "Stop"
$InstallRoot = $PSScriptRoot
Set-Location $InstallRoot

Write-Host "Jekyll & Hyde installer v1.0.0"
Write-Host "Install path: $InstallRoot"

$ModelDir = Join-Path $InstallRoot "models\merged\jekyll-hyde"
$ModelFile = Join-Path $ModelDir "model.safetensors"
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

if (-not (Test-Path $ModelFile)) {
    $parts = Get-ChildItem -Path $InstallRoot -Filter "JekyllHyde-*-model.part*" -ErrorAction SilentlyContinue |
        Sort-Object Name
    if ($parts.Count -gt 0) {
        Write-Host "Merging model parts ($($parts.Count) files)..."
        $fs = [System.IO.File]::Create($ModelFile)
        try {
            foreach ($p in $parts) {
                Write-Host "  + $($p.Name)"
                $bytes = [System.IO.File]::ReadAllBytes($p.FullName)
                $fs.Write($bytes, 0, $bytes.Length)
            }
        } finally {
            $fs.Close()
        }
        Write-Host "Model merged: $ModelFile"
    } elseif ($ModelPartsDir -and (Test-Path $ModelPartsDir)) {
        $parts = Get-ChildItem -Path $ModelPartsDir -Filter "JekyllHyde-*-model.part*" | Sort-Object Name
        foreach ($p in $parts) { Copy-Item $p.FullName $InstallRoot }
        & $PSCommandPath -SkipVenv:$SkipVenv
        exit $LASTEXITCODE
    } else {
        Write-Host "WARN: model.safetensors not found."
        Write-Host "Download model parts from GitHub Releases and place in this folder, then re-run install.ps1"
    }
}

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
    Write-Host "Desktop shortcut created."
}

Write-Host ""
Write-Host "Done. Run scripts\start.bat or open http://127.0.0.1:8080"
