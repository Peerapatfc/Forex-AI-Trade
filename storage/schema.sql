CREATE TABLE IF NOT EXISTS candles (
    id        BIGSERIAL PRIMARY KEY,
    pair      TEXT             NOT NULL,
    timeframe TEXT             NOT NULL,
    timestamp BIGINT           NOT NULL,
    open      DOUBLE PRECISION NOT NULL,
    high      DOUBLE PRECISION NOT NULL,
    low       DOUBLE PRECISION NOT NULL,
    close     DOUBLE PRECISION NOT NULL,
    volume    DOUBLE PRECISION NOT NULL,
    UNIQUE(pair, timeframe, timestamp)
);

CREATE TABLE IF NOT EXISTS indicators (
    id          BIGSERIAL PRIMARY KEY,
    candle_id   BIGINT REFERENCES candles(id),
    ema20       DOUBLE PRECISION,
    ema50       DOUBLE PRECISION,
    ema200      DOUBLE PRECISION,
    rsi14       DOUBLE PRECISION,
    macd        DOUBLE PRECISION,
    macd_signal DOUBLE PRECISION,
    macd_hist   DOUBLE PRECISION,
    bb_upper    DOUBLE PRECISION,
    bb_mid      DOUBLE PRECISION,
    bb_lower    DOUBLE PRECISION,
    atr14       DOUBLE PRECISION,
    stoch_k     DOUBLE PRECISION,
    stoch_d     DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS fetch_log (
    id          BIGSERIAL PRIMARY KEY,
    timestamp   BIGINT NOT NULL,
    pair        TEXT   NOT NULL,
    timeframe   TEXT   NOT NULL,
    provider    TEXT   NOT NULL,
    status      TEXT   NOT NULL,
    error_msg   TEXT,
    duration_ms BIGINT
);

CREATE TABLE IF NOT EXISTS signals (
    id                BIGSERIAL PRIMARY KEY,
    pair              TEXT             NOT NULL,
    timeframe         TEXT             NOT NULL,
    timestamp         BIGINT           NOT NULL,
    created_at        BIGINT           NOT NULL,
    direction         TEXT             NOT NULL,
    confidence        DOUBLE PRECISION NOT NULL,
    sl_pips           DOUBLE PRECISION,
    tp_pips           DOUBLE PRECISION,
    claude_direction  TEXT,
    claude_confidence DOUBLE PRECISION,
    gemini_direction  TEXT,
    gemini_confidence DOUBLE PRECISION,
    reasoning         TEXT,
    UNIQUE(pair, timeframe, timestamp)
);

CREATE TABLE IF NOT EXISTS account (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    balance    DOUBLE PRECISION NOT NULL,
    updated_at BIGINT           NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id           BIGSERIAL PRIMARY KEY,
    pair         TEXT             NOT NULL,
    timeframe    TEXT             NOT NULL,
    signal_id    BIGINT           NOT NULL REFERENCES signals(id),
    direction    TEXT             NOT NULL,
    entry_price  DOUBLE PRECISION NOT NULL,
    sl_price     DOUBLE PRECISION NOT NULL,
    tp_price     DOUBLE PRECISION NOT NULL,
    lot_size     DOUBLE PRECISION NOT NULL,
    sl_pips      DOUBLE PRECISION NOT NULL,
    tp_pips      DOUBLE PRECISION NOT NULL,
    opened_at    BIGINT           NOT NULL,
    closed_at    BIGINT,
    close_price  DOUBLE PRECISION,
    close_reason TEXT,
    pnl_pips     DOUBLE PRECISION,
    pnl_usd      DOUBLE PRECISION,
    mt5_ticket   BIGINT,
    status       TEXT             NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS stats (
    pair             TEXT             NOT NULL PRIMARY KEY,
    updated_at       BIGINT           NOT NULL,
    trade_count      INTEGER          NOT NULL DEFAULT 0,
    win_count        INTEGER          NOT NULL DEFAULT 0,
    loss_count       INTEGER          NOT NULL DEFAULT 0,
    win_rate         DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_pnl_pips   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_pnl_usd    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_win_pips     DOUBLE PRECISION,
    avg_loss_pips    DOUBLE PRECISION,
    profit_factor    DOUBLE PRECISION,
    max_drawdown_usd DOUBLE PRECISION NOT NULL DEFAULT 0.0
);
