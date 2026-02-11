"""Test Yahoo public market data fetch."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    module_path = ROOT / "custom_components" / "investment_tracker" / "api" / "yahoo.py"
    spec = importlib.util.spec_from_file_location("yahoo_public", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load yahoo module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _main() -> int:
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/test_yahoo_public.py <SYMBOL> [SYMBOL...]",
            file=sys.stderr,
        )
        return 2

    symbols = [s.replace("$", "").strip().upper() for s in sys.argv[1:] if s.strip()]
    if not symbols:
        print("No symbols provided", file=sys.stderr)
        return 2

    yahoo = _load_module()
    quotes = yahoo.get_quotes(symbols)
    for symbol in symbols:
        quote = quotes.get(symbol, {})
        print(
            f"{symbol}: price={quote.get('price')} currency={quote.get('currency')} timestamp={quote.get('timestamp')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
