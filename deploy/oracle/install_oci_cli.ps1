# Install Oracle OCI CLI on Windows (for retry_a1_instance.py)
$ErrorActionPreference = "Stop"

Write-Host "==> Installing oci-cli via pip"
python -m pip install --upgrade pip oci-cli

Write-Host ""
Write-Host "==> Verify"
oci --version

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. oci setup config"
Write-Host "     (API key: OCI Console > Profile > API Keys > Add)"
Write-Host "  2. Copy deploy/oracle/retry_a1.config.example.json -> deploy/oracle/retry_a1.config.json"
Write-Host "  3. python deploy/oracle/retry_a1_instance.py --discover"
Write-Host "  4. python deploy/oracle/retry_a1_instance.py"
