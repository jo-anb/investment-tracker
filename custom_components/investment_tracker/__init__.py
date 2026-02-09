"""Investment Tracker integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_BROKER_NAME, CONF_SYMBOL_MAPPING, DEFAULT_UPDATE_INTERVAL, DOMAIN, PLATFORMS
from .coordinator import InvestmentTrackerCoordinator

_LOGGER = logging.getLogger(__name__)


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
            _LOGGER.warning("remap_symbol: no coordinator found for broker=%s entry_id=%s", broker, entry_id)
            return
        entry = coordinator.entry
        updated = False
        _LOGGER.debug(
            "remap_symbol called symbol=%s broker=%s ticker=%s category=%s",
            symbol,
            broker,
            ticker,
            category,
        )
        # Update symbol mapping if ticker is provided and symbol is not empty
        if symbol and ticker:
            mapping = entry.data.get(CONF_SYMBOL_MAPPING, {})
            mapping[symbol] = ticker
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_SYMBOL_MAPPING: mapping},
            )
            updated = True
            _LOGGER.debug("remap_symbol stored ticker mapping %s -> %s", symbol, ticker)
        # Update category if provided, match both symbol and broker
        if category:
            positions = entry.data.get("positions", [])
            if not positions:
                fallback_positions = []
                for asset in coordinator.data.get("assets", []):
                    fallback_positions.append(
                        {
                            "symbol": asset.get("symbol"),
                            "name": asset.get("name") or asset.get("symbol"),
                            "type": asset.get("type", "equity"),
                            "quantity": asset.get("quantity", 0),
                            "avg_buy_price": asset.get("avg_buy_price", 0),
                            "currency": asset.get("currency"),
                            "broker": asset.get("broker", "unknown"),
                            "manual_type": bool(asset.get("manual_type")),
                        }
                    )
                if fallback_positions:
                    positions = fallback_positions
                    hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, "positions": positions, "transactions": []},
                    )
                    _LOGGER.debug("remap_symbol populated positions from assets for manual overrides")
            new_positions = []
            normalized_symbol = symbol.strip().upper() if symbol else None
            normalized_broker = broker.strip().lower() if broker else None
            _LOGGER.debug(
                "remap_symbol scanning %s positions for symbol=%s broker=%s",
                len(positions),
                normalized_symbol,
                normalized_broker,
            )
            for pos in positions:
                pos_symbol = (pos.get("symbol") or "").strip().upper()
                pos_broker = (pos.get("broker") or "").strip().lower()
                symbol_match = normalized_symbol == pos_symbol if normalized_symbol else True
                broker_match = normalized_broker == pos_broker if normalized_broker else True
                if symbol_match and broker_match:
                    _LOGGER.debug(
                        "remap_symbol match found pos symbol=%s broker=%s",
                        pos_symbol,
                        pos_broker,
                    )
                if symbol_match and broker_match:
                    new_pos = {**pos, "type": category, "manual_type": True}
                    new_positions.append(new_pos)
                    updated = True
                else:
                    new_positions.append(pos)
            if updated:
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, "positions": new_positions},
                )
                coordinator._positions = new_positions
                _LOGGER.debug(
                    "remap_symbol updated positions for %s/%s category=%s",
                    symbol,
                    broker,
                    category,
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
