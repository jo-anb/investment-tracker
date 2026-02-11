"""Helper utilities for Investment Tracker."""
from __future__ import annotations

import csv
from datetime import datetime
from typing import Dict, Optional

DEFAULT_SYMBOL_MAPPING: Dict[str, Dict[str, str]] = {
    "default": {
        "XAU": "XAUUSD=X",
        "VWCE": "VWCE.DE",
    }
}


def map_symbol(broker: str, symbol: str, mapping: Dict[str, Dict[str, str]] | None = None) -> Optional[str]:
    """Map broker symbol to Yahoo symbol if available."""
    if not mapping:
        return symbol
    broker_map = mapping.get(broker, {})
    default_map = mapping.get("default", {})
    return broker_map.get(symbol, default_map.get(symbol, symbol))


def get_default_symbol_mapping() -> Dict[str, Dict[str, str]]:
    """Return default Yahoo symbol mappings."""
    return DEFAULT_SYMBOL_MAPPING


def parse_positions_csv(path: str, default_broker: str | None = None) -> list[dict[str, object]]:
    """Parse canonical positions CSV into list of position dicts."""
    positions: list[dict[str, object]] = []
    with open(path, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if not row.get("symbol"):
                continue
            broker = row.get("broker") or default_broker or "csv"
            positions.append(
                {
                    "symbol": row.get("symbol").strip().upper(),
                    "name": row.get("name") or row.get("symbol"),
                    "type": row.get("type", "equity"),
                "manual_type": str(row.get("manual_type", "false")).lower() == "true",
                    "quantity": float(row.get("quantity", 0) or 0),
                    "avg_buy_price": float(row.get("avg_buy_price", 0) or 0),
                    "currency": row.get("currency"),
                    "broker": broker,
                    "unmapped": str(row.get("unmapped", "false")).lower() == "true",
                }
            )
    return positions


def _to_float(value: str | None) -> float:
    if value is None:
        return 0.0
    value = value.strip()
    if not value:
        return 0.0
    value = value.replace("EUR", "").replace("USD", "").replace("GBP", "").replace("PLN", "")
    value = value.replace(" ", "")
    value = value.replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return 0.0


def parse_transactions_csv(path: str, broker: str) -> list[dict[str, object]]:
    """Parse broker transaction CSVs into canonical transactions."""
    transactions: list[dict[str, object]] = []
    with open(path, newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, [])
        if not header:
            return transactions

        csvfile.seek(0)
        rows = list(csv.reader(csvfile))

        # Revolut format
        if "Date" in header and "Ticker" in header and "Type" in header:
            csvfile.seek(0)
            dict_reader = csv.DictReader(csvfile)
            for row in dict_reader:
                symbol = (row.get("Ticker") or "").strip().upper()
                if not symbol:
                    continue
                quantity = _to_float(row.get("Quantity"))
                price = _to_float(row.get("Price per share"))
                currency = (row.get("Currency") or "").strip().upper()
                tx_type = (row.get("Type") or "").upper()
                if "SELL" in tx_type:
                    quantity = -abs(quantity)
                else:
                    quantity = abs(quantity)
                transactions.append(
                    {
                        "symbol": symbol,
                        "name": symbol,
                        "quantity": quantity,
                        "price": price,
                        "currency": currency,
                        "broker": broker,
                        "date": row.get("Date"),
                    }
                )
            return transactions

        # DeGiro format (Dutch headers)
        if "Datum" in header and "Product" in header and "Aantal" in header:
            idx = {name: i for i, name in enumerate(header)}
            header_len = len(header)
            for row in rows[1:]:
                if not row:
                    continue
                if len(row) < header_len:
                    row = row + [""] * (header_len - len(row))
                symbol = (row[idx.get("ISIN", -1)] if idx.get("ISIN", -1) >= 0 else "").strip()
                name = (row[idx.get("Product", -1)] if idx.get("Product", -1) >= 0 else "").strip()
                quantity = _to_float(row[idx.get("Aantal", -1)] if idx.get("Aantal", -1) >= 0 else "0")
                price = _to_float(row[idx.get("Koers", -1)] if idx.get("Koers", -1) >= 0 else "0")

                # Try to get local currency from column after "Lokale waarde"
                currency = ""
                if "Lokale waarde" in idx:
                    cur_idx = idx["Lokale waarde"] + 1
                    if cur_idx < len(row):
                        currency = row[cur_idx].strip()
                currency = currency or "EUR"

                if not symbol and not name:
                    continue

                transactions.append(
                    {
                        "symbol": symbol or name,
                        "name": name or symbol,
                        "quantity": quantity,
                        "price": price,
                        "currency": currency,
                        "broker": broker,
                        "date": f"{row[idx.get('Datum', 0)]} {row[idx.get('Tijd', 0)]}",
                    }
                )
            return transactions

    return transactions


def apply_transactions_to_positions(
    positions: list[dict[str, object]],
    transactions: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Recompute quantities and avg_buy_price from transactions."""

    def _norm(value: str | None) -> str:
        return (value or "").strip().lower()

    def _sym(value: str | None) -> str:
        return (value or "").strip().upper()

    pos_index: dict[tuple[str, str], dict[str, object]] = {}
    symbol_brokers: dict[str, set[str]] = {}
    for pos in positions:
        broker = _norm(str(pos.get("broker", "unknown"))) or "unknown"
        symbol = _sym(str(pos.get("symbol", "")))
        if not symbol:
            continue
        key = (broker, symbol)
        pos_index[key] = {**pos, "broker": broker, "symbol": symbol}
        symbol_brokers.setdefault(symbol, set()).add(broker)

    # Sort by date if possible
    def _parse_date(value: str | None) -> datetime:
        if not value:
            return datetime.min.replace(tzinfo=datetime.now().astimezone().tzinfo)
        value = str(value).strip()
        tzinfo = datetime.now().astimezone().tzinfo
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=tzinfo)
            return parsed
        except Exception:
            pass
        for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.replace(tzinfo=tzinfo)
            except Exception:
                continue
        return datetime.min.replace(tzinfo=tzinfo)

    for tx in sorted(transactions, key=lambda t: _parse_date(str(t.get("date")))):
        broker = _norm(str(tx.get("broker", "unknown"))) or "unknown"
        symbol = _sym(str(tx.get("symbol", "")))
        if not symbol:
            continue
        key = (broker, symbol)
        current = pos_index.get(key)
        if current is None:
            candidates = symbol_brokers.get(symbol, set())
            if len(candidates) == 1:
                broker = next(iter(candidates))
                key = (broker, symbol)
                current = pos_index.get(key, {})
            else:
                current = {}
        qty_old = float(current.get("quantity", 0) or 0)
        avg_old = float(current.get("avg_buy_price", 0) or 0)

        qty_tx = float(tx.get("quantity", 0) or 0)
        price = float(tx.get("price", 0) or 0)

        qty_new = qty_old + qty_tx

        if qty_tx > 0:
            # Buy
            total_cost = (avg_old * qty_old) + (price * qty_tx)
            avg_new = total_cost / qty_new if qty_new else 0
        else:
            # Sell: keep avg cost for remaining shares
            avg_new = avg_old if qty_new > 0 else 0

        pos_index[key] = {
            **current,
            "symbol": symbol,
            "name": current.get("name") or tx.get("name") or symbol,
            "type": current.get("type") or "equity",
            "quantity": max(qty_new, 0),
            "avg_buy_price": avg_new,
            "currency": current.get("currency") or tx.get("currency"),
            "broker": broker,
        }

    return list(pos_index.values())


def compute_realized_profit_loss(transactions: list[dict[str, object]]) -> float:
    """Compute realized profit/loss from transactions using average cost."""

    def _parse_date(value: str | None) -> datetime:
        if not value:
            return datetime.min.replace(tzinfo=datetime.now().astimezone().tzinfo)
        value = str(value).strip()
        tzinfo = datetime.now().astimezone().tzinfo
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=tzinfo)
            return parsed
        except Exception:
            pass
        for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y"):
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.replace(tzinfo=tzinfo)
            except Exception:
                continue
        return datetime.min.replace(tzinfo=tzinfo)

    def _norm(value: str | None) -> str:
        return (value or "").strip().lower()

    def _sym(value: str | None) -> str:
        return (value or "").strip().upper()

    realized = 0.0
    positions: dict[tuple[str, str], dict[str, float]] = {}

    for tx in sorted(transactions, key=lambda t: _parse_date(str(t.get("date")))):
        broker = _norm(str(tx.get("broker", "unknown"))) or "unknown"
        symbol = _sym(str(tx.get("symbol", "")))
        if not symbol:
            continue

        qty_tx = float(tx.get("quantity", 0) or 0)
        price = float(tx.get("price", 0) or 0)
        key = (broker, symbol)
        current = positions.get(key, {"qty": 0.0, "avg": 0.0})
        qty_old = current["qty"]
        avg_old = current["avg"]

        if qty_tx > 0:
            total_cost = (avg_old * qty_old) + (price * qty_tx)
            qty_new = qty_old + qty_tx
            avg_new = total_cost / qty_new if qty_new else 0.0
            positions[key] = {"qty": qty_new, "avg": avg_new}
        elif qty_tx < 0:
            qty_sell = abs(qty_tx)
            qty_available = max(qty_old, 0)
            qty_used = min(qty_sell, qty_available)
            realized += (price - avg_old) * qty_used
            qty_new = qty_old - qty_sell
            if qty_new < 0:
                qty_new = 0.0
            positions[key] = {"qty": qty_new, "avg": avg_old if qty_new > 0 else 0.0}

    return realized


def compute_total_cash_invested(
    transactions: list[dict[str, object]],
    asset_types: dict[str, str] | None = None,
) -> float:
    """Return total cash invested (sum of buy transactions)."""

    normalized_types = {}
    if asset_types:
        for symbol, asset_type in asset_types.items():
            if symbol:
                normalized_types[symbol.strip().upper()] = (asset_type or "").strip().lower()

    total = 0.0
    for tx in transactions:
        quantity = float(tx.get("quantity", 0) or 0)
        if quantity <= 0:
            continue
        price = float(tx.get("price", 0) or 0)
        if not price:
            continue
        symbol = (tx.get("symbol") or "").strip().upper()
        asset_type = normalized_types.get(symbol, "")
        if asset_type == "bond":
            total += (price / 100) * quantity
        else:
            total += price * quantity
    return total
