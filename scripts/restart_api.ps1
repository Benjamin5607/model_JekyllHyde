# Stop duplicate API servers on :8080 and start with quant-enabled Python.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> Stopping existing listeners on port 8080"
Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
        $procId = $_.OwningProcess
        if ($procId) {
            Write-Host "  kill PID $procId"
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
Start-Sleep -Seconds 2

& (Join-Path $Root "scripts\start_triple_deploy.ps1")
