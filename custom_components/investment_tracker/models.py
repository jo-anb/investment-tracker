"""Datamodels for Investment Tracker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass
class Transaction:
    """Record of a broker transaction line."""

    date: str
    quantity: float
    price: float
    currency: str


@dataclass
class Asset:
    """Proxy for a tracked asset on the service sensor."""

    symbol: str
    name: str
    type: str
    quantity: float
    avg_buy_price: float
    current_price: float | None
    currency: str
    market_value: float | None
    profit_loss_abs: float | None
    profit_loss_pct: float | None
    broker: str
    unmapped: bool = False
    last_price_update: datetime | None = None
    transactions: list[Transaction] = field(default_factory=list)


@dataclass
class Broker:
    """Metadata describing a broker contribution."""

    broker_name: str
    broker_type: str
    connected: bool = False
    last_sync: datetime | None = None
    accounts: list[str] = field(default_factory=list)


@dataclass
class MarketData:
    """Pricing snapshot fetched from a market data provider."""

    symbol: str
    price: float
    currency: str
    timestamp: datetime
    source: str = "yfinance"


@dataclass
class Portfolio:
    """User portfolio grouping for the service sensor."""

    base_currency: str
    assets: list[Asset] = field(default_factory=list)
