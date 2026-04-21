import logging
import smtplib
import ssl
from email.message import EmailMessage

import requests  # already in requirements.txt

logger = logging.getLogger(__name__)


class Alerter:
    """Send notifications via Telegram and/or email. Both channels are optional."""

    def __init__(
        self,
        telegram_token: str = "",
        telegram_chat_id: str = "",
        smtp_host: str = "",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
        smtp_to: str = "",
    ) -> None:
        self._tg_token = telegram_token
        self._tg_chat_id = telegram_chat_id
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._smtp_to = smtp_to

    def _telegram_enabled(self) -> bool:
        return bool(self._tg_token and self._tg_chat_id)

    def _email_enabled(self) -> bool:
        return bool(self._smtp_host and self._smtp_user and self._smtp_to)

    def send(self, subject: str, body: str) -> None:
        """Send alert to all configured channels. Never raises."""
        if self._telegram_enabled():
            self._send_telegram(f"*{subject}*\n{body}")
        if self._email_enabled():
            self._send_email(subject, body)

    def _send_telegram(self, text: str) -> None:
        try:
            url = f"https://api.telegram.org/bot{self._tg_token}/sendMessage"
            resp = requests.post(
                url,
                json={"chat_id": self._tg_chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=10,
            )
            resp.raise_for_status()
            logger.debug("Telegram alert sent")
        except Exception as exc:
            logger.error("Telegram alert failed: %s", exc)

    def _send_email(self, subject: str, body: str) -> None:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self._smtp_user
            msg["To"] = self._smtp_to
            msg.set_content(body)
            context = ssl.create_default_context()
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as smtp:
                smtp.starttls(context=context)
                smtp.login(self._smtp_user, self._smtp_password)
                smtp.send_message(msg)
            logger.debug("Email alert sent to %s", self._smtp_to)
        except Exception as exc:
            logger.error("Email alert failed: %s", exc)

    def alert_trade_opened(self, trade: dict) -> None:
        direction = trade.get("direction", "?")
        pair = trade.get("pair", "?")
        entry = trade.get("entry_price", 0.0)
        lot = trade.get("lot_size", 0.0)
        sl = trade.get("sl_price", 0.0)
        tp = trade.get("tp_price", 0.0)
        subject = f"Trade Opened: {direction} {pair}"
        body = (
            f"Direction: {direction}\n"
            f"Pair: {pair}\n"
            f"Entry: {entry:.5f}\n"
            f"Lot: {lot:.2f}\n"
            f"SL: {sl:.5f}\n"
            f"TP: {tp:.5f}"
        )
        self.send(subject, body)

    def alert_trade_closed(self, trade_id: int, pair: str, direction: str,
                           close_reason: str, pnl_pips: float, pnl_usd: float) -> None:
        emoji = "\u2705" if pnl_usd >= 0 else "\u274c"
        subject = f"{emoji} Trade Closed: {direction} {pair} ({close_reason.upper()})"
        body = (
            f"Trade ID: {trade_id}\n"
            f"Direction: {direction}\n"
            f"Pair: {pair}\n"
            f"Reason: {close_reason.upper()}\n"
            f"P&L: {pnl_pips:+.1f} pips / ${pnl_usd:+.2f}"
        )
        self.send(subject, body)

    def alert_error(self, component: str, error: str) -> None:
        subject = f"Error in {component}"
        body = f"Component: {component}\nError: {error}"
        self.send(subject, body)
