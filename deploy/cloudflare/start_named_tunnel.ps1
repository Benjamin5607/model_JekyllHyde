# Run a previously configured named tunnel.
$ErrorActionPreference = "Stop"
$configFile = Join-Path $env:USERPROFILE ".cloudflared\jekyll-hyde.yml"
if (-not (Test-Path $configFile)) {
    Write-Host "Config not found: $configFile"
    Write-Host "Run: .\deploy\cloudflare\setup_named_tunnel.ps1 -Hostname api.yourdomain.com"
    exit 1
}

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
    $local = Join-Path $env:USERPROFILE ".cloudflared\bin\cloudflared.exe"
    if (Test-Path $local) { $cf = Get-Command $local }
}
if (-not $cf) { Write-Host "cloudflared not found"; exit 1 }

Write-Host "=== Named Cloudflare tunnel ==="
Write-Host "Config: $configFile"
Write-Host "Keep this window open."
& $cf.Source tunnel --config $configFile run
