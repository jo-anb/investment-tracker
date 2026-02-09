"""Yahoo Finance client (public endpoints)."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Dict, Any

import requests

_LOGGER = logging.getLogger(__name__)

SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
QUOTETYPE_URL = "https://query1.finance.yahoo.com/v1/finance/quoteType/"
QUOTE_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _normalize_symbol(symbol: str) -> str:
    return symbol.replace("$", "").strip().upper()


def search_symbols(query: str) -> list[dict[str, Any]]:
    """Search Yahoo for possible symbol matches, including sector, industry, and logoUrl."""
    query = _normalize_symbol(query)
    if not query:
        return []
    try:
        params = {
            "q": query,
            "lang": "en-US",
            "region": "US",
            "quotesCount": 6,
            "newsCount": 0,
            "listsCount": 0,
            "enableFuzzyQuery": "false",
            "quotesQueryId": "tss_match_phrase_query",
            "multiQuoteQueryId": "multi_quote_single_token_query",
            "enableCb": "false",
            "enableNavLinks": "true",
            "enableEnhancedTrivialQuery": "true",
            "enableResearchReports": "true",
            "enableCulturalAssets": "true",
            "enableLogoUrl": "true",
            "enableLists": "false",
            "recommendCount": 5,
            "enableCccBoost": "true",
            "enablePrivateCompany": "true",
        }
        _LOGGER.debug("Yahoo search request url=%s params=%s", SEARCH_URL, params)
        resp = requests.get(SEARCH_URL, params=params, timeout=15, headers=DEFAULT_HEADERS)
        _LOGGER.debug("Yahoo search response status=%s text=%s", resp.status_code, resp.text[:500])
        if resp.status_code != 200:
            return []
        payload = resp.json()
        quotes = payload.get("quotes", [])
        results = []
        for q in quotes:
            symbol = q.get("symbol")
            if not symbol:
                continue
            # Enrich with all available fields from search API
            sector = q.get("sector")
            industry = q.get("industry")
            logo_url = q.get("logoUrl") or q.get("logo_url")
            quote_type = q.get("quoteType")
            exchange_disp = q.get("exchDisp")
            short_name = q.get("shortName")
            long_name = q.get("longName")
            results.append({
                "symbol": symbol,
                "sector": sector,
                "industry": industry,
                "logoUrl": logo_url,
                "quoteType": quote_type,
                "exchange": exchange_disp,
                "shortName": short_name,
                "longName": long_name,
            })
        return results[:10]
    except Exception as err:
        _LOGGER.debug("Yahoo search failed for %s: %s", query, err)
        return []


def get_quote_type(symbol: str) -> dict[str, Any] | None:
    """Fetch quote type info for a symbol."""
    symbol = _normalize_symbol(symbol)
    if not symbol:
        return None
    try:
        params = {
            "symbol": symbol,
            "lang": "en-US",
            "region": "US",
            "enablePrivateCompany": "true",
        }
        _LOGGER.debug("Yahoo quoteType request url=%s params=%s", QUOTETYPE_URL, params)
        resp = requests.get(QUOTETYPE_URL, params=params, timeout=15, headers=DEFAULT_HEADERS)
        _LOGGER.debug("Yahoo quoteType response status=%s text=%s", resp.status_code, resp.text[:500])
        if resp.status_code != 200:
            return None
        payload = resp.json()
        result = payload.get("quoteType", {}).get("result", [])
        return result[0] if result else None
    except Exception as err:
        _LOGGER.debug("Yahoo quoteType failed for %s: %s", symbol, err)
        return None


def get_summary_profile(symbol: str) -> dict[str, Any] | None:
    """Fetch summaryProfile data for a symbol."""
    symbol = _normalize_symbol(symbol)
    if not symbol:
        return None
    try:
        params = {
            "formatted": "true",
            "modules": "summaryProfile",
            "enablePrivateCompany": "true",
            "enableQSPExpandedEarnings": "true",
            "overnightPrice": "true",
            "lang": "en-US",
            "region": "US",
        }
        _LOGGER.debug("Yahoo quoteSummary request url=%s params=%s", QUOTE_SUMMARY_URL.format(symbol=symbol), params)
        resp = requests.get(
            QUOTE_SUMMARY_URL.format(symbol=symbol),
            params=params,
            timeout=15,
            headers=DEFAULT_HEADERS,
        )
        _LOGGER.debug("Yahoo quoteSummary response status=%s text=%s", resp.status_code, resp.text[:500])
        if resp.status_code != 200:
            return None
        payload = resp.json()
        result = payload.get("quoteSummary", {}).get("result", [])
        if not result:
            return None
        return result[0].get("summaryProfile") or None
    except Exception as err:
        _LOGGER.debug("Yahoo summaryProfile failed for %s: %s", symbol, err)
        return None


def get_quotes(symbols: list[str]) -> Dict[str, dict]:
    """Fetch latest quotes via Yahoo chart endpoint."""
    if not symbols:
        return {}

    now = datetime.utcnow()
    period2 = int(now.timestamp())
    period1 = int((now - timedelta(days=3)).timestamp())

    data: Dict[str, dict] = {}
    for symbol in symbols:
        symbol = _normalize_symbol(symbol)
        if not symbol:
            continue
        price = None
        currency = None
        timestamp = now.isoformat()
        try:
            params = {
                "period1": str(period1),
                "period2": str(period2),
                "interval": "1m",
                "includePrePost": "true",
                "events": "div|split|earn",
                "lang": "en-US",
                "region": "US",
                "source": "cosaic",
            }
            _LOGGER.debug("Yahoo chart request url=%s params=%s", CHART_URL.format(symbol=symbol), params)
            resp = requests.get(
                CHART_URL.format(symbol=symbol),
                params=params,
                timeout=15,
                headers=DEFAULT_HEADERS,
            )
            _LOGGER.debug("Yahoo chart response status=%s text=%s", resp.status_code, resp.text[:500])
            if resp.status_code == 200:
                payload = resp.json()
                chart = payload.get("chart", {}) or {}
                if chart.get("error"):
                    _LOGGER.debug("Yahoo chart error for %s: %s", symbol, chart.get("error"))
                result = chart.get("result", [])
                if result:
                    meta = result[0].get("meta", {})
                    price = meta.get("regularMarketPrice")
                    currency = meta.get("currency")
                    ts = meta.get("regularMarketTime")
                    if ts:
                        timestamp = datetime.utcfromtimestamp(ts).isoformat()
            else:
                _LOGGER.debug("Yahoo chart HTTP %s for %s", resp.status_code, symbol)
        except Exception as err:
            _LOGGER.debug("Yahoo chart fetch failed for %s: %s", symbol, err)

        data[symbol] = {
            "price": price,
            "currency": currency,
            "timestamp": timestamp,
        }

    return data
