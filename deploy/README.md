# Forex AI Trading Bot — Production Deployment

Deploy the Forex AI Trading Bot as a managed systemd service on a Linux VPS.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Ubuntu 22.04 LTS (or later) | Other systemd-based distros should work |
| Python 3.11+ | `python3 --version` to check |
| `git` | `apt install git` |
| `python3-venv` | `apt install python3-venv` |
| Root / sudo access | Required for service installation |
| MetaTrader 5 terminal | **Live trading only** — must run on the same machine or a reachable Wine/Windows environment |

---

## Quick Start

### 1. Clone the repository

```bash
git clone <your-repo-url> /opt/forex-ai
cd /opt/forex-ai
```

### 2. Run the install script

```bash
sudo bash deploy/install.sh
```

The script will:
- Create a dedicated `forex` system user
- Set up `/opt/forex-ai` with correct ownership
- Create a Python virtual environment at `/opt/forex-ai/venv`
- Install all dependencies from `requirements.txt`
- Copy `.env.example` to `.env` (if `.env` does not already exist)
- Install and enable the `forex-ai` systemd service

### 3. Edit your environment variables

```bash
sudo nano /opt/forex-ai/.env
```

At minimum you must set:

```
ALPHA_VANTAGE_API_KEY=<your key>
ANTHROPIC_API_KEY=<your key>
GEMINI_API_KEY=<your key>
```

For live MT5 trading also set:

```
BROKER_MODE=live
MT5_LOGIN=<your login number>
MT5_PASSWORD=<your password>
MT5_SERVER=<broker server name>
```

See [Environment Variables](#environment-variables) below for the full reference.

### 4. Start the service

```bash
sudo systemctl start forex-ai
```

---

## Service Management

| Action | Command |
|---|---|
| Start | `sudo systemctl start forex-ai` |
| Stop | `sudo systemctl stop forex-ai` |
| Restart | `sudo systemctl restart forex-ai` |
| Status | `sudo systemctl status forex-ai` |
| Enable on boot | `sudo systemctl enable forex-ai` |
| Disable on boot | `sudo systemctl disable forex-ai` |
| Live logs | `sudo journalctl -u forex-ai -f` |
| Recent logs (100 lines) | `sudo journalctl -u forex-ai -n 100 --no-pager` |

---

## Update Procedure

Pull the latest code and restart the service in one step:

```bash
sudo bash /opt/forex-ai/deploy/update.sh
```

The update script:
1. Runs `git pull` inside `/opt/forex-ai`
2. Reinstalls/upgrades Python dependencies
3. Restarts the `forex-ai` service
4. Prints the current service status

---

## Environment Variables

All configuration is read from `/opt/forex-ai/.env`. The template with all available variables is at `.env.example`:

| Variable | Default | Description |
|---|---|---|
| `ALPHA_VANTAGE_API_KEY` | *(required)* | Alpha Vantage market data API key |
| `ANTHROPIC_API_KEY` | *(required)* | Anthropic Claude API key |
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `CLAUDE_MODEL` | `claude-haiku-4-5-20251001` | Claude model to use |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini model to use |
| `DB_PATH` | `forex.db` | SQLite database file path |
| `BROKER_MODE` | `paper` | `paper` for simulated trading, `live` for real trades |
| `PAPER_BALANCE` | `10000.0` | Starting balance for paper trading |
| `RISK_PCT` | `0.01` | Fraction of balance risked per trade (1% = 0.01) |
| `MT5_LOGIN` | *(empty)* | MetaTrader 5 account number (live mode only) |
| `MT5_PASSWORD` | *(empty)* | MetaTrader 5 account password (live mode only) |
| `MT5_SERVER` | *(empty)* | MetaTrader 5 broker server (live mode only) |

---

## Troubleshooting

### Service fails to start

Check the logs for the error:

```bash
sudo journalctl -u forex-ai -n 50 --no-pager
```

Common causes:

- **Missing API keys** — The bot exits immediately if `ALPHA_VANTAGE_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY` are empty. Edit `/opt/forex-ai/.env`.
- **Missing MT5 credentials** — If `BROKER_MODE=live` is set you must also provide `MT5_LOGIN`, `MT5_PASSWORD`, and `MT5_SERVER`.
- **Python version too old** — Verify with `python3 --version` (need 3.11+).
- **Dependency install failed** — Re-run `sudo /opt/forex-ai/venv/bin/pip install -r /opt/forex-ai/requirements.txt` and check for errors.

### Service keeps restarting

The service is configured with `Restart=on-failure` and a 30-second back-off (`RestartSec=30`). If it restarts repeatedly:

```bash
sudo journalctl -u forex-ai -f
```

Look for the last error message before each restart.

### Permission errors

Ensure the `forex` user owns the install directory:

```bash
sudo chown -R forex:forex /opt/forex-ai
```

### Re-running the install script

`install.sh` is idempotent — it is safe to run again. It will not overwrite an existing `.env` file or recreate an existing virtual environment.
