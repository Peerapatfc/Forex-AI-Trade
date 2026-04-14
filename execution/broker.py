from typing import Protocol, runtime_checkable


@runtime_checkable
class Broker(Protocol):
    def open_trade(self, trade: dict) -> None: ...

    def close_trade(
        self,
        trade_id: int,
        close_price: float,
        close_reason: str,
        pnl_pips: float,
        pnl_usd: float,
    ) -> None: ...

    def get_balance(self) -> float: ...
