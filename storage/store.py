import sqlite3
import time
from pathlib import Path
import pandas as pd

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text())
        conn.commit()
        # Migration: add mt5_ticket column if it doesn't exist yet
        try:
            conn.execute("ALTER TABLE trades ADD COLUMN mt5_ticket INTEGER")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    finally:
        conn.close()


def write_candle(db_path: str, pair: str, timeframe: str, candle: dict) -> int | None:
    """Insert a candle. Returns new row id, or None if a duplicate (same pair/timeframe/timestamp)."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO candles "
            "(pair, timeframe, timestamp, open, high, low, close, volume) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pair, timeframe, candle["timestamp"], candle["open"], candle["high"],
             candle["low"], candle["close"], candle["volume"]),
        )
        conn.commit()
        return cur.lastrowid if cur.rowcount > 0 else None
    finally:
        conn.close()


def write_indicators(db_path: str, candle_id: int, ind: dict) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO indicators "
            "(candle_id, ema20, ema50, ema200, rsi14, macd, macd_signal, macd_hist, "
            "bb_upper, bb_mid, bb_lower, atr14, stoch_k, stoch_d) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                candle_id,
                ind.get("ema20"), ind.get("ema50"), ind.get("ema200"),
                ind.get("rsi14"),
                ind.get("macd"), ind.get("macd_signal"), ind.get("macd_hist"),
                ind.get("bb_upper"), ind.get("bb_mid"), ind.get("bb_lower"),
                ind.get("atr14"),
                ind.get("stoch_k"), ind.get("stoch_d"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def write_fetch_log(
    db_path: str,
    pair: str,
    timeframe: str,
    provider: str,
    status: str,
    error_msg: str | None = None,
    duration_ms: int | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO fetch_log (timestamp, pair, timeframe, provider, status, error_msg, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (int(time.time()), pair, timeframe, provider, status, error_msg, duration_ms),
        )
        conn.commit()
    finally:
        conn.close()


def get_latest_candles(db_path: str, pair: str, timeframe: str, n: int) -> pd.DataFrame:
    """Return the n most recent candles, sorted oldest-first."""
    conn = get_connection(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM candles WHERE pair=? AND timeframe=? "
            "ORDER BY timestamp DESC LIMIT ?",
            conn,
            params=(pair, timeframe, n),
        )
        return df.sort_values("timestamp").reset_index(drop=True)
    finally:
        conn.close()


def get_latest_indicators(db_path: str, pair: str, timeframe: str, n: int) -> pd.DataFrame:
    """Return indicators for the n most recent candles, sorted oldest-first."""
    conn = get_connection(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT i.* FROM indicators i "
            "JOIN candles c ON i.candle_id = c.id "
            "WHERE c.pair=? AND c.timeframe=? "
            "ORDER BY c.timestamp DESC LIMIT ?",
            conn,
            params=(pair, timeframe, n),
        )
        return df.sort_values("id").reset_index(drop=True)
    finally:
        conn.close()


def get_candle_with_indicators(
    db_path: str, pair: str, timeframe: str, timestamp: int
) -> dict:
    """Return a single candle merged with its indicators as a flat dict. Empty dict if not found."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT c.id, c.pair, c.timeframe, c.timestamp, "
            "c.open, c.high, c.low, c.close, c.volume, "
            "i.ema20, i.ema50, i.ema200, i.rsi14, "
            "i.macd, i.macd_signal, i.macd_hist, "
            "i.bb_upper, i.bb_mid, i.bb_lower, "
            "i.atr14, i.stoch_k, i.stoch_d "
            "FROM candles c LEFT JOIN indicators i ON i.candle_id = c.id "
            "WHERE c.pair=? AND c.timeframe=? AND c.timestamp=?",
            (pair, timeframe, timestamp),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def write_signal(db_path: str, signal: dict) -> int | None:
    """Insert a signal. Returns new row id, or None if duplicate (same pair/timeframe/timestamp)."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO signals "
            "(pair, timeframe, timestamp, created_at, direction, confidence, "
            "sl_pips, tp_pips, claude_direction, claude_confidence, "
            "gemini_direction, gemini_confidence, reasoning) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                signal["pair"], signal["timeframe"], signal["timestamp"],
                signal["created_at"], signal["direction"], signal["confidence"],
                signal.get("sl_pips"), signal.get("tp_pips"),
                signal.get("claude_direction"), signal.get("claude_confidence"),
                signal.get("gemini_direction"), signal.get("gemini_confidence"),
                signal.get("reasoning"),
            ),
        )
        conn.commit()
        return cur.lastrowid if cur.rowcount > 0 else None
    finally:
        conn.close()


def get_latest_signals(db_path: str, pair: str, timeframe: str, n: int) -> pd.DataFrame:
    """Return the n most recent signals, sorted oldest-first."""
    conn = get_connection(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM signals WHERE pair=? AND timeframe=? "
            "ORDER BY timestamp DESC LIMIT ?",
            conn,
            params=(pair, timeframe, n),
        )
        return df.sort_values("timestamp").reset_index(drop=True)
    finally:
        conn.close()


def seed_account(db_path: str, initial_balance: float) -> None:
    """Seed account with initial_balance on first run. Idempotent — no-op if row exists."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO account (id, balance, updated_at) VALUES (1, ?, ?)",
            (initial_balance, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def get_account_balance(db_path: str) -> float:
    """Return current account balance. Returns 0.0 if account not yet seeded."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT balance FROM account WHERE id = 1").fetchone()
        return float(row["balance"]) if row else 0.0
    finally:
        conn.close()


def update_account_balance(db_path: str, new_balance: float) -> None:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "UPDATE account SET balance = ?, updated_at = ? WHERE id = 1",
            (new_balance, int(time.time())),
        )
        conn.commit()
        if cur.rowcount == 0:
            raise RuntimeError("update_account_balance: account row not found — was seed_account called?")
    finally:
        conn.close()


def write_trade(db_path: str, trade: dict) -> int:
    """Insert a new trade. Returns the new row id."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO trades "
            "(pair, timeframe, signal_id, direction, entry_price, sl_price, tp_price, "
            "lot_size, sl_pips, tp_pips, opened_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trade["pair"], trade["timeframe"], trade["signal_id"],
                trade["direction"], trade["entry_price"],
                trade["sl_price"], trade["tp_price"],
                trade["lot_size"], trade["sl_pips"], trade["tp_pips"],
                trade["opened_at"],
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_open_trades(db_path: str, pair: str) -> pd.DataFrame:
    """Return all open trades for the given pair."""
    conn = get_connection(db_path)
    try:
        return pd.read_sql_query(
            "SELECT * FROM trades WHERE pair = ? AND status = 'open'",
            conn,
            params=(pair,),
        )
    finally:
        conn.close()


def close_trade(
    db_path: str,
    trade_id: int,
    close_price: float,
    close_reason: str,
    pnl_pips: float,
    pnl_usd: float,
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE trades SET status='closed', closed_at=?, close_price=?, "
            "close_reason=?, pnl_pips=?, pnl_usd=? WHERE id=? AND status='open'",
            (int(time.time()), close_price, close_reason, pnl_pips, pnl_usd, trade_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_closed_trades(db_path: str, pair: str, n: int) -> pd.DataFrame:
    """Return the n most recent closed trades for the given pair, sorted oldest-first."""
    conn = get_connection(db_path)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM trades WHERE pair = ? AND status = 'closed' "
            "ORDER BY closed_at DESC LIMIT ?",
            conn,
            params=(pair, n),
        )
        return df.sort_values("closed_at").reset_index(drop=True)
    finally:
        conn.close()


def write_stats(db_path: str, stats: dict) -> None:
    """Upsert performance stats for a pair (INSERT OR REPLACE by pair primary key)."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO stats "
            "(pair, updated_at, trade_count, win_count, loss_count, win_rate, "
            "total_pnl_pips, total_pnl_usd, avg_win_pips, avg_loss_pips, "
            "profit_factor, max_drawdown_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                stats["pair"], stats["updated_at"],
                stats["trade_count"], stats["win_count"], stats["loss_count"],
                stats["win_rate"], stats["total_pnl_pips"], stats["total_pnl_usd"],
                stats.get("avg_win_pips"), stats.get("avg_loss_pips"),
                stats.get("profit_factor"), stats["max_drawdown_usd"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_stats(db_path: str, pair: str) -> dict | None:
    """Return the stats row for the given pair as a plain dict, or None if not yet computed."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM stats WHERE pair = ?", (pair,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_trade_ticket(db_path: str, trade_id: int, ticket: int) -> None:
    """Store the MT5 ticket number for a trade."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("UPDATE trades SET mt5_ticket=? WHERE id=?", (ticket, trade_id))
        conn.commit()
        if cur.rowcount == 0:
            raise RuntimeError(f"set_trade_ticket: trade {trade_id} not found")
    finally:
        conn.close()


def get_trade_ticket(db_path: str, trade_id: int) -> int | None:
    """Return the MT5 ticket for a trade, or None if not set."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT mt5_ticket FROM trades WHERE id=?", (trade_id,)).fetchone()
        return int(row["mt5_ticket"]) if row and row["mt5_ticket"] is not None else None
    finally:
        conn.close()
