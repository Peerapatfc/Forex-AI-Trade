#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# update.sh — Pull latest code and restart the Forex AI Trading Bot service.
# Must be run as root (or via sudo).
# ---------------------------------------------------------------------------

INSTALL_DIR="/opt/forex-ai"
SERVICE_NAME="forex-ai"

echo "==> Updating Forex AI Trading Bot..."

echo "==> [1/4] Pulling latest code..."
cd "${INSTALL_DIR}"
git pull

echo "==> [2/4] Installing/updating Python dependencies..."
"${INSTALL_DIR}/venv/bin/pip" install -r requirements.txt -q

echo "==> [3/4] Restarting service..."
systemctl restart "${SERVICE_NAME}"

echo "==> [4/4] Service status:"
systemctl status "${SERVICE_NAME}" --no-pager

echo ""
echo "Update complete. Follow logs with: journalctl -u ${SERVICE_NAME} -f"
