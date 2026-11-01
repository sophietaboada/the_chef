#!/usr/bin/env bash
# Install TheChef (and cloudflared) as user-level systemd services. No sudo needed.
# Run from the app checkout:   cd ~/apps/the_chef && bash deploy/setup.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${THECHEF_PORT:-8010}"
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR" "$HOME/.local/bin"

echo "==> App directory: $APP_DIR"
[ -x "$APP_DIR/.venv/bin/python" ] || { echo "Missing .venv - run: uv sync --frozen --no-dev"; exit 1; }
[ -f "$APP_DIR/.env" ] || echo "WARNING: no .env in $APP_DIR (AI/Spoonacular keys and production settings)"

cat > "$UNIT_DIR/thechef.service" <<EOF
[Unit]
Description=TheChef (Sanic app on 127.0.0.1:$PORT)
After=network-online.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python -m thechef --host 127.0.0.1 --port $PORT
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now thechef.service
systemctl --user restart thechef.service

# Keep user services running after logout and across reboots.
if ! loginctl enable-linger "$USER" 2>/dev/null; then
  echo "NOTE: couldn't enable lingering. Run once:  sudo loginctl enable-linger $USER"
fi

echo -n "==> Health check: "
for _ in $(seq 1 20); do
  if curl -fs "http://127.0.0.1:$PORT/healthz"; then echo; break; fi
  sleep 0.5
done || true
systemctl --user is-active thechef.service >/dev/null || { echo "TheChef failed to start:"; journalctl --user -u thechef -n 20 --no-pager; exit 1; }

# cloudflared binary
if ! command -v cloudflared >/dev/null && [ ! -x "$HOME/.local/bin/cloudflared" ]; then
  echo "==> Installing cloudflared to ~/.local/bin"
  curl -fsSL -o "$HOME/.local/bin/cloudflared" \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x "$HOME/.local/bin/cloudflared"
fi
"$HOME/.local/bin/cloudflared" --version 2>/dev/null || cloudflared --version

echo
echo "Done. TheChef is running on 127.0.0.1:$PORT."
echo "Next: create the tunnel in Cloudflare, then run:  bash deploy/set-tunnel-token.sh"
