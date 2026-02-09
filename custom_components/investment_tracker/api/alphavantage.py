"""Alpha Vantage market data client."""
from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any
from typing import Dict

import requests

_LOGGER = logging.getLogger(__name__)


def _load_cache(cache_path: Path) -> dict[str, dict[str, Any]]:
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache_path: Path, cache: dict[str, dict[str, Any]]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:
        return


def get_quotes(symbols: list[str], api_key: str, cache_path: str | None = None) -> Dict[str, dict]:
    """Fetch latest quotes via Alpha Vantage GLOBAL_QUOTE.

    If cache_path is provided, cached values are used when the API returns no data
    (rate limit, errors, or empty response).
    """
    data: Dict[str, dict] = {}
    cache_file = Path(cache_path) if cache_path else None
    cache = _load_cache(cache_file) if cache_file else {}
    if not api_key:
        for symbol in symbols:
            data[symbol] = {"price": None, "currency": None, "timestamp": datetime.utcnow().isoformat()}
        return data

    for symbol in symbols:
        price = None
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": api_key,
            }
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                _LOGGER.debug("Alpha Vantage HTTP %s for %s", resp.status_code, symbol)
            else:
                payload = resp.json()
                if payload.get("Note") or payload.get("Error Message"):
                    _LOGGER.debug("Alpha Vantage rate limit or error for %s: %s", symbol, payload)
                else:
                    quote = payload.get("Global Quote") or payload.get("Global quote") or {}
                    price_str = quote.get("05. price") or quote.get("05. Price")
                    if price_str not in (None, ""):
                        price = float(price_str)
        except Exception as err:
            _LOGGER.debug("Alpha Vantage fetch failed for %s: %s", symbol, err)

        timestamp = datetime.utcnow().isoformat()
        if price is None and symbol in cache:
            cached = cache.get(symbol, {})
            data[symbol] = {
                "price": cached.get("price"),
                "currency": cached.get("currency"),
                "timestamp": cached.get("timestamp", timestamp),
            }
        else:
            data[symbol] = {
                "price": price,
                "currency": None,
                "timestamp": timestamp,
            }
            cache[symbol] = {"price": price, "currency": None, "timestamp": timestamp}

    if cache_file:
        _save_cache(cache_file, cache)

    return data
