# Start MCP mesh worker on this machine (second PC / sidecar process)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$py = Join-Path $Root ".venv-train\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$port = if ($env:JH_MESH_PORT) { $env:JH_MESH_PORT } else { "8092" }
$nodeId = if ($env:JH_MESH_NODE_ID) { $env:JH_MESH_NODE_ID } else { "mesh-worker-1" }

Write-Host "MCP Mesh worker on port $port (node=$nodeId)"
& $py -m safety_eval.mcp.mesh_worker --host 0.0.0.0 --port $port --node-id $nodeId
