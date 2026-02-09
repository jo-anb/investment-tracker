"""Config flow for Investment Tracker."""
from __future__ import annotations

from typing import Any
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import selector

from .const import (
    CONF_BASE_CURRENCY,
    CONF_BROKER_NAME,
    CONF_BROKER_TYPE,
    CONF_CSV_MODE,
    CONF_CSV_PATH,
    CONF_MANUAL_SYMBOL,
    CONF_MANUAL_QUANTITY,
    CONF_MANUAL_AVG_BUY,
    CONF_MANUAL_CURRENCY,
    CONF_MANUAL_BROKER,
    CONF_MANUAL_TYPE,
    CONF_SYMBOLS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_CURRENCY,
    DOMAIN,
    CONF_MENU_ACTION,
    CONF_MARKET_DATA_PROVIDER,
    CONF_ALPHA_VANTAGE_API_KEY,
    CONF_PLAN_TOTAL,
    CONF_PLAN_FREQUENCY,
    CONF_PLAN_PER_ASSET,
)

_LOGGER = logging.getLogger(__name__)

BROKER_TYPES = ["api", "csv", "manual"]
CSV_MODES = ["upload", "directory"]
MARKET_PROVIDERS = ["stooq", "alpha_vantage", "yahoo_public"]
PLAN_FREQUENCIES = ["weekly", "monthly", "quarterly", "yearly"]


class InvestmentTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Investment Tracker."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        self._manual_positions: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _LOGGER.debug("Config step user input: %s", user_input)
            self._user_input = user_input
            broker_type = user_input.get(CONF_BROKER_TYPE)
            if broker_type == "csv":
                try:
                    return await self.async_step_csv()
                except Exception as err:  # pragma: no cover
                    _LOGGER.exception("Failed to open CSV step: %s", err)
                    errors["base"] = "unknown"
            if broker_type == "manual":
                try:
                    return await self.async_step_manual_setup()
                except Exception as err:  # pragma: no cover
                    _LOGGER.exception("Failed to open manual step: %s", err)
                    errors["base"] = "unknown"
            errors["base"] = "api_not_supported"

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Investment Tracker"): str,
                vol.Required(CONF_BROKER_NAME): str,
                vol.Required(CONF_BROKER_TYPE, default="csv"): vol.In(BROKER_TYPES),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_csv(self, user_input: dict[str, Any] | None = None):
        """CSV import setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _LOGGER.debug("Config step csv input: %s", user_input)
            csv_mode = user_input.get(CONF_CSV_MODE)
            csv_path = user_input.get(CONF_CSV_PATH)
            if isinstance(csv_path, dict):
                csv_path = csv_path.get("path")
            if csv_path:
                user_input[CONF_CSV_PATH] = csv_path
            if csv_mode == "upload" and not csv_path:
                errors["base"] = "csv_path_required"
            else:
                self._user_input.update(user_input)
                return await self.async_step_preferences()

        schema = vol.Schema(
            {
                vol.Required(CONF_CSV_MODE, default="directory"): vol.In(CSV_MODES),
                vol.Optional(CONF_CSV_PATH): selector({"file": {"accept": ".csv"}}),
            }
        )
        return self.async_show_form(step_id="csv", data_schema=schema, errors=errors)

    async def async_step_manual_setup(self, user_input: dict[str, Any] | None = None):
        """Manual setup step."""
        if user_input is not None:
            _LOGGER.debug("Config step manual_setup input: %s", user_input)
            manual_symbol = user_input.get(CONF_MANUAL_SYMBOL, "").strip().upper()
            if manual_symbol:
                self._manual_positions.append(
                    {
                        "symbol": manual_symbol,
                        "name": user_input.get("name", manual_symbol),
                        "type": user_input.get(CONF_MANUAL_TYPE, "equity"),
                        "quantity": float(user_input.get(CONF_MANUAL_QUANTITY, 0) or 0),
                        "avg_buy_price": float(user_input.get(CONF_MANUAL_AVG_BUY, 0) or 0),
                        "currency": user_input.get(CONF_MANUAL_CURRENCY, DEFAULT_BASE_CURRENCY),
                        "broker": user_input.get(CONF_MANUAL_BROKER, "manual"),
                    }
                )
            return await self.async_step_preferences()

        schema = vol.Schema(
            {
                vol.Required(CONF_MANUAL_SYMBOL): str,
                vol.Optional(CONF_MANUAL_QUANTITY, default=0): vol.Coerce(float),
                vol.Optional(CONF_MANUAL_AVG_BUY, default=0): vol.Coerce(float),
                vol.Optional(CONF_MANUAL_CURRENCY, default=DEFAULT_BASE_CURRENCY): str,
                vol.Optional(CONF_MANUAL_BROKER, default="manual"): str,
                vol.Optional(CONF_MANUAL_TYPE, default="equity"): str,
            }
        )
        return self.async_show_form(step_id="manual_setup", data_schema=schema)

    async def async_step_preferences(self, user_input: dict[str, Any] | None = None):
        """Preferences step."""
        if user_input is not None:
            _LOGGER.debug("Config step preferences input: %s", user_input)
            symbols_raw = self._user_input.get(CONF_SYMBOLS, "")
            symbols_list = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]
            data = {**self._user_input, **user_input, CONF_SYMBOLS: symbols_list}
            if self._manual_positions:
                data["positions"] = self._manual_positions
            data.setdefault(CONF_MARKET_DATA_PROVIDER, "yahoo_public")
            return self.async_create_entry(title=data[CONF_NAME], data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_CURRENCY, default=DEFAULT_BASE_CURRENCY): str,
                vol.Required(CONF_UPDATE_INTERVAL, default=900): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="preferences", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return InvestmentTrackerOptionsFlow(config_entry)


class InvestmentTrackerOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Investment Tracker."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Show options menu."""
        if user_input is not None:
            action = user_input.get(CONF_MENU_ACTION)
            if action == "settings":
                return await self.async_step_settings()
            if action == "manual_add":
                return await self.async_step_manual_add()
            if action == "manual_transaction":
                return await self.async_step_manual_transaction()
            if action == "investment_plan":
                return await self.async_step_investment_plan()

        menu_labels_en = {
            "settings": "Settings",
            "manual_add": "Manual add",
            "manual_transaction": "Add transaction",
            "investment_plan": "Investment plan",
        }
        menu_labels_nl = {
            "settings": "Instellingen",
            "manual_add": "Handmatig toevoegen",
            "manual_transaction": "Transactie toevoegen",
            "investment_plan": "Investeringsplan",
        }
        language = (self.hass.config.language or "en") if self.hass else "en"
        menu_labels = menu_labels_nl if language.lower().startswith("nl") else menu_labels_en

        schema = vol.Schema(
            {
                vol.Required(CONF_MENU_ACTION): vol.In(menu_labels),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        """Handle settings options."""
        if user_input is not None:
            symbols_raw = user_input.get(CONF_SYMBOLS, "")
            symbols_list = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]
            user_input[CONF_SYMBOLS] = symbols_list
            if user_input.get(CONF_UPDATE_INTERVAL) is not None:
                user_input[CONF_UPDATE_INTERVAL] = max(900, int(user_input[CONF_UPDATE_INTERVAL]))
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options or {}
        defaults = {
            CONF_BASE_CURRENCY: current.get(CONF_BASE_CURRENCY, self._config_entry.data.get(CONF_BASE_CURRENCY, DEFAULT_BASE_CURRENCY)),
            CONF_UPDATE_INTERVAL: current.get(CONF_UPDATE_INTERVAL, self._config_entry.data.get(CONF_UPDATE_INTERVAL, 900)),
            CONF_SYMBOLS: ", ".join(current.get(CONF_SYMBOLS, self._config_entry.data.get(CONF_SYMBOLS, []))),
            CONF_CSV_PATH: current.get(CONF_CSV_PATH, self._config_entry.data.get(CONF_CSV_PATH, "")),
            CONF_CSV_MODE: current.get(CONF_CSV_MODE, self._config_entry.data.get(CONF_CSV_MODE, "directory")),
            CONF_MARKET_DATA_PROVIDER: current.get(
                CONF_MARKET_DATA_PROVIDER, self._config_entry.data.get(CONF_MARKET_DATA_PROVIDER, "yahoo_public")
            ),
            CONF_ALPHA_VANTAGE_API_KEY: current.get(
                CONF_ALPHA_VANTAGE_API_KEY, self._config_entry.data.get(CONF_ALPHA_VANTAGE_API_KEY, "")
            ),
            CONF_PLAN_TOTAL: current.get(CONF_PLAN_TOTAL, self._config_entry.data.get(CONF_PLAN_TOTAL, 0)),
            CONF_PLAN_FREQUENCY: current.get(
                CONF_PLAN_FREQUENCY, self._config_entry.data.get(CONF_PLAN_FREQUENCY, "monthly")
            ),
            CONF_PLAN_PER_ASSET: ", ".join(current.get(CONF_PLAN_PER_ASSET, self._config_entry.data.get(CONF_PLAN_PER_ASSET, []))),
        }

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_CURRENCY, default=defaults[CONF_BASE_CURRENCY]): str,
                vol.Required(CONF_UPDATE_INTERVAL, default=defaults[CONF_UPDATE_INTERVAL]): vol.Coerce(int),
                vol.Optional(CONF_SYMBOLS, default=defaults[CONF_SYMBOLS]): str,
                vol.Optional(CONF_CSV_PATH, default=defaults[CONF_CSV_PATH]): str,
                vol.Optional(CONF_CSV_MODE, default=defaults[CONF_CSV_MODE]): vol.In(CSV_MODES),
                vol.Optional(CONF_MARKET_DATA_PROVIDER, default=defaults[CONF_MARKET_DATA_PROVIDER]): vol.In(MARKET_PROVIDERS),
                vol.Optional(CONF_ALPHA_VANTAGE_API_KEY, default=defaults[CONF_ALPHA_VANTAGE_API_KEY]): str,
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)

    async def async_step_manual_add(self, user_input: dict[str, Any] | None = None):
        """Manual add flow."""
        if user_input is not None:
            manual_symbol = user_input.get(CONF_MANUAL_SYMBOL, "").strip().upper()
            if manual_symbol:
                positions = self._config_entry.data.get("positions", [])
                positions.append(
                    {
                        "symbol": manual_symbol,
                        "name": user_input.get("name", manual_symbol),
                        "type": user_input.get(CONF_MANUAL_TYPE, "equity"),
                        "quantity": float(user_input.get(CONF_MANUAL_QUANTITY, 0) or 0),
                        "avg_buy_price": float(user_input.get(CONF_MANUAL_AVG_BUY, 0) or 0),
                        "currency": user_input.get(CONF_MANUAL_CURRENCY, "USD"),
                        "broker": user_input.get(CONF_MANUAL_BROKER, "manual"),
                    }
                )
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data={**self._config_entry.data, "positions": positions}
                )
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(CONF_MANUAL_SYMBOL): str,
                vol.Optional(CONF_MANUAL_QUANTITY, default=0): vol.Coerce(float),
                vol.Optional(CONF_MANUAL_AVG_BUY, default=0): vol.Coerce(float),
                vol.Optional(CONF_MANUAL_CURRENCY, default=self._config_entry.data.get(CONF_BASE_CURRENCY, DEFAULT_BASE_CURRENCY)): str,
                vol.Optional(CONF_MANUAL_BROKER, default=self._config_entry.data.get(CONF_BROKER_NAME, "manual")): str,
                vol.Optional(CONF_MANUAL_TYPE, default="equity"): str,
            }
        )
        return self.async_show_form(step_id="manual_add", data_schema=schema)

    async def async_step_manual_transaction(self, user_input: dict[str, Any] | None = None):
        """Manual transaction add flow."""
        if user_input is not None:
            symbol = user_input.get(CONF_MANUAL_SYMBOL, "").strip().upper()
            if symbol:
                positions = self._config_entry.data.get("positions", [])
                matched_position = next(
                    (pos for pos in positions if (pos.get("symbol") or "").strip().upper() == symbol),
                    None,
                )
                default_broker = (
                    matched_position.get("broker") if matched_position else self._config_entry.data.get(CONF_BROKER_NAME, "manual")
                )
                broker_input = (user_input.get(CONF_MANUAL_BROKER) or "").strip()
                broker_value = broker_input or default_broker or "manual"
                transactions = self._config_entry.data.get("transactions", [])
                transactions.append(
                    {
                        "symbol": symbol,
                        "name": symbol,
                        "quantity": float(user_input.get(CONF_MANUAL_QUANTITY, 0) or 0),
                        "price": float(user_input.get(CONF_MANUAL_AVG_BUY, 0) or 0),
                        "currency": user_input.get(CONF_MANUAL_CURRENCY, "USD"),
                        "broker": broker_value,
                        "date": user_input.get("date"),
                    }
                )
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data={**self._config_entry.data, "transactions": transactions}
                )
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(CONF_MANUAL_SYMBOL): str,
                vol.Required(CONF_MANUAL_QUANTITY): vol.Coerce(float),
                vol.Required(CONF_MANUAL_AVG_BUY): vol.Coerce(float),
                vol.Optional(CONF_MANUAL_CURRENCY, default=self._config_entry.data.get(CONF_BASE_CURRENCY, DEFAULT_BASE_CURRENCY)): str,
                vol.Optional(CONF_MANUAL_BROKER, default=self._config_entry.data.get(CONF_BROKER_NAME, "manual")): str,
                vol.Optional("date"): selector({"date": {}}),
            }
        )
        return self.async_show_form(step_id="manual_transaction", data_schema=schema)

    async def async_step_investment_plan(self, user_input: dict[str, Any] | None = None):
        """Investment plan options."""
        if user_input is not None:
            per_asset_raw = user_input.get(CONF_PLAN_PER_ASSET, "")
            per_asset_list = [s.strip() for s in per_asset_raw.split(",") if s.strip()]
            user_input[CONF_PLAN_PER_ASSET] = per_asset_list
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options or {}
        defaults = {
            CONF_PLAN_TOTAL: current.get(CONF_PLAN_TOTAL, self._config_entry.data.get(CONF_PLAN_TOTAL, 0)),
            CONF_PLAN_FREQUENCY: current.get(
                CONF_PLAN_FREQUENCY, self._config_entry.data.get(CONF_PLAN_FREQUENCY, "monthly")
            ),
            CONF_PLAN_PER_ASSET: ", ".join(current.get(CONF_PLAN_PER_ASSET, self._config_entry.data.get(CONF_PLAN_PER_ASSET, []))),
        }

        schema = vol.Schema(
            {
                vol.Optional(CONF_PLAN_TOTAL, default=defaults[CONF_PLAN_TOTAL]): vol.Coerce(float),
                vol.Optional(CONF_PLAN_FREQUENCY, default=defaults[CONF_PLAN_FREQUENCY]): vol.In(PLAN_FREQUENCIES),
                vol.Optional(CONF_PLAN_PER_ASSET, default=defaults[CONF_PLAN_PER_ASSET]): str,
            }
        )
        return self.async_show_form(step_id="investment_plan", data_schema=schema)
