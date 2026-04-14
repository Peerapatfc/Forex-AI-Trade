class LiveBroker:
    def open_trade(self, trade: dict) -> None:
        raise NotImplementedError("Live execution not yet implemented")

    def close_trade(
        self,
        trade_id: int,
        close_price: float,
        close_reason: str,
        pnl_pips: float,
        pnl_usd: float,
    ) -> None:
        raise NotImplementedError("Live execution not yet implemented")

    def get_balance(self) -> float:
        raise NotImplementedError("Live execution not yet implemented")
