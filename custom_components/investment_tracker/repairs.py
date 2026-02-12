"""Repairs for Investment Tracker."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow

from .api.yahoo import search_symbols
from .const import CONF_SYMBOL_MAPPING

_UNMAPPED_ISSUE_PARTS = 3

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.data_entry_flow import FlowResult


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Create a repair flow for the issue in Home Assistant."""
    data = data or {}
    entry_id = data.get("entry_id", "")
    symbol = data.get("symbol", "")
    name = data.get("name", "")
    if (not entry_id or not symbol) and issue_id.startswith("unmapped_"):
        parts = issue_id.split("_", 2)
        if len(parts) == _UNMAPPED_ISSUE_PARTS:
            entry_id = entry_id or parts[1]
            symbol = symbol or parts[2]
    return InvestmentTrackerRepairFlow(hass, entry_id, symbol, name)


async def async_get_repair_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Backward compatible repair flow entry point."""
    return await async_create_fix_flow(hass, issue_id, data)


class InvestmentTrackerRepairFlow(RepairsFlow):
    """Repair flow for symbol mapping."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, symbol: str, name: str
    ) -> None:
        """Initialize the repair flow state for a mapping issue."""
        self.hass = hass
        self.entry_id = entry_id
        self.symbol = symbol
        self.name = name or symbol
        self._suggestions: list[str] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show symbol mapping form or persist the mapped symbol."""
        if user_input and user_input.get("mapped_symbol"):
            mapped = user_input.get("mapped_symbol", "").strip().upper()
            entry = self.hass.config_entries.async_get_entry(self.entry_id)
            if entry:
                mapping = entry.data.get(CONF_SYMBOL_MAPPING, {})
                mapping[self.symbol] = mapped
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_SYMBOL_MAPPING: mapping},
                )
            return self.async_create_entry(title="", data={})

        # search_symbols now returns a list of dicts
        results = await self.hass.async_add_executor_job(search_symbols, self.symbol)
        self._suggestions = [r["symbol"] for r in results]
        exact = next(
            (s for s in self._suggestions if s.upper() == self.symbol.upper()), None
        )
        default_value = exact or (
            self._suggestions[0] if self._suggestions else self.symbol
        )

        schema = vol.Schema(
            {
                vol.Required("mapped_symbol", default=default_value): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "symbol": self.symbol,
                "name": self.name,
                "suggestions": ", ".join(self._suggestions)
                if self._suggestions
                else "-",
            },
        )
