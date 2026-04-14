import pandas as pd


def build(
    candles_1h: pd.DataFrame,
    candles_15m: pd.DataFrame,
    indicators: dict,
) -> str:
    """Build the structured prompt string for AI model analysis."""

    def format_candles(df: pd.DataFrame) -> str:
        rows = []
        for _, row in df.iterrows():
            ts = pd.Timestamp(int(row["timestamp"]), unit="s", tz="UTC").strftime("%Y-%m-%d %H:%M")
            rows.append(
                f"{ts}, {float(row['open']):.5f}, {float(row['high']):.5f}, "
                f"{float(row['low']):.5f}, {float(row['close']):.5f}, {float(row['volume']):.0f}"
            )
        return "\n".join(rows)

    def fmt(val, decimals: int = 5) -> str:
        if val is None:
            return "N/A"
        try:
            f = float(val)
            if f != f:  # NaN check
                return "N/A"
            return f"{f:.{decimals}f}"
        except (TypeError, ValueError):
            return "N/A"

    ind = (
        f"EMA20: {fmt(indicators.get('ema20'))} | "
        f"EMA50: {fmt(indicators.get('ema50'))} | "
        f"EMA200: {fmt(indicators.get('ema200'))}\n"
        f"RSI14: {fmt(indicators.get('rsi14'), 1)} | "
        f"MACD: {fmt(indicators.get('macd'))} | "
        f"Signal: {fmt(indicators.get('macd_signal'))} | "
        f"Hist: {fmt(indicators.get('macd_hist'))}\n"
        f"BB Upper: {fmt(indicators.get('bb_upper'))} | "
        f"Mid: {fmt(indicators.get('bb_mid'))} | "
        f"Lower: {fmt(indicators.get('bb_lower'))}\n"
        f"ATR14: {fmt(indicators.get('atr14'))} | "
        f"Stoch K: {fmt(indicators.get('stoch_k'), 1)} | "
        f"Stoch D: {fmt(indicators.get('stoch_d'), 1)}"
    )

    return (
        "You are a professional Forex analyst. Analyze the following EUR/USD market data "
        "and return a trading signal as JSON.\n\n"
        f"## 1-Hour Context (last {len(candles_1h)} candles — trend/bias)\n"
        "timestamp, open, high, low, close, volume\n"
        f"{format_candles(candles_1h)}\n\n"
        f"## 15-Minute Context (last {len(candles_15m)} candles — entry timing)\n"
        "timestamp, open, high, low, close, volume\n"
        f"{format_candles(candles_15m)}\n\n"
        "## Current Indicators (15m)\n"
        f"{ind}\n\n"
        "## Instructions\n"
        "Return ONLY valid JSON, no markdown, no explanation outside the JSON:\n"
        "{\n"
        '  "direction": "BUY" | "SELL" | "HOLD",\n'
        '  "confidence": 0.0-1.0,\n'
        '  "sl_pips": <number or null>,\n'
        '  "tp_pips": <number or null>,\n'
        '  "reasoning": "<one sentence>"\n'
        "}\n"
        "Rules: sl_pips and tp_pips must be null when direction is HOLD.\n"
        "confidence reflects certainty (0.5 = uncertain, 1.0 = very confident)."
    )
