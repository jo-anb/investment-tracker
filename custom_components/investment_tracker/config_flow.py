"""Config flow for Investment Tracker."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME

from .const import (
    CONF_BASE_CURRENCY,
    CONF_BROKER_NAME,
    CONF_BROKER_TYPE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_CURRENCY,
    DOMAIN,
)

BROKER_TYPES = ["api", "csv", "manual"]


class InvestmentTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Investment Tracker."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        if user_input is not None:
            self._user_input = user_input
            return await self.async_step_preferences()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Investment Tracker"): str,
                vol.Required(CONF_BROKER_NAME): str,
                vol.Required(CONF_BROKER_TYPE, default="csv"): vol.In(BROKER_TYPES),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_preferences(self, user_input: dict[str, Any] | None = None):
        """Preferences step."""
        if user_input is not None:
            data = {**self._user_input, **user_input}
            return self.async_create_entry(title=data[CONF_NAME], data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_CURRENCY, default=DEFAULT_BASE_CURRENCY): str,
                vol.Required(CONF_UPDATE_INTERVAL, default=60): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="preferences", data_schema=schema)
