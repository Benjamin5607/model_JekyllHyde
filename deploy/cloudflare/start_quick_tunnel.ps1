# Expose local Jekyll & Hyde API via Cloudflare quick tunnel (no account/domain).
$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

$port = if ($env:JH_PORT) { $env:JH_PORT } else { "8080" }
$url = "http://127.0.0.1:$port"

function Find-Cloudflared {
    $candidates = @(
        (Get-Command cloudflared -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
        (Join-Path $env:USERPROFILE ".cloudflared\bin\cloudflared.exe"),
        "C:\Program Files (x86)\cloudflared\cloudflared.exe",
        "C:\Program Files\cloudflared\cloudflared.exe"
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    return $null
}

$cf = Find-Cloudflared
if (-not $cf) {
    Write-Host "cloudflared not found. Run: .\deploy\cloudflare\install_cloudflared.ps1"
    exit 1
}

Write-Host "=== Cloudflare quick tunnel ==="
Write-Host "Local API: $url"
Write-Host "Make sure API is running (.\scripts\start_triple_deploy.ps1)"
Write-Host ""
Write-Host "Your public HTTPS URL will appear below (https://....trycloudflare.com):"
Write-Host ""

& $cf tunnel --url $url
