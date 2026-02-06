"""Coordinator for Investment Tracker."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN


class InvestmentTrackerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and normalize investment data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        update_seconds = entry.data.get(CONF_UPDATE_INTERVAL, 60)
        update_interval = timedelta(seconds=update_seconds) if update_seconds else DEFAULT_UPDATE_INTERVAL
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sources."""
        try:
            return {
                "portfolio": {},
                "assets": [],
                "totals": {
                    "total_value": 0,
                    "total_invested": 0,
                    "total_profit_loss": 0,
                    "total_profit_loss_pct": 0,
                },
            }
        except Exception as err:  # pragma: no cover
            raise UpdateFailed(str(err)) from err
