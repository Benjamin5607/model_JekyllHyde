#Requires -Version 5.1
param(
    [string]$ModelPartsDir = "",
    [switch]$SkipVenv
)

$ErrorActionPreference = "Stop"
$InstallRoot = $PSScriptRoot
Set-Location $InstallRoot

Write-Host "Jekyll & Hyde installer v1.2.0 (gzip level-9 model parts)"
Write-Host "Install path: $InstallRoot"

$ModelDir = Join-Path $InstallRoot "models\merged\jekyll-hyde"
$ModelFile = Join-Path $ModelDir "model.safetensors"
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

function Merge-GzipParts {
    param([System.IO.FileInfo[]]$Parts, [string]$OutFile)
    Write-Host "Decompressing and merging $($Parts.Count) gzip parts..."
    $out = [System.IO.File]::Create($OutFile)
    try {
        foreach ($p in $Parts) {
            Write-Host "  + $($p.Name)"
            $raw = [System.IO.File]::OpenRead($p.FullName)
            try {
                $gzip = New-Object System.IO.Compression.GzipStream($raw, [System.IO.Compression.CompressionMode]::Decompress)
                try { $gzip.CopyTo($out) } finally { $gzip.Dispose() }
            } finally { $raw.Dispose() }
        }
    } finally { $out.Dispose() }
    Write-Host "Model ready: $OutFile ($([math]::Round((Get-Item $OutFile).Length/1GB, 2)) GB)"
}

if (-not (Test-Path $ModelFile)) {
    $gzParts = Get-ChildItem -Path $InstallRoot -Filter "JekyllHyde-*-model.part*.gz" -ErrorAction SilentlyContinue |
        Sort-Object Name
    if ($gzParts.Count -gt 0) {
        Merge-GzipParts -Parts $gzParts -OutFile $ModelFile
    } else {
        $rawParts = Get-ChildItem -Path $InstallRoot -Filter "JekyllHyde-*-model.part*" -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -ne ".gz" } | Sort-Object Name
        if ($rawParts.Count -gt 0) {
            Write-Host "Merging raw model parts ($($rawParts.Count))..."
            $fs = [System.IO.File]::Create($ModelFile)
            try {
                foreach ($p in $rawParts) {
                    Write-Host "  + $($p.Name)"
                    $bytes = [System.IO.File]::ReadAllBytes($p.FullName)
                    $fs.Write($bytes, 0, $bytes.Length)
                }
            } finally { $fs.Close() }
        } elseif ($ModelPartsDir -and (Test-Path $ModelPartsDir)) {
            Get-ChildItem $ModelPartsDir -Filter "JekyllHyde-*-model.part*.gz" | Copy-Item -Destination $InstallRoot
            & $PSCommandPath -SkipVenv:$SkipVenv
            exit $LASTEXITCODE
        } else {
            Write-Host "WARN: Download model.part00.gz – part02.gz from GitHub Releases."
        }
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
}

Write-Host ""
Write-Host "Done. Open http://127.0.0.1:8080"
