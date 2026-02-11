from __future__ import annotations

import argparse

import requests


def fetch(symbol: str) -> float | None:
    url = "https://stooq.com/q/l/"
    params = {"s": symbol.lower(), "f": "sd2t2ohlcv", "h": "", "e": "csv"}
    resp = requests.get(url, params=params, timeout=10)
    if resp.status_code != 200:
        return None
    lines = resp.text.strip().splitlines()
    if len(lines) < 2:
        return None
    header = lines[0].split(",")
    row = lines[1].split(",")
    row_map = dict(zip(header, row, strict=False))
    close_val = row_map.get("Close")
    if close_val in (None, "", "N/A"):
        return None
    return float(close_val)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Stooq fetch.")
    parser.add_argument(
        "symbols", nargs="*", default=["NVDA.US", "GOOGL.US"], help="Symbols to fetch"
    )
    args = parser.parse_args()

    for symbol in args.symbols:
        price = fetch(symbol)
        print(f"{symbol}: price={price}")


if __name__ == "__main__":
    main()
