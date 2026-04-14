PIP_VALUE_PER_LOT = 10.0  # USD per pip per standard lot for EURUSD


def calculate_lot_size(balance: float, risk_pct: float, sl_pips: float) -> float:
    """
    Calculate EURUSD position size.

    Args:
        balance: Account balance in USD.
        risk_pct: Fraction of balance to risk (e.g. 0.01 = 1%).
        sl_pips: Stop-loss distance in pips.

    Returns:
        Lot size rounded to 2 decimal places, minimum 0.01.
        Returns 0.0 if sl_pips <= 0 or result is below minimum lot size.
    """
    if sl_pips <= 0:
        return 0.0
    risk_amount = balance * risk_pct
    raw = risk_amount / (sl_pips * PIP_VALUE_PER_LOT)
    lot = round(raw, 2)
    return lot if lot >= 0.01 else 0.0
