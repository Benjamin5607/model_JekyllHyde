#!/usr/bin/env bash
# Oracle Cloud Always Free (ARM 4 OCPU / 24GB) — Ollama + Jekyll & Hyde API
set -euo pipefail

REPO="${REPO:-$HOME/jekyll-hyde}"
PORT="${JH_PORT:-8080}"

echo "==> Installing Ollama"
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
sudo systemctl enable ollama || true
sudo systemctl start ollama || true

echo "==> Python venv + deps"
cd "$REPO"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

echo "==> Merge LoRA + Ollama models (jekyll / hyde)"
python scripts/setup_triple_deploy.py --merge --ollama

echo "==> Env for 24/7 API (add to ~/.bashrc or systemd)"
cat <<EOF

export JH_API_BACKEND=ollama
export JH_AGENT_BACKEND=groq
export JH_OLLAMA_URL=http://127.0.0.1:11434
# export GROQ_API_KEY=gsk_...   # optional — MCP agent fast path

EOF

echo "==> Install systemd unit"
sudo cp deploy/oracle/jekyll-hyde-api.service /etc/systemd/system/
sudo sed -i "s|/opt/jekyll-hyde|$REPO|g" /etc/systemd/system/jekyll-hyde-api.service
sudo systemctl daemon-reload
sudo systemctl enable jekyll-hyde-api
sudo systemctl restart jekyll-hyde-api

echo "Done. API: http://$(curl -s ifconfig.me 2>/dev/null || echo SERVER_IP):$PORT"
echo "Open firewall TCP $PORT in Oracle VCN if needed."
