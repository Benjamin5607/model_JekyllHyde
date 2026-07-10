# Run Oracle A1.Flex capacity retry loop (background-friendly)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)

$env:OCI_CLI_CONFIG_FILE = "$env:USERPROFILE\.oci\config"

$config = "deploy/oracle/retry_a1.config.json"
if (-not (Test-Path $config)) {
    Copy-Item "deploy/oracle/retry_a1.config.example.json" $config
    Write-Host "Created $config - run discover first:"
    python deploy/oracle/retry_a1_instance.py --discover
    exit 1
}

Write-Host "==> OCI auth check"
$tenancy = (Select-String -Path $env:OCI_CLI_CONFIG_FILE -Pattern '^tenancy=').Line.Split('=', 2)[1]
oci iam availability-domain list --compartment-id $tenancy --output json | Out-Null
Write-Host "OCI OK`n"

$interval = if ($env:JH_OCI_RETRY_INTERVAL) { $env:JH_OCI_RETRY_INTERVAL } else { 120 }
python deploy/oracle/retry_a1_instance.py --config $config --interval $interval
