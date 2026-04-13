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
