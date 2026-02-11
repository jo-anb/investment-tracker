"""Sensors for Investment Tracker."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_ALPHA_VANTAGE_API_KEY,
    CONF_MARKET_DATA_PROVIDER,
    CONF_PLAN_FREQUENCY,
    CONF_PLAN_PER_ASSET,
    CONF_PLAN_TOTAL,
    DOMAIN,
)
from .coordinator import InvestmentTrackerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: InvestmentTrackerCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        InvestmentServiceSensor(coordinator),
        InvestmentTotalValueSensor(coordinator),
        InvestmentTotalInvestedSensor(coordinator),
        InvestmentTotalProfitLossSensor(coordinator),
        InvestmentTotalProfitLossRealizedSensor(coordinator),
        InvestmentTotalProfitLossPctSensor(coordinator),
        InvestmentTotalActiveInvestedSensor(coordinator),
        InvestmentTotalProfitLossUnrealizedSensor(coordinator),
    ]
    tracked: dict[str, SensorEntity] = {}

    def _asset_key(asset: dict[str, Any], suffix: str) -> str:
        return f"{asset.get('broker','unknown')}:{asset.get('symbol','unknown')}:{suffix}".lower()

    def _sync_assets() -> None:
        assets = coordinator.data.get("assets", [])
        current_keys: set[str] = set()
        for asset in assets:
            current_keys.add(_asset_key(asset, "value"))
            current_keys.add(_asset_key(asset, "pl_pct"))

        # Add new entities
        new_entities: list[SensorEntity] = []
        for asset in assets:
            value_key = _asset_key(asset, "value")
            if value_key not in tracked:
                sensor = InvestmentAssetValueSensor(coordinator, asset)
                tracked[value_key] = sensor
                new_entities.append(sensor)

            pl_pct_key = _asset_key(asset, "pl_pct")
            if pl_pct_key not in tracked:
                sensor = InvestmentAssetProfitLossPctSensor(coordinator, asset)
                tracked[pl_pct_key] = sensor
                new_entities.append(sensor)

        if new_entities:
            async_add_entities(new_entities)

        # Remove entities that no longer exist
        remove_keys = [key for key in tracked if key not in current_keys]
        for key in remove_keys:
            sensor = tracked.pop(key)
            hass.async_create_task(sensor.async_remove())

    _sync_assets()
    async_add_entities(entities)

    coordinator.async_add_listener(_sync_assets)


class InvestmentBaseSensor(CoordinatorEntity[InvestmentTrackerCoordinator], SensorEntity):
    """Base sensor."""

    def __init__(self, coordinator: InvestmentTrackerCoordinator) -> None:
        super().__init__(coordinator)
        self._entry_id = coordinator.entry.entry_id

    def _broker_slug(self) -> str:
        broker = self.coordinator.entry.data.get("broker_name", "broker")
        return slugify(broker)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class InvestmentTotalValueSensor(InvestmentBaseSensor):
    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("totals", {}).get("total_value", 0)

    @property
    def name(self) -> str | None:
        return f"{self._broker_slug()} Total Value"

    @property
    def unique_id(self) -> str | None:
        return f"{self._entry_id}_investment_total_value"

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.coordinator.data.get("portfolio", {}).get("base_currency")


class InvestmentTotalInvestedSensor(InvestmentBaseSensor):
    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("totals", {}).get("total_invested", 0)

    @property
    def name(self) -> str | None:
        return f"{self._broker_slug()} Total Invested"

    @property
    def unique_id(self) -> str | None:
        return f"{self._entry_id}_investment_total_invested"

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.coordinator.data.get("portfolio", {}).get("base_currency")


class InvestmentTotalActiveInvestedSensor(InvestmentBaseSensor):
    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("totals", {}).get("total_active_invested", 0)

    @property
    def name(self) -> str | None:
        return f"{self._broker_slug()} Total Active Invested"

    @property
    def unique_id(self) -> str | None:
        return f"{self._entry_id}_investment_total_active_invested"

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.coordinator.data.get("portfolio", {}).get("base_currency")


class InvestmentTotalProfitLossSensor(InvestmentBaseSensor):
    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("totals", {}).get("total_profit_loss", 0)

    @property
    def name(self) -> str | None:
        return f"{self._broker_slug()} Total Profit/Loss"

    @property
    def unique_id(self) -> str | None:
        return f"{self._entry_id}_investment_total_profit_loss"

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.coordinator.data.get("portfolio", {}).get("base_currency")


class InvestmentTotalProfitLossPctSensor(InvestmentBaseSensor):
    _attr_name = None
    _attr_unique_id = None
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("totals", {}).get("total_profit_loss_pct", 0)

    @property
    def name(self) -> str | None:
        return f"{self._broker_slug()} Total Profit/Loss %"

    @property
    def unique_id(self) -> str | None:
        return f"{self._entry_id}_investment_total_profit_loss_pct"


class InvestmentTotalProfitLossRealizedSensor(InvestmentBaseSensor):
    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("totals", {}).get("total_profit_loss_realized", 0)

    @property
    def name(self) -> str | None:
        return f"{self._broker_slug()} Total Realized Profit/Loss"

    @property
    def unique_id(self) -> str | None:
        return f"{self._entry_id}_investment_total_profit_loss_realized"

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.coordinator.data.get("portfolio", {}).get("base_currency")

class InvestmentTotalProfitLossUnrealizedSensor(InvestmentBaseSensor):
    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("totals", {}).get("total_profit_loss_unrealized", 0)

    @property
    def name(self) -> str | None:
        return f"{self._broker_slug()} Total Unrealized Profit/Loss"

    @property
    def unique_id(self) -> str | None:
        return f"{self._entry_id}_investment_total_profit_loss_unrealized"

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.coordinator.data.get("portfolio", {}).get("base_currency")

class InvestmentAssetBaseSensor(InvestmentBaseSensor):
    """Base sensor for a single asset."""

    def __init__(self, coordinator: InvestmentTrackerCoordinator, asset: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._symbol = asset.get("symbol", "unknown")
        self._broker = asset.get("broker", "unknown")

    def _get_asset(self) -> dict[str, Any] | None:
        assets = self.coordinator.data.get("assets", [])
        for asset in assets:
            if asset.get("symbol") == self._symbol and asset.get("broker") == self._broker:
                return asset
        return None

    def _base_attributes(self) -> dict[str, Any] | None:
        asset = self._get_asset()
        if not asset:
            return None
        attrs = {
            "friendly_name": asset.get("display_name") or asset.get("symbol"),
            "exchange_name": asset.get("exchange_name"),
            "country": asset.get("country"),
            "sector": asset.get("sector"),
            "industry": asset.get("industry"),
            "symbol": asset.get("symbol"),
            "quantity": asset.get("quantity"),
            "avg_buy_price": asset.get("avg_buy_price"),
            "current_price": asset.get("current_price"),
            "currency": asset.get("currency"),
            "market_value": asset.get("market_value"),
            "profit_loss_abs": asset.get("profit_loss_abs"),
            "profit_loss_pct": asset.get("profit_loss_pct"),
            "profit_loss_pct_unit": PERCENTAGE,
            "broker": asset.get("broker"),
            "category": asset.get("type"),
            "unmapped": asset.get("unmapped"),
            "last_price_update": asset.get("last_price_update"),
            "transactions": asset.get("transactions", []),
            "repair_suggestions": asset.get("repair_suggestions", []),
        }
        logo_url = asset.get("logoUrl")
        if logo_url:
            attrs["entity_picture"] = logo_url
        return attrs


class InvestmentAssetValueSensor(InvestmentAssetBaseSensor):
    """Market value sensor for a single asset."""

    @property
    def unique_id(self) -> str | None:
        return f"{self._entry_id}_investment_{self._broker}_{self._symbol}".lower()

    @property
    def name(self) -> str | None:
        broker = slugify(self._broker)
        asset = self._get_asset() or {}
        display = asset.get("display_name") or asset.get("symbol") or self._symbol
        return f"{broker} {display} Value"

    @property
    def native_value(self) -> Any:
        asset = self._get_asset()
        return asset.get("market_value") if asset else None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        return SensorDeviceClass.MONETARY

    @property
    def state_class(self) -> SensorStateClass | None:
        return SensorStateClass.TOTAL

    @property
    def native_unit_of_measurement(self) -> str | None:
        asset = self._get_asset()
        return asset.get("currency") if asset else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self._base_attributes()


class InvestmentAssetProfitLossPctSensor(InvestmentAssetBaseSensor):
    """Profit/loss percentage sensor for a single asset."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def unique_id(self) -> str | None:
        return f"{self._entry_id}_investment_{self._broker}_{self._symbol}_pl_pct".lower()

    @property
    def name(self) -> str | None:
        broker = slugify(self._broker)
        asset = self._get_asset() or {}
        display = asset.get("display_name") or asset.get("symbol") or self._symbol
        return f"{broker} {display} P/L %"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self._base_attributes()


class InvestmentServiceSensor(InvestmentBaseSensor):
    """General service sensor for the integration entry."""

    _attr_name = None
    _attr_unique_id = None
    _attr_suggested_object_id = None

    @property
    def name(self) -> str | None:
        entry_name = self.coordinator.entry.data.get("name")
        return entry_name or "Investment Tracker"

    @property
    def suggested_object_id(self) -> str | None:
        entry_name = self.coordinator.entry.data.get("name") or "investment_tracker"
        return f"investment_tracker_{slugify(entry_name)}"

    @property
    def unique_id(self) -> str | None:
        return f"{self._entry_id}_service"

    @property
    def native_value(self) -> Any:
        return "active"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        entry = self.coordinator.entry
        options = entry.options or {}
        return {
            "broker_name": entry.data.get("broker_name"),
            "broker_type": entry.data.get("broker_type"),
            "market_data_provider": options.get(
                CONF_MARKET_DATA_PROVIDER, entry.data.get(CONF_MARKET_DATA_PROVIDER)
            ),
            "update_interval": options.get("update_interval", entry.data.get("update_interval")),
            "plan_total": options.get(CONF_PLAN_TOTAL, entry.data.get(CONF_PLAN_TOTAL)),
            "plan_frequency": options.get(CONF_PLAN_FREQUENCY, entry.data.get(CONF_PLAN_FREQUENCY)),
            "plan_per_asset": options.get(CONF_PLAN_PER_ASSET, entry.data.get(CONF_PLAN_PER_ASSET, [])),
            "alpha_vantage_api_key_set": bool(
                options.get(CONF_ALPHA_VANTAGE_API_KEY, entry.data.get(CONF_ALPHA_VANTAGE_API_KEY))
            ),
        }
