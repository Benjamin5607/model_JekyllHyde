# One-time setup: named Cloudflare tunnel + DNS for your domain.
param(
    [Parameter(Mandatory = $true)]
    [string]$Hostname,
    [string]$Port = "8080"
)
$ErrorActionPreference = "Stop"

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
    $local = Join-Path $env:USERPROFILE ".cloudflared\bin\cloudflared.exe"
    if (Test-Path $local) { $cf = Get-Command $local }
}
if (-not $cf) {
    Write-Host "Run .\deploy\cloudflare\install_cloudflared.ps1 first"
    exit 1
}

$tunnelName = "jekyll-hyde-api"
$configDir = Join-Path $env:USERPROFILE ".cloudflared"
$configFile = Join-Path $configDir "jekyll-hyde.yml"

Write-Host "==> Login (browser opens)"
& $cf.Source tunnel login

Write-Host "==> Create tunnel: $tunnelName"
$createOut = & $cf.Source tunnel create $tunnelName 2>&1 | Out-String
Write-Host $createOut

if ($createOut -notmatch "id:\s*([0-9a-f-]{36})") {
    Write-Host "Could not parse tunnel id. Run: cloudflared tunnel list"
    exit 1
}
$tunnelId = $Matches[1]
$credFile = Join-Path $configDir "$tunnelId.json"

Write-Host "==> DNS route: $Hostname"
& $cf.Source tunnel route dns $tunnelName $Hostname

$yml = @"
tunnel: $tunnelId
credentials-file: $credFile

ingress:
  - hostname: $Hostname
    service: http://127.0.0.1:$Port
  - service: http_status:404
"@
Set-Content -Path $configFile -Value $yml -Encoding utf8

Write-Host ""
Write-Host "Saved: $configFile"
Write-Host "Start with: .\deploy\cloudflare\start_named_tunnel.ps1"
Write-Host "Public URL: https://$Hostname"
