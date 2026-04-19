import logging
import MetaTrader5 as mt5
from storage import store

logger = logging.getLogger(__name__)

MT5_MAGIC = 20240101  # magic number to identify our bot's orders


class LiveBroker:
    def __init__(self, db_path: str, login: int, password: str, server: str) -> None:
        self._db_path = db_path
        self._login = login
        self._password = password
        self._server = server
        self._connect()

    def _connect(self) -> None:
        if not mt5.initialize():
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        if not mt5.login(self._login, self._password, self._server):
            mt5.shutdown()
            raise RuntimeError(f"MT5 login failed: {mt5.last_error()}")
        logger.info("MT5 connected: account %d on %s", self._login, self._server)

    def open_trade(self, trade: dict) -> None:
        symbol = trade["pair"]
        direction = trade["direction"]
        lot = float(trade["lot_size"])
        sl = float(trade["sl_price"])
        tp = float(trade["tp_price"])

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"MT5 symbol_info_tick failed for {symbol}: {mt5.last_error()}")
        price = tick.ask if direction == "BUY" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "magic": MT5_MAGIC,
            "comment": "forex-ai",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = mt5.last_error() if result is None else result.retcode
            raise RuntimeError(f"MT5 order_send failed: {error}")

        trade_id = store.write_trade(self._db_path, trade)
        store.set_trade_ticket(self._db_path, trade_id, result.order)
        logger.info("Opened %s %s lot=%.2f ticket=%d", direction, symbol, lot, result.order)

    def close_trade(
        self,
        trade_id: int,
        close_price: float,
        close_reason: str,
        pnl_pips: float,
        pnl_usd: float,
    ) -> None:
        ticket = store.get_trade_ticket(self._db_path, trade_id)
        if ticket is None:
            raise RuntimeError(f"No MT5 ticket for trade {trade_id}")

        position = mt5.positions_get(ticket=ticket)
        if not position:
            logger.warning("MT5 position %d not found (may already be closed)", ticket)
        else:
            pos = position[0]
            symbol = pos.symbol
            lot = pos.volume
            # Close by opposite order
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                raise RuntimeError(f"MT5 symbol_info_tick failed for {symbol}: {mt5.last_error()}")
            price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
            order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot,
                "type": order_type,
                "price": price,
                "position": ticket,
                "magic": MT5_MAGIC,
                "comment": f"close-{close_reason}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                error = mt5.last_error() if result is None else result.retcode
                raise RuntimeError(f"MT5 close order failed: {error}")
            logger.info("Closed MT5 ticket %d reason=%s", ticket, close_reason)

        store.close_trade(self._db_path, trade_id, close_price, close_reason, pnl_pips, pnl_usd)

    def get_balance(self) -> float:
        info = mt5.account_info()
        if info is None:
            raise RuntimeError(f"MT5 account_info failed: {mt5.last_error()}")
        return float(info.equity)

    def shutdown(self) -> None:
        mt5.shutdown()
        logger.info("MT5 disconnected")
