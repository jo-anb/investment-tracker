"""Investment Tracker integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_BROKER_NAME, DEFAULT_UPDATE_INTERVAL, DOMAIN, PLATFORMS
from .coordinator import InvestmentTrackerCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Investment Tracker from a config entry."""
    coordinator: DataUpdateCoordinator = InvestmentTrackerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _handle_refresh(call) -> None:
        coordinator: InvestmentTrackerCoordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_request_refresh()

    async def _handle_refresh_asset(call) -> None:
        entry_id = call.data.get("entry_id")
        broker = call.data.get("broker")
        symbol = call.data.get("symbol")

        coordinator: InvestmentTrackerCoordinator | None = None
        if entry_id and entry_id in hass.data.get(DOMAIN, {}):
            coordinator = hass.data[DOMAIN][entry_id]
        elif broker:
            broker_lower = str(broker).lower()
            for coord in hass.data.get(DOMAIN, {}).values():
                name = coord.entry.data.get(CONF_BROKER_NAME, "")
                if name and name.lower() == broker_lower:
                    coordinator = coord
                    break
        elif len(hass.data.get(DOMAIN, {})) == 1:
            coordinator = next(iter(hass.data[DOMAIN].values()))

        if coordinator and symbol:
            await coordinator.async_refresh_asset(symbol, broker)

    async def _handle_remap_symbol(call) -> None:
        entry_id = call.data.get("entry_id")
        broker = call.data.get("broker")
        symbol = call.data.get("symbol")
        ticker = call.data.get("ticker")
        category = call.data.get("category")

        coordinator: InvestmentTrackerCoordinator | None = None
        if entry_id and entry_id in hass.data.get(DOMAIN, {}):
            coordinator = hass.data[DOMAIN][entry_id]
        elif broker:
            broker_lower = str(broker).lower()
            for coord in hass.data.get(DOMAIN, {}).values():
                name = coord.entry.data.get(CONF_BROKER_NAME, "")
                if name and name.lower() == broker_lower:
                    coordinator = coord
                    break
        elif len(hass.data.get(DOMAIN, {})) == 1:
            coordinator = next(iter(hass.data[DOMAIN].values()))

        if not coordinator:
            return
        entry = coordinator.entry
        updated = False
        # Update symbol mapping if ticker is provided and symbol is not empty
        if symbol and ticker:
            mapping = entry.data.get(CONF_SYMBOL_MAPPING, {})
            mapping[symbol] = ticker
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_SYMBOL_MAPPING: mapping},
            )
            updated = True
        # Update category if provided, match both symbol and broker
        if category:
            positions = entry.data.get("positions", [])
            new_positions = []
            for pos in positions:
                match_symbol = symbol if symbol else pos.get("symbol")
                match_broker = broker if broker else pos.get("broker")
                if pos.get("symbol") == match_symbol and pos.get("broker") == match_broker:
                    # Zet expliciet type, maar verwijder ook eventueel oude Yahoo-derived type zodat enrichment opnieuw gebeurt
                    new_pos = {**pos, "type": category}
                    new_positions.append(new_pos)
                    updated = True
                else:
                    new_positions.append(pos)
            if updated:
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, "positions": new_positions},
                )
            # Force coordinator refresh altijd, zodat enrichment en UI syncen
            await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, "refresh"):
        hass.services.async_register(DOMAIN, "refresh", _handle_refresh)
    if not hass.services.has_service(DOMAIN, "refresh_asset"):
        hass.services.async_register(DOMAIN, "refresh_asset", _handle_refresh_asset)
    if not hass.services.has_service(DOMAIN, "remap_symbol"):
        hass.services.async_register(DOMAIN, "remap_symbol", _handle_remap_symbol)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: InvestmentTrackerCoordinator = hass.data[DOMAIN][entry.entry_id]
    update_seconds = entry.options.get("update_interval", entry.data.get("update_interval", 60))
    update_seconds = max(900, int(update_seconds)) if update_seconds else None
    coordinator.update_interval = timedelta(seconds=update_seconds) if update_seconds else DEFAULT_UPDATE_INTERVAL
    await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
