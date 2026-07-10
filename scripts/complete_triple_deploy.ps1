# One-shot: verify + start API (loads secrets/.env)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Get-Content "$Root\secrets\.env" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}

Write-Host "=== Verify tri-deploy ==="
python scripts/verify_triple_deploy.py
if ($LASTEXITCODE -ne 0) { Write-Host "Some checks failed (see above)" }

Write-Host "`n=== Starting API on :8080 ==="
python -m safety_eval.platform.serve --host 0.0.0.0 --port 8080
