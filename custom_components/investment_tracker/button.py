"""Button entities for Investment Tracker."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import InvestmentTrackerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: InvestmentTrackerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([InvestmentRefreshButton(coordinator)])


class InvestmentRefreshButton(ButtonEntity):
    """Button to refresh investment data."""

    _attr_name = "Investment Tracker Refresh"

    def __init__(self, coordinator: InvestmentTrackerCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.entry.entry_id}_investment_tracker_refresh"

    async def async_press(self) -> None:
        await self._coordinator.async_request_refresh()
