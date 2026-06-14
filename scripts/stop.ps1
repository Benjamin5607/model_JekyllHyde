# Stop Jekyll & Hyde background server
param([int]$Port = 8080)
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Write-Host "Jekyll & Hyde stopped (port $Port)."
