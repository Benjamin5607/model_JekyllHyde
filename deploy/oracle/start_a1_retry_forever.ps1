# Keep retrying even if Python crashes, PC wakes from sleep, or network blips.
# Usage: .\deploy\oracle\start_a1_retry_forever.ps1
$ErrorActionPreference = "Continue"
Set-Location (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)

$log = "deploy/oracle/retry_a1.log"
$restartWait = if ($env:JH_OCI_RESTART_WAIT) { [int]$env:JH_OCI_RESTART_WAIT } else { 30 }

Write-Host "Forever mode: restarts on crash. Log: $log"
Write-Host "Disable PC sleep while this runs.`n"

while ($true) {
    try {
        & "$PSScriptRoot\start_a1_retry.ps1"
        $code = $LASTEXITCODE
        if ($code -eq 0) {
            Write-Host "Instance created. Exiting forever loop."
            break
        }
        $msg = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] wrapper: script exited code $code; restart in ${restartWait}s"
        Write-Host $msg
        Add-Content -Path $log -Value $msg
    }
    catch {
        $msg = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] wrapper: $($_.Exception.Message); restart in ${restartWait}s"
        Write-Host $msg
        Add-Content -Path $log -Value $msg
    }
    Start-Sleep -Seconds $restartWait
}
