from storage import store


class PaperBroker:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def open_trade(self, trade: dict) -> None:
        store.write_trade(self._db_path, trade)

    def close_trade(
        self,
        trade_id: int,
        close_price: float,
        close_reason: str,
        pnl_pips: float,
        pnl_usd: float,
    ) -> None:
        store.close_trade(self._db_path, trade_id, close_price, close_reason, pnl_pips, pnl_usd)
        balance = store.get_account_balance(self._db_path)
        store.update_account_balance(self._db_path, balance + pnl_usd)

    def get_balance(self) -> float:
        return store.get_account_balance(self._db_path)
