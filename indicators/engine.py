import pandas as pd
import pandas_ta as ta


def calculate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all indicators on an OHLCV DataFrame.

    Input must have lowercase columns: open, high, low, close, volume.
    Returns a copy of df with indicator columns appended.
    Columns requiring more history than available will contain NaN.
    """
    df = df.copy()

    # Trend
    df["ema20"] = ta.ema(df["close"], length=20)
    df["ema50"] = ta.ema(df["close"], length=50)
    df["ema200"] = ta.ema(df["close"], length=200)

    # Momentum
    df["rsi14"] = ta.rsi(df["close"], length=14)

    macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
    if macd is not None and not macd.empty:
        df["macd"] = macd["MACD_12_26_9"]
        df["macd_signal"] = macd["MACDs_12_26_9"]
        df["macd_hist"] = macd["MACDh_12_26_9"]
    else:
        df["macd"] = df["macd_signal"] = df["macd_hist"] = float("nan")

    stoch = ta.stoch(df["high"], df["low"], df["close"], k=14, d=3, smooth_k=3)
    if stoch is not None and not stoch.empty:
        df["stoch_k"] = stoch["STOCHk_14_3_3"]
        df["stoch_d"] = stoch["STOCHd_14_3_3"]
    else:
        df["stoch_k"] = df["stoch_d"] = float("nan")

    # Volatility
    bb = ta.bbands(df["close"], length=20, std=2)
    if bb is not None and not bb.empty:
        suffix = "2.0_2.0" if "BBU_20_2.0_2.0" in bb.columns else "2.0"
        df["bb_upper"] = bb[f"BBU_20_{suffix}"]
        df["bb_mid"] = bb[f"BBM_20_{suffix}"]
        df["bb_lower"] = bb[f"BBL_20_{suffix}"]
    else:
        df["bb_upper"] = df["bb_mid"] = df["bb_lower"] = float("nan")

    df["atr14"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    return df


def latest_indicators(df: pd.DataFrame) -> dict:
    """
    Return indicator values for the most recent candle as a plain dict.
    Values that could not be computed (NaN) are returned as None.
    """
    result = calculate(df)
    last = result.iloc[-1]

    def safe(val):
        try:
            return None if pd.isna(val) else float(val)
        except (TypeError, ValueError):
            return None

    return {
        "ema20": safe(last.get("ema20")),
        "ema50": safe(last.get("ema50")),
        "ema200": safe(last.get("ema200")),
        "rsi14": safe(last.get("rsi14")),
        "macd": safe(last.get("macd")),
        "macd_signal": safe(last.get("macd_signal")),
        "macd_hist": safe(last.get("macd_hist")),
        "bb_upper": safe(last.get("bb_upper")),
        "bb_mid": safe(last.get("bb_mid")),
        "bb_lower": safe(last.get("bb_lower")),
        "atr14": safe(last.get("atr14")),
        "stoch_k": safe(last.get("stoch_k")),
        "stoch_d": safe(last.get("stoch_d")),
    }
