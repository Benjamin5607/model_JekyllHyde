# Quick Groq smoke test (requires GROQ_API_KEY in secrets/.env or env)
$Root = Split-Path -Parent $PSScriptRoot
$secrets = Join-Path $Root "secrets\.env"
if (Test-Path $secrets) {
    Get-Content $secrets | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}
if (-not $env:GROQ_API_KEY) {
    Write-Error "Set GROQ_API_KEY in secrets/.env — https://console.groq.com/keys"
}
python -c "from safety_eval.platform.groq_client import chat, groq_available; assert groq_available(); r=chat([{'role':'user','content':'Say hi in one sentence.'}], persona='jekyll'); print('Groq OK:', r[:200])"
