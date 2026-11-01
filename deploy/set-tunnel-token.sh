#!/usr/bin/env bash
# Store the Cloudflare Tunnel token (prompted, never echoed) and run the tunnel as a user service.
# Run in YOUR terminal (not via an AI chat):   cd ~/apps/the_chef && bash deploy/set-tunnel-token.sh
set -euo pipefail

CF_BIN="$(command -v cloudflared || echo "$HOME/.local/bin/cloudflared")"
[ -x "$CF_BIN" ] || { echo "cloudflared not found - run deploy/setup.sh first"; exit 1; }

ENV_FILE="$HOME/.config/cloudflared/the-chef.env"
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$(dirname "$ENV_FILE")" "$UNIT_DIR"

read -rsp "Paste the tunnel token (starts with eyJ, input hidden): " TOKEN
echo
TOKEN="${TOKEN#*--token }"   # accept the whole install command too
TOKEN="${TOKEN##* }"
[[ "$TOKEN" == eyJ* ]] || { echo "That doesn't look like a tunnel token (should start with eyJ)."; exit 1; }

( umask 077; printf 'TUNNEL_TOKEN=%s\n' "$TOKEN" > "$ENV_FILE" )
unset TOKEN

cat > "$UNIT_DIR/cloudflared-thechef.service" <<EOF
[Unit]
Description=Cloudflare Tunnel for TheChef
After=network-online.target thechef.service

[Service]
EnvironmentFile=$ENV_FILE
ExecStart=$CF_BIN tunnel --no-autoupdate run
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now cloudflared-thechef.service
systemctl --user restart cloudflared-thechef.service
sleep 4
systemctl --user --no-pager status cloudflared-thechef.service | head -n 5
echo
echo "If it says 'active (running)', open your public hostname, e.g. https://thechef.orbi.com"
