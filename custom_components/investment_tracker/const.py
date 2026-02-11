"""Constants for Investment Tracker."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "investment_tracker"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

CONF_BROKER_NAME = "broker_name"
CONF_BROKER_TYPE = "broker_type"
CONF_SYMBOLS = "symbols"
CONF_CSV_PATH = "csv_path"
CONF_CSV_MODE = "csv_mode"
CONF_SYMBOL_MAPPING = "symbol_mapping"
CONF_ASSET_METADATA = "asset_metadata"
CONF_TRANSACTIONS = "transactions"
CONF_MANUAL_SYMBOL = "manual_symbol"
CONF_MANUAL_QUANTITY = "manual_quantity"
CONF_MANUAL_AVG_BUY = "manual_avg_buy_price"
CONF_MANUAL_CURRENCY = "manual_currency"
CONF_MANUAL_BROKER = "manual_broker"
CONF_MANUAL_TYPE = "manual_type"
CONF_BASE_CURRENCY = "base_currency"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_MENU_ACTION = "menu_action"
CONF_MARKET_DATA_PROVIDER = "market_data_provider"
CONF_ALPHA_VANTAGE_API_KEY = "alpha_vantage_api_key"
CONF_PLAN_TOTAL = "plan_total"
CONF_PLAN_FREQUENCY = "plan_frequency"
CONF_PLAN_PER_ASSET = "plan_per_asset"

DEFAULT_BASE_CURRENCY = "EUR"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=15)
