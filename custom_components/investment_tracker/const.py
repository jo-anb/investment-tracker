"""Constants for Investment Tracker."""
from __future__ import annotations

from datetime import timedelta
from homeassistant.const import Platform

DOMAIN = "investment_tracker"

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_BROKER_NAME = "broker_name"
CONF_BROKER_TYPE = "broker_type"
CONF_BASE_CURRENCY = "base_currency"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_BASE_CURRENCY = "EUR"
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=60)
