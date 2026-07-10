# Dual deploy: local API (Ollama+Groq) + Oracle Kulai retry in a second window.
param(
    [ValidateSet("", "quick", "named")]
    [string]$Tunnel = ""
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== Dual deploy ==="
Write-Host "1) Local API  -> this window"
Write-Host "2) Oracle Kulai retry -> opening second PowerShell window"
if ($Tunnel -eq "quick") {
    Write-Host "3) Cloudflare quick tunnel -> opening third PowerShell window"
} elseif ($Tunnel -eq "named") {
    Write-Host "3) Cloudflare named tunnel -> opening third PowerShell window"
}
Write-Host ""

# Disable sleep while Oracle retry runs (optional; revert manually later)
try {
    powercfg /change standby-timeout-ac 0 | Out-Null
    powercfg /change standby-timeout-dc 0 | Out-Null
    Write-Host "PC sleep disabled while this session runs."
} catch {
    Write-Host "Could not change power settings (run as admin to disable sleep)."
}

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $Root "deploy\oracle\start_a1_retry_forever.ps1")
)

if ($Tunnel -eq "quick") {
    Start-Sleep -Seconds 3
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $Root "deploy\cloudflare\start_quick_tunnel.ps1")
    )
} elseif ($Tunnel -eq "named") {
    Start-Sleep -Seconds 3
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $Root "deploy\cloudflare\start_named_tunnel.ps1")
    )
}

Write-Host ""
& (Join-Path $Root "scripts\start_triple_deploy.ps1")
