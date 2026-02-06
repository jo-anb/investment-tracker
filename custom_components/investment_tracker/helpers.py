"""Helper utilities for Investment Tracker."""
from __future__ import annotations

from typing import Dict, Optional


def map_symbol(broker: str, symbol: str, mapping: Dict[str, Dict[str, str]] | None = None) -> Optional[str]:
    """Map broker symbol to Yahoo symbol if available."""
    if not mapping:
        return symbol
    broker_map = mapping.get(broker, {})
    return broker_map.get(symbol, symbol)
