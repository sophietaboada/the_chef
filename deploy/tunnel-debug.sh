#!/usr/bin/env bash
# Run the Cloudflare Tunnel in the foreground for 25 s to show why it can't connect.
# Usage:  cd ~/apps/the_chef && bash deploy/tunnel-debug.sh
set -uo pipefail

CF_BIN="$(command -v cloudflared || echo "$HOME/.local/bin/cloudflared")"
ENV_FILE="$HOME/.config/cloudflared/the-chef.env"

echo "== Outbound port 7844 (required by Cloudflare Tunnel):"
for h in region1.v2.argotunnel.com region2.v2.argotunnel.com; do
  if timeout 5 bash -c "</dev/tcp/$h/7844" 2>/dev/null; then echo "  $h TCP 7844: open"; else echo "  $h TCP 7844: BLOCKED"; fi
done

echo "== Running tunnel in the foreground for 25 seconds (service paused meanwhile)..."
systemctl --user stop cloudflared-thechef.service
set -a; . "$ENV_FILE"; set +a
timeout 25 "$CF_BIN" tunnel --no-autoupdate --loglevel info run 2>&1 \
  | sed -E 's/eyJ[A-Za-z0-9_=-]+/<token>/g' | tail -n 25
unset TUNNEL_TOKEN

echo "== Retrying with HTTP/2 over TCP instead of QUIC (UDP) for 20 seconds..."
set -a; . "$ENV_FILE"; set +a
timeout 20 "$CF_BIN" tunnel --no-autoupdate --protocol http2 run 2>&1 \
  | sed -E 's/eyJ[A-Za-z0-9_=-]+/<token>/g' | grep -iE "registered|error|ERR|failed|unable" | tail -n 10
unset TUNNEL_TOKEN

systemctl --user start cloudflared-thechef.service
echo "== Service restarted. Paste the output above (it contains no token)."
