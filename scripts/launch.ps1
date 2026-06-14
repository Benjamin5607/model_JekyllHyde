# Jekyll & Hyde — silent background launcher (restart + open browser)
param([int]$Port = 8080)

$ErrorActionPreference = "SilentlyContinue"
$Root = Split-Path $PSScriptRoot -Parent
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "platform.log"

function Find-Python {
    $candidates = @(
        (Join-Path $Root ".venv-train\Scripts\python.exe"),
        (Join-Path $Root ".venv\Scripts\python.exe")
    )
    if (Test-Path (Join-Path $Root "models\merged\jekyll-hyde\config.json")) {
        if (Test-Path $candidates[0]) { return $candidates[0] }
    }
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

$Python = Find-Python
if (-not $Python) {
    [System.Windows.Forms.MessageBox]::Show(
        "Python not found.`nRun scripts\setup_platform.bat once.",
        "Jekyll & Hyde",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}

Add-Type -AssemblyName System.Windows.Forms | Out-Null

# Ensure package (quiet)
& $Python -c "import safety_eval.platform.serve" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $Python -m pip install -q -e "${Root}[quant,mcp]" 2>> $LogFile
    if ($LASTEXITCODE -ne 0) { & $Python -m pip install -q -e $Root 2>> $LogFile }
}

# Always restart (like restart.bat)
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

$env:HF_HUB_DISABLE_PROGRESS_BARS = "1"
$env:TRANSFORMERS_NO_ADVISORY_WARNINGS = "1"
$env:TOKENIZERS_PARALLELISM = "false"
$tokenPath = Join-Path $Root "secrets\hf_token.txt"
if (Test-Path $tokenPath) { $env:HF_TOKEN = (Get-Content $tokenPath -Raw).Trim() }

$OutLog = Join-Path $LogDir "platform.log"
$ErrLog = Join-Path $LogDir "platform.err.log"
"=== $(Get-Date -Format o) starting on port $Port ===" | Add-Content $OutLog

$args = @("-u", "-m", "safety_eval.platform.serve", "--port", "$Port")
Start-Process -FilePath $Python -ArgumentList $args -WorkingDirectory $Root `
    -WindowStyle Hidden -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog

# Wait for HTTP then model_ready
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
        if ($h.model_ready -eq $true) { $ready = $true; break }
        if ($i -ge 5 -and $h.model_loading -eq $false -and $h.model_ready -eq $false) {
            # server up, model still loading — open UI anyway after 5s
            if ($i -ge 8) { break }
        }
    } catch { }
}

Start-Process "http://127.0.0.1:$Port"

if (-not $ready) {
    # UI still usable while model loads in background
    exit 0
}
exit 0
