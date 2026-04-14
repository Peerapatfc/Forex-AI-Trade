CREATE TABLE IF NOT EXISTS candles (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pair      TEXT    NOT NULL,
    timeframe TEXT    NOT NULL,
    timestamp INTEGER NOT NULL,
    open      REAL    NOT NULL,
    high      REAL    NOT NULL,
    low       REAL    NOT NULL,
    close     REAL    NOT NULL,
    volume    REAL    NOT NULL,
    UNIQUE(pair, timeframe, timestamp)
);

CREATE TABLE IF NOT EXISTS indicators (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    candle_id   INTEGER NOT NULL REFERENCES candles(id),
    ema20       REAL,
    ema50       REAL,
    ema200      REAL,
    rsi14       REAL,
    macd        REAL,
    macd_signal REAL,
    macd_hist   REAL,
    bb_upper    REAL,
    bb_mid      REAL,
    bb_lower    REAL,
    atr14       REAL,
    stoch_k     REAL,
    stoch_d     REAL
);

CREATE TABLE IF NOT EXISTS fetch_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   INTEGER NOT NULL,
    pair        TEXT    NOT NULL,
    timeframe   TEXT    NOT NULL,
    provider    TEXT    NOT NULL,
    status      TEXT    NOT NULL,
    error_msg   TEXT,
    duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS signals (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    pair              TEXT    NOT NULL,
    timeframe         TEXT    NOT NULL,
    timestamp         INTEGER NOT NULL,
    created_at        INTEGER NOT NULL,
    direction         TEXT    NOT NULL,
    confidence        REAL    NOT NULL,
    sl_pips           REAL,
    tp_pips           REAL,
    claude_direction  TEXT,
    claude_confidence REAL,
    gemini_direction  TEXT,
    gemini_confidence REAL,
    reasoning         TEXT,
    UNIQUE(pair, timeframe, timestamp)
);

CREATE TABLE IF NOT EXISTS account (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    balance    REAL    NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pair         TEXT    NOT NULL,
    timeframe    TEXT    NOT NULL,
    signal_id    INTEGER NOT NULL REFERENCES signals(id),
    direction    TEXT    NOT NULL,
    entry_price  REAL    NOT NULL,
    sl_price     REAL    NOT NULL,
    tp_price     REAL    NOT NULL,
    lot_size     REAL    NOT NULL,
    sl_pips      REAL    NOT NULL,
    tp_pips      REAL    NOT NULL,
    opened_at    INTEGER NOT NULL,
    closed_at    INTEGER,
    close_price  REAL,
    close_reason TEXT,
    pnl_pips     REAL,
    pnl_usd      REAL,
    status       TEXT    NOT NULL DEFAULT 'open'
);
