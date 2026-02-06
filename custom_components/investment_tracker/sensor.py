"""Sensors for Investment Tracker."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import InvestmentTrackerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: InvestmentTrackerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        InvestmentTotalValueSensor(coordinator),
        InvestmentTotalInvestedSensor(coordinator),
        InvestmentTotalProfitLossSensor(coordinator),
        InvestmentTotalProfitLossPctSensor(coordinator),
    ])


class InvestmentBaseSensor(CoordinatorEntity[InvestmentTrackerCoordinator], SensorEntity):
    """Base sensor."""

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class InvestmentTotalValueSensor(InvestmentBaseSensor):
    _attr_name = "Investment Total Value"
    _attr_unique_id = "investment_total_value"

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("totals", {}).get("total_value", 0)


class InvestmentTotalInvestedSensor(InvestmentBaseSensor):
    _attr_name = "Investment Total Invested"
    _attr_unique_id = "investment_total_invested"

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("totals", {}).get("total_invested", 0)


class InvestmentTotalProfitLossSensor(InvestmentBaseSensor):
    _attr_name = "Investment Total Profit/Loss"
    _attr_unique_id = "investment_total_profit_loss"

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("totals", {}).get("total_profit_loss", 0)


class InvestmentTotalProfitLossPctSensor(InvestmentBaseSensor):
    _attr_name = "Investment Total Profit/Loss %"
    _attr_unique_id = "investment_total_profit_loss_pct"

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get("totals", {}).get("total_profit_loss_pct", 0)
