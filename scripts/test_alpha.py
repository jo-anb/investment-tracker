"""Test Alpha Vantage market data fetch."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import importlib.util


def _load_get_quotes():
    module_path = (
        ROOT / "custom_components" / "investment_tracker" / "api" / "alphavantage.py"
    )
    spec = importlib.util.spec_from_file_location("alphavantage", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load alphavantage module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_quotes


get_quotes = _load_get_quotes()


def _main() -> int:
    if len(sys.argv) < 3:
        print(
            "Usage: python scripts/test_alpha.py <API_KEY> <SYMBOL> [SYMBOL...]",
            file=sys.stderr,
        )
        return 2

    api_key = sys.argv[1].strip()
    symbols = [s.replace("$", "").strip().upper() for s in sys.argv[2:] if s.strip()]
    if not symbols:
        print("No symbols provided", file=sys.stderr)
        return 2

    cache_path = ROOT / "scripts" / ".alpha_cache.json"
    quotes = get_quotes(symbols, api_key, str(cache_path))
    for symbol in symbols:
        quote = quotes.get(symbol, {})
        print(
            f"{symbol}: price={quote.get('price')} currency={quote.get('currency')} timestamp={quote.get('timestamp')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
