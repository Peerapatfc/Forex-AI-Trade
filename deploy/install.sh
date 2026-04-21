#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# install.sh — Deploy Forex AI Trading Bot onto a Linux VPS
# Safe to run multiple times (idempotent).
# Must be run as root (or via sudo).
# ---------------------------------------------------------------------------

INSTALL_DIR="/opt/forex-ai"
SERVICE_NAME="forex-ai"
FOREX_USER="forex"

echo "==> [1/7] Creating system user '${FOREX_USER}' (if not exists)..."
if ! id "${FOREX_USER}" &>/dev/null; then
    useradd -m -s /bin/bash "${FOREX_USER}"
    echo "    User '${FOREX_USER}' created."
else
    echo "    User '${FOREX_USER}' already exists — skipping."
fi

echo "==> [2/7] Setting up application directory at ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"

# If the current directory looks like the project root, copy files across.
# Otherwise assume the caller has already placed the code in INSTALL_DIR.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

if [[ -f "${PROJECT_ROOT}/main.py" ]]; then
    echo "    Copying project files from ${PROJECT_ROOT} to ${INSTALL_DIR}..."
    # rsync preferred; fall back to cp if unavailable
    if command -v rsync &>/dev/null; then
        rsync -a --exclude='.git' --exclude='__pycache__' \
              --exclude='*.pyc' --exclude='.env' \
              --exclude='venv' \
              "${PROJECT_ROOT}/" "${INSTALL_DIR}/"
    else
        cp -r "${PROJECT_ROOT}/." "${INSTALL_DIR}/"
    fi
else
    echo "    Project root not detected next to deploy/. Skipping file copy."
    echo "    Ensure code is already present in ${INSTALL_DIR}."
fi

echo "==> [3/7] Creating Python virtual environment..."
if [[ ! -d "${INSTALL_DIR}/venv" ]]; then
    python3 -m venv "${INSTALL_DIR}/venv"
    echo "    Virtual environment created."
else
    echo "    Virtual environment already exists — skipping creation."
fi

echo "==> [4/7] Installing Python dependencies..."
"${INSTALL_DIR}/venv/bin/pip" install --upgrade pip -q
"${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt" -q
echo "    Dependencies installed."

echo "==> [5/7] Setting up environment file..."
if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
    if [[ -f "${INSTALL_DIR}/.env.example" ]]; then
        cp "${INSTALL_DIR}/.env.example" "${INSTALL_DIR}/.env"
        echo "    Copied .env.example to .env — REMEMBER to fill in your API keys!"
    else
        echo "    WARNING: .env.example not found. Create ${INSTALL_DIR}/.env manually."
    fi
else
    echo "    .env already exists — not overwriting."
fi

echo "==> [6/7] Installing systemd service..."
cp "${SCRIPT_DIR}/forex-ai.service" "/etc/systemd/system/${SERVICE_NAME}.service"
echo "    Service file installed."

echo "==> [7/7] Enabling systemd service..."
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

# Set ownership so the service user can write logs / the database
chown -R "${FOREX_USER}:${FOREX_USER}" "${INSTALL_DIR}"

echo ""
echo "==========================================================="
echo " Installation complete!"
echo "==========================================================="
echo ""
echo " Next steps:"
echo "   1. Edit your environment variables:"
echo "        nano ${INSTALL_DIR}/.env"
echo "      Required keys: ALPHA_VANTAGE_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY"
echo "      For live trading also set: MT5_LOGIN, MT5_PASSWORD, MT5_SERVER"
echo ""
echo "   2. Start the service:"
echo "        systemctl start ${SERVICE_NAME}"
echo ""
echo "   3. Check service status:"
echo "        systemctl status ${SERVICE_NAME}"
echo ""
echo "   4. Follow live logs:"
echo "        journalctl -u ${SERVICE_NAME} -f"
echo "==========================================================="
