import pytest
from execution.position_sizer import calculate_lot_size


def test_normal_case():
    # $10,000 * 1% / (15 pips * $10/pip/lot) = $100 / $150 = 0.6666... → 0.67
    result = calculate_lot_size(10000.0, 0.01, 15.0)
    assert result == pytest.approx(0.67)


def test_large_balance():
    # $100,000 * 2% / (20 pips * $10) = $2,000 / $200 = 10.0 lots
    result = calculate_lot_size(100000.0, 0.02, 20.0)
    assert result == pytest.approx(10.0)


def test_sl_pips_zero_returns_zero():
    result = calculate_lot_size(10000.0, 0.01, 0.0)
    assert result == 0.0


def test_sl_pips_negative_returns_zero():
    result = calculate_lot_size(10000.0, 0.01, -5.0)
    assert result == 0.0


def test_result_below_minimum_returns_zero():
    # $100 * 1% / (1000 pips * $10) = $1 / $10,000 = 0.0001 → rounds to 0.0
    result = calculate_lot_size(100.0, 0.01, 1000.0)
    assert result == 0.0


def test_rounds_to_two_decimal_places():
    # $10,000 * 1% / (7 pips * $10) = $100 / $70 = 1.42857... → 1.43
    result = calculate_lot_size(10000.0, 0.01, 7.0)
    assert result == pytest.approx(1.43)
