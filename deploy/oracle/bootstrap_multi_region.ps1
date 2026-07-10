# Bootstrap VCN + public subnet in all regions listed in retry_a1.config.json
$ErrorActionPreference = "Stop"
Set-Location (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)

$env:OCI_CLI_CONFIG_FILE = "$env:USERPROFILE\.oci\config"

Write-Host "==> OCI auth check"
$tenancy = (Select-String -Path $env:OCI_CLI_CONFIG_FILE -Pattern '^tenancy=').Line.Split('=', 2)[1]
oci iam availability-domain list --compartment-id $tenancy --output json | Out-Null
Write-Host "OCI OK`n"

Write-Host "==> Subscribe extra regions (tenancy must allow this)"
python deploy/oracle/subscribe_regions.py --config deploy/oracle/retry_a1.config.json --wait
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "==> Bootstrap OCI networking (multi-region)"
python deploy/oracle/bootstrap_multi_region.py --config deploy/oracle/retry_a1.config.json

Write-Host ""
Write-Host "==> Verify"
python deploy/oracle/retry_a1_instance.py --discover-regions --config deploy/oracle/retry_a1.config.json
