"""Yahoo Finance client (yfinance)."""
from __future__ import annotations

from datetime import datetime
from typing import Dict

import yfinance as yf


def get_quotes(symbols: list[str]) -> Dict[str, dict]:
    """Fetch latest quotes via yfinance."""
    if not symbols:
        return {}

    data = {}
    tickers = yf.Tickers(" ".join(symbols))
    for symbol, ticker in tickers.tickers.items():
        price = ticker.fast_info.get("lastPrice") if ticker.fast_info else None
        currency = ticker.fast_info.get("currency") if ticker.fast_info else None
        data[symbol] = {
            "price": price,
            "currency": currency,
            "timestamp": datetime.utcnow().isoformat(),
        }
    return data
