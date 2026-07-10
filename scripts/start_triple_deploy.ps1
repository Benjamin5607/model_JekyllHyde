# Start Jekyll & Hyde API (Ollama backend) with optional Groq for MCP agent path.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Resolve-Python {
    $candidates = @(
        (Join-Path $Root ".venv-train\Scripts\python.exe"),
        (Join-Path $Root ".venv\Scripts\python.exe")
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    return "python"
}

$py = Resolve-Python
Write-Host "Python: $py"

$quantOk = & $py -c "import yfinance" 2>$null
if (-not $quantOk) {
    Write-Host "Installing quant deps (yfinance, FinanceDataReader, duckduckgo-search)..."
    & $py -m pip install -e ".[quant]"
}

$secrets = Join-Path $Root "secrets\.env"
if (Test-Path $secrets) {
    Get-Content $secrets | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    Write-Host "Loaded secrets/.env"
} else {
    Write-Host "No secrets/.env - using defaults (Ollama API only)"
    $env:JH_API_BACKEND = "ollama"
    $env:JH_AGENT_BACKEND = "groq"
    $env:JH_OLLAMA_URL = "http://127.0.0.1:11434"
}

if (-not (ollama list 2>$null | Select-String "jekyll-hyde-jekyll")) {
    Write-Host "Creating Ollama models..."
    & $py scripts/setup_triple_deploy.py --merge --ollama
}

$port = if ($env:JH_PORT) { $env:JH_PORT } else { "8080" }

$listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
if ($listeners.Count -gt 0) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/api/health/lite" -TimeoutSec 5
        if ($health.ok) {
            Write-Host "API already running on port $port (model_ready=$($health.model_ready), quant_deps=$($health.quant_deps))"
            Write-Host "Open http://127.0.0.1:$port"
            if (-not $health.quant_deps) {
                Write-Host "WARNING: quant deps missing - run .\scripts\restart_api.ps1"
            } else {
                Write-Host "No need to start again. To restart: .\scripts\restart_api.ps1"
            }
            exit 0
        }
    } catch {}
    Write-Host "ERROR: Port $port is already in use (WinError 10048)."
    Write-Host "Run: .\scripts\restart_api.ps1"
    exit 1
}

Write-Host "API backend: $($env:JH_API_BACKEND) | Agent: $($env:JH_AGENT_BACKEND)"
Write-Host "Open http://127.0.0.1:$port"
& $py -m safety_eval.platform.serve --host 0.0.0.0 --port $port
