"""Button entities for Investment Tracker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import InvestmentTrackerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the refresh button for the entry."""
    coordinator: InvestmentTrackerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([InvestmentRefreshButton(coordinator)])


class InvestmentRefreshButton(ButtonEntity):
    """Button to refresh investment data."""

    _attr_name = "Investment Tracker Refresh"

    def __init__(self, coordinator: InvestmentTrackerCoordinator) -> None:
        """Initialize the refresh button entity."""
        self._coordinator = coordinator
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_investment_tracker_refresh"
        )

    async def async_press(self) -> None:
        """Refresh investment data when pressed."""
        await self._coordinator.async_request_refresh()
