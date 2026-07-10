# Install cloudflared on Windows
$ErrorActionPreference = "Stop"

$binDir = Join-Path $env:USERPROFILE ".cloudflared\bin"
New-Item -ItemType Directory -Force -Path $binDir | Out-Null

$cloudflared = Join-Path $binDir "cloudflared.exe"
if (Test-Path $cloudflared) {
    Write-Host "cloudflared already installed: $cloudflared"
    & $cloudflared --version
    exit 0
}

Write-Host "==> Installing cloudflared via winget"
try {
    winget install --id Cloudflare.cloudflared -e --accept-package-agreements --accept-source-agreements
    $wingetPath = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($wingetPath) {
        Write-Host "Installed: $($wingetPath.Source)"
        cloudflared --version
        exit 0
    }
} catch {
    Write-Host "winget install failed, downloading binary..."
}

$arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "386" }
$url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-$arch.exe"
Write-Host "Downloading $url"
Invoke-WebRequest -Uri $url -OutFile $cloudflared -UseBasicParsing
Write-Host "Installed: $cloudflared"
& $cloudflared --version

Write-Host ""
Write-Host "Add to PATH (optional, current session):"
Write-Host "  `$env:PATH = `"$binDir;`$env:PATH`""
