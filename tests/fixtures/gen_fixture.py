"""
Run once to generate the test fixture:
    python tests/fixtures/gen_fixture.py
Produces tests/fixtures/eurusd_15m.json — 200 synthetic EUR/USD 15m candles.
Commit the output; the fixture is static input for offline tests.
"""
import json
import random
from pathlib import Path

random.seed(42)

BASE_PRICE = 1.0850
CANDLES = 200
INTERVAL_SECS = 900  # 15 minutes
START_TS = 1704067200  # 2024-01-01 00:00:00 UTC

rows = []
price = BASE_PRICE
for i in range(CANDLES):
    change = random.gauss(0, 0.0004)
    open_ = round(price, 5)
    close = round(price + change, 5)
    high = round(max(open_, close) + abs(random.gauss(0, 0.0002)), 5)
    low = round(min(open_, close) - abs(random.gauss(0, 0.0002)), 5)
    volume = round(random.uniform(500, 2000), 1)
    rows.append({
        "timestamp": START_TS + i * INTERVAL_SECS,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
    price = close

out = Path(__file__).parent / "eurusd_15m.json"
if out.exists():
    print(f"Fixture already exists at {out}. Delete it first to regenerate.")
    raise SystemExit(1)
out.write_text(json.dumps(rows, indent=2))
print(f"Written {len(rows)} candles to {out}")
