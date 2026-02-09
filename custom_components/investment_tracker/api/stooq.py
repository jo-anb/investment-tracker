"""Stooq market data client."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Dict

import requests

_LOGGER = logging.getLogger(__name__)


def _normalize_symbol(symbol: str) -> str:
    return symbol.replace("$", "").strip().upper()


def _stooq_symbols(symbol: str) -> list[str]:
    sym = _normalize_symbol(symbol)
    if not sym:
        return []
    # If already has suffix (e.g., .US, .DE), try as-is first.
    if "." in sym:
        return [sym]
    return [f"{sym}.US", f"{sym}.DE", f"{sym}.UK", f"{sym}.L", f"{sym}.F", f"{sym}.PL", sym]


def suggest_symbols(symbol: str) -> list[str]:
    """Return close matches based on Stooq availability."""
    candidates = _stooq_symbols(symbol)
    matches: list[str] = []
    for candidate in candidates:
        try:
            url = "https://stooq.com/q/l/"
            params = {"s": candidate.lower(), "f": "sd2t2ohlcv", "h": "", "e": "csv"}
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                continue
            lines = resp.text.strip().splitlines()
            if len(lines) < 2:
                continue
            header = lines[0].split(",")
            row = lines[1].split(",")
            row_map = dict(zip(header, row))
            close_val = row_map.get("Close")
            if close_val in (None, "", "N/A"):
                continue
            matches.append(candidate)
        except Exception as err:
            _LOGGER.debug("Stooq suggest failed for %s: %s", candidate, err)
            continue
    return matches[:10]


def get_quotes(symbols: list[str]) -> Dict[str, dict]:
    """Fetch latest quotes via Stooq CSV API."""
    data: Dict[str, dict] = {}
    for symbol in symbols:
        candidates = _stooq_symbols(symbol)
        price = None
        currency = None
        used_symbol = None

        for candidate in candidates:
            try:
                url = "https://stooq.com/q/l/"
                params = {"s": candidate.lower(), "f": "sd2t2ohlcv", "h": "", "e": "csv"}
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code != 200:
                    continue
                lines = resp.text.strip().splitlines()
                if len(lines) < 2:
                    continue
                header = lines[0].split(",")
                row = lines[1].split(",")
                row_map = dict(zip(header, row))
                close_val = row_map.get("Close")
                if close_val in (None, "", "N/A"):
                    continue
                price = float(close_val)
                used_symbol = candidate
                break
            except Exception as err:
                _LOGGER.debug("Stooq fetch failed for %s: %s", candidate, err)
                continue

        data[symbol] = {
            "price": price,
            "currency": currency,
            "timestamp": datetime.utcnow().isoformat(),
            "source_symbol": used_symbol,
        }

    return data
