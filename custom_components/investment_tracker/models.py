"""Datamodels for Investment Tracker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Transaction:
    date: str
    quantity: float
    price: float
    currency: str


@dataclass
class Asset:
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
    broker_name: str
    broker_type: str
    connected: bool = False
    last_sync: datetime | None = None
    accounts: list[str] = field(default_factory=list)


@dataclass
class MarketData:
    symbol: str
    price: float
    currency: str
    timestamp: datetime
    source: str = "yfinance"


@dataclass
class Portfolio:
    base_currency: str
    assets: list[Asset] = field(default_factory=list)
