"""Datamodels for Investment Tracker."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


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
    current_price: Optional[float]
    currency: str
    market_value: Optional[float]
    profit_loss_abs: Optional[float]
    profit_loss_pct: Optional[float]
    broker: str
    unmapped: bool = False
    last_price_update: Optional[datetime] = None
    transactions: List[Transaction] = field(default_factory=list)


@dataclass
class Broker:
    broker_name: str
    broker_type: str
    connected: bool = False
    last_sync: Optional[datetime] = None
    accounts: List[str] = field(default_factory=list)


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
    assets: List[Asset] = field(default_factory=list)
