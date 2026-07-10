# Cloudflare Tunnel for Jekyll & Hyde local API (port 8080)

## Quick start (no domain, ~2 min)

Random `*.trycloudflare.com` URL. Good for testing.

```powershell
cd c:\Users\User\evil_model
.\deploy\cloudflare\install_cloudflared.ps1
.\scripts\start_triple_deploy.ps1          # window 1 - API
.\deploy\cloudflare\start_quick_tunnel.ps1 # window 2 - public HTTPS URL
```

Copy the `https://....trycloudflare.com` line from the tunnel window.

Test:

```powershell
curl https://YOUR-URL.trycloudflare.com/api/health
```

## Named tunnel (your domain, permanent URL)

Requires a domain on Cloudflare (free plan OK).

```powershell
.\deploy\cloudflare\install_cloudflared.ps1
.\deploy\cloudflare\setup_named_tunnel.ps1 -Hostname api.yourdomain.com
.\deploy\cloudflare\start_named_tunnel.ps1
```

## All-in-one (local API + Oracle retry + quick tunnel)

```powershell
.\scripts\start_dual_deploy.ps1 -Tunnel quick
```

## Security

- The API has no built-in login. Anyone with the URL can call it.
- For production: Cloudflare Access (Zero Trust) or put API behind a secret header.
- Quick tunnel URLs change each restart; do not share publicly long-term.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `cloudflared not found` | Run `install_cloudflared.ps1` |
| 502 Bad Gateway | Start local API first (`start_triple_deploy.ps1`) |
| Tunnel exits | Keep the tunnel PowerShell window open |
