from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import candles, signals, status, trades, stats

app = FastAPI(title="Forex AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(candles.router, prefix="/api")
app.include_router(signals.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(trades.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
