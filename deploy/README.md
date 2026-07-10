# Tri-deploy quick reference

## Roles

| Role | Backend | Env |
|------|---------|-----|
| Demo UI | HF ZeroGPU Space | browser only |
| API 24/7 | Ollama GGUF | `JH_API_BACKEND=ollama` |
| Agent/MCP | Groq LPU | `JH_AGENT_BACKEND=groq` + `GROQ_API_KEY` |

## Setup

```bash
# 1) Merge LoRA + Ollama models (on dev machine or Oracle VM)
python scripts/setup_triple_deploy.py --merge --ollama
# optional GGUF (needs llama.cpp):
python scripts/setup_triple_deploy.py --merge --gguf --ollama

# 2) Oracle Always Free

### 2a) Bootstrap VCN in multiple regions (once)

```powershell
.\deploy\oracle\bootstrap_multi_region.ps1
```

Creates `jekyll-hyde-vcn` + public subnet (SSH 22, API 8080) in each region listed in `retry_a1.config.json`. Skips regions that already have a subnet.

### 2b) ARM VM capacity retry (Out of capacity)

Prerequisites: VCN + **public subnet** in OCI Console, SSH key (`~/.ssh/id_rsa.pub`).

```powershell
# Windows — once
.\deploy\oracle\install_oci_cli.ps1
oci setup config

copy deploy\oracle\retry_a1.config.example.json deploy\oracle\retry_a1.config.json
python deploy/oracle/retry_a1_instance.py --discover
# Edit retry_a1.config.json with compartment_id + subnet_id

# Run until A1.Flex is available (Ctrl+C to stop)
# Multi-region: rotates on capacity full (see regions in retry_a1.config.json)
python deploy/oracle/retry_a1_instance.py --discover-regions
.\deploy\oracle\start_a1_retry_forever.ps1
```

The script rotates AD-1/2/3 automatically. Change region in `~/.oci/config` if your home region has no ARM capacity.

### 2c) After VM is created

```bash
bash deploy/oracle/setup.sh
```

# 3) Groq agent path
export GROQ_API_KEY=gsk_...
export JH_AGENT_BACKEND=groq

# 4) Run API
JH_API_BACKEND=ollama python -m safety_eval.platform.serve --host 0.0.0.0 --port 8080
```

## HF demo

https://benjamin5607-jekyll-hyde-demo.hf.space — ZeroGPU quota applies per visitor, not HF_TOKEN.

## Cloudflare Tunnel (expose local API)

```powershell
.\deploy\cloudflare\install_cloudflared.ps1
.\scripts\start_triple_deploy.ps1
.\deploy\cloudflare\start_quick_tunnel.ps1
# or all at once:
.\scripts\start_dual_deploy.ps1 -Tunnel quick
```

See `deploy/cloudflare/README.md`.

## Config

See `config/inference.yaml`.
