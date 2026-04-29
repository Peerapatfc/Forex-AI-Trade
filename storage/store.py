import time
from pathlib import Path

import pandas as pd
import psycopg2
import psycopg2.extras

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_url: str):
    conn = psycopg2.connect(db_url)
    return conn


def init_db(db_url: str) -> None:
    conn = get_connection(db_url)
    try:
        schema = SCHEMA_PATH.read_text()
        with conn.cursor() as cur:
            for statement in schema.split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)
        conn.commit()
    finally:
        conn.close()


def write_candle(db_url: str, pair: str, timeframe: str, candle: dict) -> int | None:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO candles "
                "(pair, timeframe, timestamp, open, high, low, close, volume) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT DO NOTHING RETURNING id",
                (pair, timeframe, candle["timestamp"], candle["open"], candle["high"],
                 candle["low"], candle["close"], candle["volume"]),
            )
            row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    finally:
        conn.close()


def write_indicators(db_url: str, candle_id: int, ind: dict) -> None:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO indicators "
                "(candle_id, ema20, ema50, ema200, rsi14, macd, macd_signal, macd_hist, "
                "bb_upper, bb_mid, bb_lower, atr14, stoch_k, stoch_d) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
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
    db_url: str,
    pair: str,
    timeframe: str,
    provider: str,
    status: str,
    error_msg: str | None = None,
    duration_ms: int | None = None,
) -> None:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO fetch_log (timestamp, pair, timeframe, provider, status, error_msg, duration_ms) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (int(time.time()), pair, timeframe, provider, status, error_msg, duration_ms),
            )
        conn.commit()
    finally:
        conn.close()


def get_latest_candles(db_url: str, pair: str, timeframe: str, n: int) -> pd.DataFrame:
    conn = get_connection(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM candles WHERE pair=%s AND timeframe=%s "
                "ORDER BY timestamp DESC LIMIT %s",
                (pair, timeframe, n),
            )
            rows = cur.fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        if df.empty:
            return df
        return df.sort_values("timestamp").reset_index(drop=True)
    finally:
        conn.close()


def get_latest_indicators(db_url: str, pair: str, timeframe: str, n: int) -> pd.DataFrame:
    conn = get_connection(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT i.* FROM indicators i "
                "JOIN candles c ON i.candle_id = c.id "
                "WHERE c.pair=%s AND c.timeframe=%s "
                "ORDER BY c.timestamp DESC LIMIT %s",
                (pair, timeframe, n),
            )
            rows = cur.fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        if df.empty:
            return df
        return df.sort_values("id").reset_index(drop=True)
    finally:
        conn.close()


def get_candle_with_indicators(
    db_url: str, pair: str, timeframe: str, timestamp: int
) -> dict:
    conn = get_connection(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT c.id, c.pair, c.timeframe, c.timestamp, "
                "c.open, c.high, c.low, c.close, c.volume, "
                "i.ema20, i.ema50, i.ema200, i.rsi14, "
                "i.macd, i.macd_signal, i.macd_hist, "
                "i.bb_upper, i.bb_mid, i.bb_lower, "
                "i.atr14, i.stoch_k, i.stoch_d "
                "FROM candles c LEFT JOIN indicators i ON i.candle_id = c.id "
                "WHERE c.pair=%s AND c.timeframe=%s AND c.timestamp=%s",
                (pair, timeframe, timestamp),
            )
            row = cur.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def write_signal(db_url: str, signal: dict) -> int | None:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO signals "
                "(pair, timeframe, timestamp, created_at, direction, confidence, "
                "sl_pips, tp_pips, claude_direction, claude_confidence, "
                "gemini_direction, gemini_confidence, reasoning) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT DO NOTHING RETURNING id",
                (
                    signal["pair"], signal["timeframe"], signal["timestamp"],
                    signal["created_at"], signal["direction"], signal["confidence"],
                    signal.get("sl_pips"), signal.get("tp_pips"),
                    signal.get("claude_direction"), signal.get("claude_confidence"),
                    signal.get("gemini_direction"), signal.get("gemini_confidence"),
                    signal.get("reasoning"),
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    finally:
        conn.close()


def get_latest_signals(db_url: str, pair: str, timeframe: str, n: int) -> pd.DataFrame:
    conn = get_connection(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM signals WHERE pair=%s AND timeframe=%s "
                "ORDER BY timestamp DESC LIMIT %s",
                (pair, timeframe, n),
            )
            rows = cur.fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        if df.empty:
            return df
        return df.sort_values("timestamp").reset_index(drop=True)
    finally:
        conn.close()


def seed_account(db_url: str, initial_balance: float) -> None:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO account (id, balance, updated_at) VALUES (1, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (initial_balance, int(time.time())),
            )
        conn.commit()
    finally:
        conn.close()


def get_account_balance(db_url: str) -> float:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM account WHERE id = 1")
            row = cur.fetchone()
        return float(row[0]) if row else 0.0
    finally:
        conn.close()


def update_account_balance(db_url: str, new_balance: float) -> None:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE account SET balance = %s, updated_at = %s WHERE id = 1",
                (new_balance, int(time.time())),
            )
            if cur.rowcount == 0:
                raise RuntimeError("update_account_balance: account row not found")
        conn.commit()
    finally:
        conn.close()


def write_trade(db_url: str, trade: dict) -> int:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO trades "
                "(pair, timeframe, signal_id, direction, entry_price, sl_price, tp_price, "
                "lot_size, sl_pips, tp_pips, opened_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (
                    trade["pair"], trade["timeframe"], trade["signal_id"],
                    trade["direction"], trade["entry_price"],
                    trade["sl_price"], trade["tp_price"],
                    trade["lot_size"], trade["sl_pips"], trade["tp_pips"],
                    trade["opened_at"],
                ),
            )
            row = cur.fetchone()
        conn.commit()
        return row[0]
    finally:
        conn.close()


def get_open_trades(db_url: str, pair: str) -> pd.DataFrame:
    conn = get_connection(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM trades WHERE pair = %s AND status = 'open'",
                (pair,),
            )
            rows = cur.fetchall()
        return pd.DataFrame([dict(r) for r in rows])
    finally:
        conn.close()


def close_trade(
    db_url: str,
    trade_id: int,
    close_price: float,
    close_reason: str,
    pnl_pips: float,
    pnl_usd: float,
) -> None:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE trades SET status='closed', closed_at=%s, close_price=%s, "
                "close_reason=%s, pnl_pips=%s, pnl_usd=%s WHERE id=%s AND status='open'",
                (int(time.time()), close_price, close_reason, pnl_pips, pnl_usd, trade_id),
            )
        conn.commit()
    finally:
        conn.close()


def get_closed_trades(db_url: str, pair: str, n: int) -> pd.DataFrame:
    conn = get_connection(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM trades WHERE pair = %s AND status = 'closed' "
                "ORDER BY closed_at DESC LIMIT %s",
                (pair, n),
            )
            rows = cur.fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        if df.empty:
            return df
        return df.sort_values("closed_at").reset_index(drop=True)
    finally:
        conn.close()


def write_stats(db_url: str, stats: dict) -> None:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO stats "
                "(pair, updated_at, trade_count, win_count, loss_count, win_rate, "
                "total_pnl_pips, total_pnl_usd, avg_win_pips, avg_loss_pips, "
                "profit_factor, max_drawdown_usd) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (pair) DO UPDATE SET "
                "updated_at=EXCLUDED.updated_at, trade_count=EXCLUDED.trade_count, "
                "win_count=EXCLUDED.win_count, loss_count=EXCLUDED.loss_count, "
                "win_rate=EXCLUDED.win_rate, total_pnl_pips=EXCLUDED.total_pnl_pips, "
                "total_pnl_usd=EXCLUDED.total_pnl_usd, avg_win_pips=EXCLUDED.avg_win_pips, "
                "avg_loss_pips=EXCLUDED.avg_loss_pips, profit_factor=EXCLUDED.profit_factor, "
                "max_drawdown_usd=EXCLUDED.max_drawdown_usd",
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


def get_stats(db_url: str, pair: str) -> dict | None:
    conn = get_connection(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM stats WHERE pair = %s", (pair,))
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_trade_ticket(db_url: str, trade_id: int, ticket: int) -> None:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE trades SET mt5_ticket=%s WHERE id=%s", (ticket, trade_id))
            if cur.rowcount == 0:
                raise RuntimeError(f"set_trade_ticket: trade {trade_id} not found")
        conn.commit()
    finally:
        conn.close()


def get_trade_ticket(db_url: str, trade_id: int) -> int | None:
    conn = get_connection(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT mt5_ticket FROM trades WHERE id=%s", (trade_id,))
            row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None
    finally:
        conn.close()
