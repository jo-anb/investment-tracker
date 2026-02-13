"""Sensors for Investment Tracker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ALPHA_VANTAGE_API_KEY,
    CONF_BROKER_NAME,
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
    """Set up Investment Tracker sensors for the config entry."""
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
        return f"{asset.get('broker', 'unknown')}:{asset.get('symbol', 'unknown')}:{suffix}".lower()

    def _sync_assets() -> None:
        assets = coordinator.data.get("assets", [])
        current_keys: set[str] = set()
        for asset in assets:
            current_keys.add(_asset_key(asset, "value"))
            current_keys.add(_asset_key(asset, "pl_pct"))
            current_keys.add(_asset_key(asset, "price"))

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

            price_key = _asset_key(asset, "price")
            if price_key not in tracked:
                sensor = InvestmentAssetPriceSensor(coordinator, asset)
                tracked[price_key] = sensor
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


class InvestmentBaseSensor(
    CoordinatorEntity[InvestmentTrackerCoordinator], SensorEntity
):
    """Base sensor."""

    def __init__(self, coordinator: InvestmentTrackerCoordinator) -> None:
        """Initialize base sensor with the coordinator reference."""
        super().__init__(coordinator)
        self._entry_id = coordinator.entry.entry_id

    def _broker_slug(self) -> str:
        broker = self.coordinator.entry.data.get("broker_name", "broker")
        return slugify(broker)

    @property
    def available(self) -> bool:
        """Report whether the coordinator successfully refreshed recently."""
        return self.coordinator.last_update_success


class InvestmentTotalValueSensor(InvestmentBaseSensor):
    """Sensor for the broker's total portfolio value."""

    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        """Return the total portfolio value for the entry."""
        return self.coordinator.data.get("totals", {}).get("total_value", 0)

    @property
    def name(self) -> str | None:
        """Return a display name that includes the broker slug."""
        return f"{self._broker_slug()} Total Value"

    @property
    def unique_id(self) -> str | None:
        """Return a stable unique id for the total value sensor."""
        return f"{self._entry_id}_investment_total_value"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the portfolio's base currency."""
        return self.coordinator.data.get("portfolio", {}).get("base_currency")


class InvestmentTotalInvestedSensor(InvestmentBaseSensor):
    """Sensor for the broker's total invested amount."""

    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        """Return the total invested amount for the entry."""
        return self.coordinator.data.get("totals", {}).get("total_invested", 0)

    @property
    def name(self) -> str | None:
        """Return the friendly name for the invested total sensor."""
        return f"{self._broker_slug()} Total Invested"

    @property
    def unique_id(self) -> str | None:
        """Return the stable id for the invested total sensor."""
        return f"{self._entry_id}_investment_total_invested"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the portfolio's currency for invested totals."""
        return self.coordinator.data.get("portfolio", {}).get("base_currency")


class InvestmentTotalActiveInvestedSensor(InvestmentBaseSensor):
    """Sensor for the broker's currently active invested amount."""

    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        """Return the currently active invested amount."""
        return self.coordinator.data.get("totals", {}).get("total_active_invested", 0)

    @property
    def name(self) -> str | None:
        """Return the friendly name for active invested total."""
        return f"{self._broker_slug()} Total Active Invested"

    @property
    def unique_id(self) -> str | None:
        """Return the stable id for the active invested sensor."""
        return f"{self._entry_id}_investment_total_active_invested"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency for active invested totals."""
        return self.coordinator.data.get("portfolio", {}).get("base_currency")


class InvestmentTotalProfitLossSensor(InvestmentBaseSensor):
    """Sensor for the broker's total profit or loss."""

    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        """Return the total profit or loss amount."""
        return self.coordinator.data.get("totals", {}).get("total_profit_loss", 0)

    @property
    def name(self) -> str | None:
        """Return the friendly name for profit/loss totals."""
        return f"{self._broker_slug()} Total Profit/Loss"

    @property
    def unique_id(self) -> str | None:
        """Return the stable id for the profit/loss sensor."""
        return f"{self._entry_id}_investment_total_profit_loss"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency for profit/loss totals."""
        return self.coordinator.data.get("portfolio", {}).get("base_currency")


class InvestmentTotalProfitLossPctSensor(InvestmentBaseSensor):
    """Sensor for the broker's overall profit/loss percentage."""

    _attr_name = None
    _attr_unique_id = None
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        """Return the overall profit/loss percentage."""
        return self.coordinator.data.get("totals", {}).get("total_profit_loss_pct", 0)

    @property
    def name(self) -> str | None:
        """Return the friendly name for the profit/loss percentage sensor."""
        return f"{self._broker_slug()} Total Profit/Loss %"

    @property
    def unique_id(self) -> str | None:
        """Return the stable id for the percentage sensor."""
        return f"{self._entry_id}_investment_total_profit_loss_pct"


class InvestmentTotalProfitLossRealizedSensor(InvestmentBaseSensor):
    """Sensor for the broker's realized profit or loss."""

    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        """Return the realized profit or loss amount."""
        return self.coordinator.data.get("totals", {}).get(
            "total_profit_loss_realized", 0
        )

    @property
    def name(self) -> str | None:
        """Return the friendly name for the realized sensor."""
        return f"{self._broker_slug()} Total Realized Profit/Loss"

    @property
    def unique_id(self) -> str | None:
        """Return the id for the realized profit/loss sensor."""
        return f"{self._entry_id}_investment_total_profit_loss_realized"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency for realized profit/loss."""
        return self.coordinator.data.get("portfolio", {}).get("base_currency")


class InvestmentTotalProfitLossUnrealizedSensor(InvestmentBaseSensor):
    """Sensor for the broker's unrealized profit or loss."""

    _attr_name = None
    _attr_unique_id = None
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> Any:
        """Return the unrealized profit or loss amount."""
        return self.coordinator.data.get("totals", {}).get(
            "total_profit_loss_unrealized", 0
        )

    @property
    def name(self) -> str | None:
        """Return the friendly name for the unrealized sensor."""
        return f"{self._broker_slug()} Total Unrealized Profit/Loss"

    @property
    def unique_id(self) -> str | None:
        """Return the id for the unrealized profit/loss sensor."""
        return f"{self._entry_id}_investment_total_profit_loss_unrealized"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency for unrealized profit/loss."""
        return self.coordinator.data.get("portfolio", {}).get("base_currency")


class InvestmentAssetBaseSensor(InvestmentBaseSensor):
    """Base sensor for a single asset."""

    def __init__(
        self, coordinator: InvestmentTrackerCoordinator, asset: dict[str, Any]
    ) -> None:
        """Record the asset identifiers for later lookups."""
        super().__init__(coordinator)
        self._symbol = asset.get("symbol", "unknown")
        self._broker = asset.get("broker", "unknown")

    def _get_asset(self) -> dict[str, Any] | None:
        assets = self.coordinator.data.get("assets", [])
        for asset in assets:
            if (
                asset.get("symbol") == self._symbol
                and asset.get("broker") == self._broker
            ):
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
    """Sensor reporting the market value for an individual asset."""

    @property
    def unique_id(self) -> str | None:
        """Return a per-asset unique identifier for this value sensor."""
        return f"{self._entry_id}_investment_{self._broker}_{self._symbol}".lower()

    @property
    def name(self) -> str | None:
        """Return a friendly name for the asset value sensor."""
        broker = slugify(self._broker)
        asset = self._get_asset() or {}
        display = asset.get("display_name") or asset.get("symbol") or self._symbol
        return f"{broker} {display} Value"

    @property
    def native_value(self) -> Any:
        """Return the latest market value for the asset."""
        asset = self._get_asset()
        return asset.get("market_value") if asset else None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Declare that this sensor reports monetary values."""
        return SensorDeviceClass.MONETARY

    @property
    def state_class(self) -> SensorStateClass | None:
        """Declare that this sensor tracks a total measurement."""
        return SensorStateClass.TOTAL

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency code used by the asset."""
        asset = self._get_asset()
        return asset.get("currency") if asset else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the asset attributes collected from the coordinator."""
        return self._base_attributes()


class InvestmentAssetProfitLossPctSensor(InvestmentAssetBaseSensor):
    """Sensor reporting the profit/loss percentage for an individual asset."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def unique_id(self) -> str | None:
        """Return the unique identifier for this asset P/L sensor."""
        return (
            f"{self._entry_id}_investment_{self._broker}_{self._symbol}_pl_pct".lower()
        )

    @property
    def name(self) -> str | None:
        """Return a friendly name for the asset profit/loss percentage."""
        broker = slugify(self._broker)
        asset = self._get_asset() or {}
        display = asset.get("display_name") or asset.get("symbol") or self._symbol
        return f"{broker} {display} P/L %"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose extra metadata associated with the asset."""
        return self._base_attributes()


class InvestmentAssetPriceSensor(InvestmentAssetBaseSensor):
    """Sensor reporting the current price for an individual asset."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def unique_id(self) -> str | None:
        """Return the unique identifier for this asset price sensor."""
        return (
            f"{self._entry_id}_investment_{self._broker}_{self._symbol}_price".lower()
        )

    @property
    def name(self) -> str | None:
        """Return a friendly name for the asset price sensor."""
        broker = slugify(self._broker)
        asset = self._get_asset() or {}
        display = asset.get("display_name") or asset.get("symbol") or self._symbol
        return f"{broker} {display} Price"

    @property
    def native_value(self) -> Any:
        """Return the current price for the asset."""
        asset = self._get_asset()
        return asset.get("current_price") if asset else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the currency code used by the asset."""
        asset = self._get_asset()
        return asset.get("currency") if asset else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose extra metadata associated with the asset."""
        return self._base_attributes()


class InvestmentServiceSensor(InvestmentBaseSensor):
    """General service sensor for the integration entry."""

    _attr_name = None
    _attr_unique_id = None
    _attr_suggested_object_id = None

    @property
    def name(self) -> str | None:
        """Return the configured entry name or a default."""
        entry_name = self.coordinator.entry.data.get("name")
        return entry_name or "Investment Tracker"

    @property
    def suggested_object_id(self) -> str | None:
        """Return a slugified object id for the service sensor."""
        entry_name = self.coordinator.entry.data.get("name") or "investment_tracker"
        return f"investment_tracker_{slugify(entry_name)}"

    @property
    def unique_id(self) -> str | None:
        """Return a stable unique id for the service sensor."""
        return f"{self._entry_id}_service"

    @property
    def native_value(self) -> Any:
        """Return the integration service state."""
        return "active"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the service-level attributes such as broker details."""
        entry = self.coordinator.entry
        options = entry.options or {}
        attrs: dict[str, Any] = {
            "broker_name": entry.data.get("broker_name"),
            "broker_type": entry.data.get("broker_type"),
            "market_data_provider": options.get(
                CONF_MARKET_DATA_PROVIDER, entry.data.get(CONF_MARKET_DATA_PROVIDER)
            ),
            "update_interval": options.get(
                "update_interval", entry.data.get("update_interval")
            ),
            "plan_total": options.get(CONF_PLAN_TOTAL, entry.data.get(CONF_PLAN_TOTAL)),
            "plan_frequency": options.get(
                CONF_PLAN_FREQUENCY, entry.data.get(CONF_PLAN_FREQUENCY)
            ),
            "plan_per_asset": options.get(
                CONF_PLAN_PER_ASSET, entry.data.get(CONF_PLAN_PER_ASSET, [])
            ),
            "alpha_vantage_api_key_set": bool(
                options.get(
                    CONF_ALPHA_VANTAGE_API_KEY,
                    entry.data.get(CONF_ALPHA_VANTAGE_API_KEY),
                )
            ),
        }
        attrs["entry_id"] = entry.entry_id
        broker_names = self._collect_broker_names()
        if broker_names:
            attrs["broker_names"] = broker_names
            attrs["broker_slugs"] = [slugify(name) for name in broker_names if name]
        return attrs

    def _collect_broker_names(self) -> list[str]:
        seen: set[str] = set()
        brokers: list[str] = []

        def _append(name: str | None) -> None:
            value = (name or "").strip()
            if not value:
                return
            key = value.lower()
            if key in seen:
                return
            seen.add(key)
            brokers.append(value)

        _append(self.coordinator.entry.data.get(CONF_BROKER_NAME))
        assets = (self.coordinator.data or {}).get("assets", [])
        for asset in assets:
            _append(asset.get("broker"))
        return brokers
