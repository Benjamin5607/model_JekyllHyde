param([int]$Port = 8080)
try {
    $h = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
    if ($h.model_ready -eq $true) { Write-Output "0"; exit 0 }
    if ($h.model_loading -eq $true) { Write-Output "2"; exit 0 }
    Write-Output "1"
} catch {
    Write-Output "1"
}
