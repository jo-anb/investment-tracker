"""Coordinator for Investment Tracker."""
from __future__ import annotations

from datetime import timedelta
from difflib import SequenceMatcher
import inspect
import logging
from pathlib import Path
from time import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import issue_registry as ir
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BROKER_NAME,
    CONF_BROKER_TYPE,
    CONF_CSV_MODE,
    CONF_CSV_PATH,
    CONF_SYMBOL_MAPPING,
    CONF_ASSET_METADATA,
    CONF_UPDATE_INTERVAL,
    CONF_MARKET_DATA_PROVIDER,
    CONF_ALPHA_VANTAGE_API_KEY,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .api.stooq import get_quotes as get_stooq_quotes
from .api.alphavantage import get_quotes as get_alpha_quotes
from .api.yahoo import get_quote_type, get_quotes as get_yahoo_quotes, search_symbols, get_summary_profile
from .helpers import (
    apply_transactions_to_positions,
    compute_realized_profit_loss,
    compute_total_cash_invested,
    get_default_symbol_mapping,
    map_symbol,
    parse_positions_csv,
    parse_transactions_csv,
)


class InvestmentTrackerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch and normalize investment data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        update_seconds = entry.options.get(CONF_UPDATE_INTERVAL, entry.data.get(CONF_UPDATE_INTERVAL, 900))
        if update_seconds:
            update_seconds = max(900, int(update_seconds))
        update_interval = timedelta(seconds=update_seconds) if update_seconds else DEFAULT_UPDATE_INTERVAL
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.entry = entry
        self._positions: list[dict[str, Any]] = entry.data.get("positions", [])
        stored_metadata = entry.data.get(CONF_ASSET_METADATA) or {}
        self._asset_metadata: dict[str, dict[str, Any]] = {k: dict(v) for k, v in stored_metadata.items()} if isinstance(stored_metadata, dict) else {}
        self._asset_metadata_dirty = False
        self._transactions: list[dict[str, Any]] = self._dedupe_transactions(list(entry.data.get("transactions", [])))

    async def _update_entry_data(self, overrides: dict[str, Any]) -> None:
        data = {**(self.entry.data or {}), **overrides}
        data[CONF_ASSET_METADATA] = {k: dict(v) for k, v in self._asset_metadata.items()}
        if "transactions" not in overrides and self._transactions:
            data["transactions"] = self._transactions
        update_result = self.hass.config_entries.async_update_entry(self.entry, data=data)
        self._asset_metadata_dirty = False
        if inspect.isawaitable(update_result):
            await update_result

    def _dedupe_transactions(self, transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep the first instance of each unique transaction record."""
        seen: set[tuple[str, str, str, str, str, str]] = set()
        unique: list[dict[str, Any]] = []
        for tx in transactions:
            key = (
                (tx.get("symbol") or "").strip().upper(),
                (tx.get("broker") or "unknown").strip().lower(),
                str(tx.get("date") or "").strip(),
                str(tx.get("quantity") or "").strip(),
                str(tx.get("price") or "").strip(),
                (tx.get("type") or "").strip().upper(),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(tx)
        return unique

    async def async_refresh_asset(self, symbol: str, broker: str | None = None) -> None:
        """Refresh a single asset via Stooq and update coordinator data."""
        symbol = (symbol or "").replace("$", "").strip().upper()
        if not symbol:
            return

        assets = list(self.data.get("assets", []) if self.data else [])
        if not assets:
            await self.async_request_refresh()
            return

        target_broker = broker or None
        target_asset = None
        for asset in assets:
            if asset.get("symbol") == symbol and (not target_broker or asset.get("broker") == target_broker):
                target_asset = asset
                break

        if not target_asset:
            return

        broker_name = target_broker or target_asset.get("broker") or self.entry.data.get(CONF_BROKER_NAME, "broker")
        symbol_mapping = get_default_symbol_mapping()
        stored_mapping = self.entry.data.get(CONF_SYMBOL_MAPPING, {})
        if stored_mapping:
            symbol_mapping.setdefault(broker_name, {}).update(stored_mapping)

        mapped_symbol = map_symbol(broker_name, symbol, symbol_mapping)
        quotes = await self.hass.async_add_executor_job(lambda: get_stooq_quotes([mapped_symbol]))
        quote = quotes.get(mapped_symbol, {})
        price = quote.get("price")
        currency = quote.get("currency") or target_asset.get("currency")

        new_assets: list[dict[str, Any]] = []
        for asset in assets:
            if asset.get("symbol") == symbol and (not target_broker or asset.get("broker") == target_broker):
                updated = {**asset}
                quantity = float(updated.get("quantity", 0.0))
                avg_buy = float(updated.get("avg_buy_price", 0.0))
                updated["current_price"] = price
                updated["currency"] = currency
                updated["unmapped"] = price is None
                updated["last_price_update"] = quote.get("timestamp")
                updated["market_value"] = price * quantity if price is not None else None
                updated["profit_loss_abs"] = (price - avg_buy) * quantity if price is not None else None
                updated["profit_loss_pct"] = (((price - avg_buy) / avg_buy) * 100) if price is not None and avg_buy else 0
                new_assets.append(updated)
            else:
                new_assets.append(asset)

        total_value = 0.0
        total_invested = 0.0
        unmapped_symbols: list[str] = []
        for asset in new_assets:
            quantity = float(asset.get("quantity", 0.0))
            avg_buy = float(asset.get("avg_buy_price", 0.0))
            market_value = asset.get("market_value")
            if market_value is not None:
                total_value += market_value
            total_invested += avg_buy * quantity
            if asset.get("unmapped"):
                unmapped_symbols.append(asset.get("symbol"))

        total_profit_loss = total_value - total_invested
        total_profit_loss_pct = ((total_profit_loss / total_invested) * 100) if total_invested else 0

        unmapped_unique = sorted(set([s for s in unmapped_symbols if s]))
        prev_unmapped = set(self.entry.data.get("unmapped_symbols", []))
        if self.entry.data.get("unmapped_symbols") != unmapped_unique:
            await self._update_entry_data({"unmapped_symbols": unmapped_unique})

        new_unmapped = set(unmapped_unique)
        to_remove = prev_unmapped - new_unmapped
        name_by_symbol = {a.get("symbol"): a.get("name") for a in (self.data or {}).get("assets", [])}
        for sym in new_unmapped:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id=f"unmapped_{self.entry.entry_id}_{sym}",
                is_fixable=True,
                is_persistent=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="unmapped_symbol",
                translation_placeholders={
                    "symbol": sym,
                    "name": name_by_symbol.get(sym) or sym,
                },
                data={
                    "entry_id": self.entry.entry_id,
                    "symbol": sym,
                    "name": name_by_symbol.get(sym) or sym,
                },
            )
        for sym in to_remove:
            ir.async_delete_issue(
                self.hass,
                DOMAIN,
                issue_id=f"unmapped_{self.entry.entry_id}_{sym}",
            )

        new_data = {
            **(self.data or {}),
            "assets": new_assets,
            "unmapped_symbols": unmapped_unique,
            "totals": {
                "total_value": total_value,
                "total_invested": total_invested,
                "total_profit_loss": total_profit_loss,
                "total_profit_loss_pct": total_profit_loss_pct,
            },
        }
        self.async_set_updated_data(new_data)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sources."""
        try:
            symbols: list[str] = self.entry.options.get("symbols", self.entry.data.get("symbols", []))
            positions: list[dict[str, Any]] = self._positions
            transactions: list[dict[str, Any]] = list(self.entry.data.get("transactions", []))
            transactions = self._dedupe_transactions(transactions)
            self._transactions = transactions
            broker_type = self.entry.data.get(CONF_BROKER_TYPE, "csv")
            csv_mode = self.entry.options.get(CONF_CSV_MODE, self.entry.data.get(CONF_CSV_MODE, "directory"))
            csv_path = self.entry.options.get(CONF_CSV_PATH, self.entry.data.get(CONF_CSV_PATH))
            provider = self.entry.options.get(
                CONF_MARKET_DATA_PROVIDER,
                self.entry.data.get(CONF_MARKET_DATA_PROVIDER, "yahoo_public"),
            )
            alpha_key = self.entry.options.get(
                CONF_ALPHA_VANTAGE_API_KEY,
                self.entry.data.get(CONF_ALPHA_VANTAGE_API_KEY, ""),
            )

            # If positions are explicitly provided in entry data, prefer them.
            if self.entry.data.get("positions"):
                positions = self.entry.data.get("positions", [])

            if broker_type == "csv":
                if csv_mode == "directory":
                    import_dir = Path(self.hass.config.path("www", "investment_tracker_imports"))
                    import_dir.mkdir(parents=True, exist_ok=True)

                    def _merge_positions(current: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
                        index: dict[tuple[str, str], dict[str, Any]] = {}
                        for pos in current:
                            key = (pos.get("broker", "unknown"), pos.get("symbol", ""))
                            index[key] = pos
                        for pos in incoming:
                            key = (pos.get("broker", "unknown"), pos.get("symbol", ""))
                            existing = index.get(key, {})
                            merged = {**existing, **pos}
                            if existing.get("manual_type"):
                                merged["manual_type"] = True
                                merged["type"] = existing.get("type", merged.get("type"))
                            index[key] = merged
                        return list(index.values())

                    # Process any new CSV files in directory (excluding transaction CSVs)
                    for import_file in import_dir.glob("*.csv"):
                        if import_file.name.endswith("_transactions.csv"):
                            continue
                        default_broker = import_file.stem.replace(" ", "")
                        incoming = await self.hass.async_add_executor_job(
                            parse_positions_csv, str(import_file), default_broker
                        )
                        positions = _merge_positions(positions, incoming)
                        await self._update_entry_data({"positions": positions})
                        processed_file = import_file.with_suffix(import_file.suffix + f".processed.{int(time())}")
                        import_file.rename(processed_file)

                    # Transaction CSVs: {broker}_transactions.csv
                    for tx_file in import_dir.glob("*_transactions.csv"):
                        broker = tx_file.stem.replace("_transactions", "").replace(" ", "")
                        incoming_tx = await self.hass.async_add_executor_job(
                            parse_transactions_csv, str(tx_file), broker
                        )
                        if incoming_tx:
                            transactions.extend(incoming_tx)
                            transactions = self._dedupe_transactions(transactions)
                            self._transactions = transactions
                            await self._update_entry_data({"transactions": transactions})
                        processed_tx = tx_file.with_suffix(tx_file.suffix + f".processed.{int(time())}")
                        tx_file.rename(processed_tx)

                    # If no positions yet, allow reading latest processed file once
                    if not positions:
                        processed = sorted(import_dir.glob("*.csv.processed.*"))
                        if processed:
                            last_file = processed[-1]
                            default_broker = last_file.name.split(".csv.processed")[0].replace(" ", "")
                            positions = await self.hass.async_add_executor_job(
                                parse_positions_csv, str(last_file), default_broker
                            )
                            await self._update_entry_data({"positions": positions})
                elif csv_path:
                    positions = await self.hass.async_add_executor_job(parse_positions_csv, csv_path)
                    await self._update_entry_data({"positions": positions})

            # Recompute positions if transactions are present (do not persist to avoid compounding)
            if transactions:
                positions = apply_transactions_to_positions(positions, transactions)

            if not symbols and positions:
                symbols = [pos.get("symbol") for pos in positions if pos.get("symbol")]
            symbols = [s.replace("$", "").strip().upper() for s in symbols if s]

            self.logger.debug(
                "Market data provider=%s symbols=%s positions=%s",
                provider,
                symbols,
                len(positions),
            )
            if not symbols:
                self.logger.debug("No symbols available for market data fetch.")

            position_lookup: dict[str, dict[str, Any]] = {}
            symbol_brokers: dict[str, set[str]] = {}
            for pos in positions:
                sym = (pos.get("symbol") or "").strip().upper()
                broker = (pos.get("broker") or "unknown").strip().lower()
                if sym:
                    position_lookup[sym] = pos
                    symbol_brokers.setdefault(sym, set()).add(broker)

            broker_name = self.entry.data.get(CONF_BROKER_NAME, "broker")
            symbol_mapping = get_default_symbol_mapping()
            stored_mapping = self.entry.data.get(CONF_SYMBOL_MAPPING, {})
            if stored_mapping:
                symbol_mapping.setdefault(broker_name, {}).update(stored_mapping)

            symbol_map: dict[str, str] = {}
            mapped_symbols: list[str] = []
            unresolved_symbols: list[str] = []
            mapping_updates: dict[str, str] = {}

            search_candidates: dict[str, list[dict[str, Any]]] = {}

            if provider == "alpha_vantage":
                for symbol in symbols:
                    symbol_map[symbol] = symbol
                    mapped_symbols.append(symbol)
            elif provider == "yahoo_public":
                for symbol in symbols:
                    pos = position_lookup.get(symbol, {})
                    if pos.get("type") == "commodity":
                        currency = pos.get("currency") or self.entry.options.get(
                            "base_currency", self.entry.data.get("base_currency", "USD")
                        )
                        mapped = f"{symbol}{str(currency).strip().upper()}"
                        symbol_map[symbol] = mapped
                        mapped_symbols.append(mapped)
                        continue
                    existing = stored_mapping.get(symbol) if stored_mapping else None
                    if existing:
                        symbol_map[symbol] = existing
                        mapped_symbols.append(existing)
                        continue

                    results = await self.hass.async_add_executor_job(search_symbols, symbol)
                    search_candidates[symbol] = results[:5] if results else []
                    candidates = [r["symbol"] for r in results]
                    scored = [
                        (cand, SequenceMatcher(None, symbol.upper(), cand.upper()).ratio())
                        for cand in candidates
                    ]
                    high = [cand for cand, score in scored if score >= 0.9]
                    if len(high) == 1:
                        mapped = high[0]
                        symbol_map[symbol] = mapped
                        mapped_symbols.append(mapped)
                        mapping_updates[symbol] = mapped
                    else:
                        symbol_map[symbol] = symbol
                        mapped_symbols.append(symbol)
                        unresolved_symbols.append(symbol)
            else:
                for symbol in symbols:
                    mapped = map_symbol(broker_name, symbol, symbol_mapping)
                    symbol_map[symbol] = mapped
                    mapped_symbols.append(mapped)

            if mapping_updates:
                new_mapping = {**stored_mapping, **mapping_updates} if stored_mapping else {**mapping_updates}
                await self._update_entry_data({CONF_SYMBOL_MAPPING: new_mapping})

            self.logger.debug(
                "Symbol mapping: %s",
                {"symbol_map": symbol_map, "unresolved": unresolved_symbols, "mapped_symbols": mapped_symbols},
            )

            if provider == "alpha_vantage":
                if not alpha_key:
                    self.logger.warning("Alpha Vantage selected but no API key set; falling back to Stooq.")
                    quotes = await self.hass.async_add_executor_job(lambda: get_stooq_quotes(mapped_symbols))
                else:
                    cache_path = self.hass.config.path("investment_tracker_alpha_cache.json")
                    quotes = await self.hass.async_add_executor_job(
                        lambda: get_alpha_quotes(mapped_symbols, alpha_key, cache_path)
                    )
                    missing = [sym for sym, quote in quotes.items() if quote.get("price") is None]
                    if missing:
                        stooq_map = {sym: map_symbol(broker_name, sym, symbol_mapping) for sym in missing}
                        stooq_symbols = [stooq_map[sym] for sym in missing]
                        fallback_quotes = await self.hass.async_add_executor_job(
                            lambda: get_stooq_quotes(stooq_symbols)
                        )
                        for sym in missing:
                            mapped = stooq_map.get(sym, sym)
                            fallback = fallback_quotes.get(mapped)
                            if fallback and fallback.get("price") is not None:
                                quotes[sym] = fallback
            elif provider == "yahoo_public":
                self.logger.debug("Yahoo public fetch: %s", mapped_symbols)
                yahoo_symbols: list[str] = []
                stooq_symbols: list[str] = []
                for symbol, mapped in symbol_map.items():
                    pos = position_lookup.get(symbol, {})
                    if pos.get("type") == "commodity":
                        stooq_symbols.append(mapped)
                    else:
                        yahoo_symbols.append(mapped)

                quotes = {}
                if yahoo_symbols:
                    yahoo_quotes = await self.hass.async_add_executor_job(
                        lambda: get_yahoo_quotes(yahoo_symbols)
                    )
                    quotes.update(yahoo_quotes)
                if stooq_symbols:
                    stooq_quotes = await self.hass.async_add_executor_job(
                        lambda: get_stooq_quotes(stooq_symbols)
                    )
                    quotes.update(stooq_quotes)
            else:
                self.logger.debug("Stooq fetch: %s", mapped_symbols)
                quotes = await self.hass.async_add_executor_job(lambda: get_stooq_quotes(mapped_symbols))

            assets: list[dict[str, Any]] = []
            total_value = 0.0
            total_active_invested = 0.0
            unmapped_symbols: list[str] = []
            realized_profit_loss = compute_realized_profit_loss(transactions) if transactions else 0.0
            symbol_asset_types: dict[str, str] = {}

            quote_type_cache: dict[str, dict[str, Any] | None] = {}
            summary_profile_cache: dict[str, dict[str, Any] | None] = {}

            for pos in positions or [{"symbol": s, "quantity": 0.0, "avg_buy_price": 0.0, "broker": "unknown"} for s in symbols]:
                symbol = pos.get("symbol")
                if not symbol:
                    continue
                mapped_symbol = symbol_map.get(symbol, symbol)
                quote = quotes.get(mapped_symbol, {})
                price = quote.get("price")
                currency = quote.get("currency")
                quantity = float(pos.get("quantity", 0.0))
                avg_buy = float(pos.get("avg_buy_price", 0.0))
                unmapped = symbol in unresolved_symbols
                if unmapped:
                    unmapped_symbols.append(symbol)



                name = pos.get("name", symbol)
                display_name = symbol
                exchange_name = "unknown"
                country = "unknown"
                sector = "unknown"
                industry = "unknown"
                logo_url = None
                yahoo_type = None
                # Enrich via Yahoo search and quoteType APIs
                if provider == "yahoo_public" and mapped_symbol:
                    search_results = await self.hass.async_add_executor_job(search_symbols, mapped_symbol)
                    if search_results:
                        search_info = next((r for r in search_results if r.get("symbol") == mapped_symbol), search_results[0])
                    else:
                        search_info = None
                    if search_info:
                        sector = search_info.get("sector") or "unknown"
                        industry = search_info.get("industry") or "unknown"
                        logo_url = search_info.get("logoUrl") or search_info.get("logo_url")
                        yahoo_type = search_info.get("quoteType") or None
                        exchange_name = search_info.get("exchange") or "unknown"
                        short_name = search_info.get("shortName") or search_info.get("shortname")
                        long_name = search_info.get("longName") or search_info.get("longname")
                        display_name = short_name or long_name or display_name
                        name = display_name
                    if mapped_symbol not in quote_type_cache:
                        quote_type_cache[mapped_symbol] = await self.hass.async_add_executor_job(
                            get_quote_type, mapped_symbol
                        )
                    quote_type = quote_type_cache.get(mapped_symbol) or {}
                    if not exchange_name:
                        exchange_name = quote_type.get("fullExchangeName") or quote_type.get("exchangeName") or exchange_name
                    if not short_name and not long_name:
                        display_name = quote_type.get("shortName") or quote_type.get("longName") or display_name
                        name = display_name
                    if not yahoo_type:
                        yahoo_type = (quote_type.get("quoteType") or quote_type.get("type"))
                    if not logo_url:
                        logo_url = quote_type.get("logoUrl") or quote_type.get("logo_url")

                # Map Yahoo type/category to integration type
                def map_yahoo_category(yahoo_type, sector, industry):
                    yt = (yahoo_type or "").lower()
                    sec = (sector or "").lower()
                    ind = (industry or "").lower()
                    if yt in ["etf", "exchange-traded fund"] or "etf" in ind:
                        return "etf"
                    if yt in ["bond"] or "bond" in ind or "fixed income" in sec:
                        return "bond"
                    if yt in ["commodity"] or "commodity" in sec or "commodity" in ind:
                        return "commodity"
                    if yt in ["cryptocurrency", "crypto"] or "crypto" in ind or "crypto" in sec:
                        return "crypto"
                    if yt in ["cash"] or "cash" in ind or "cash" in sec:
                        return "cash"
                    if yt in ["equity", "stock"] or "stock" in ind or "stock" in sec or "equity" in sec or "equity" in ind:
                        return "equity"
                    if not sec and not ind:
                        return "equity"
                    return "other"

                mapped_type = map_yahoo_category(yahoo_type, sector, industry)
                manual_override = bool(pos.get("manual_type"))
                asset_type = pos.get("type") if manual_override else mapped_type
                if symbol:
                    symbol_asset_types[symbol.strip().upper()] = asset_type or ""

                effective_avg_buy = avg_buy
                if asset_type == "bond" and effective_avg_buy <= 0 and price is not None:
                    effective_avg_buy = price

                if price is not None:
                    if asset_type == "bond":
                        percent_value = price / 100
                        percent_cost = (effective_avg_buy or price) / 100 if (effective_avg_buy or price) else 0
                        market_value = percent_value * quantity
                        profit_loss_abs = ((price - effective_avg_buy) / 100 if effective_avg_buy else 0) * quantity
                        profit_loss_pct = (((price - effective_avg_buy) / effective_avg_buy) * 100) if effective_avg_buy else 0
                        total_active_invested += percent_cost * quantity
                    else:
                        market_value = price * quantity
                        if effective_avg_buy:
                            profit_loss_abs = (price - effective_avg_buy) * quantity
                            profit_loss_pct = (((price - effective_avg_buy) / effective_avg_buy) * 100)
                        else:
                            profit_loss_abs = 0
                            profit_loss_pct = 0
                        total_active_invested += (effective_avg_buy or 0) * quantity
                else:
                    market_value = None
                    profit_loss_abs = None
                    profit_loss_pct = 0

                if market_value is not None:
                    total_value += market_value

                pos_broker = (pos.get("broker") or "unknown").strip().lower()
                asset_transactions = [
                    tx
                    for tx in transactions
                    if (tx.get("symbol") or "").strip().upper() == symbol
                    and (tx.get("broker") or "unknown").strip().lower() == pos_broker
                ]
                if not asset_transactions and len(symbol_brokers.get(symbol, set())) == 1:
                    asset_transactions = [
                        tx
                        for tx in transactions
                        if (tx.get("symbol") or "").strip().upper() == symbol
                    ]

                assets.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "display_name": display_name,
                        "exchange_name": exchange_name,
                        "country": country,
                        "sector": sector,
                        "industry": industry,
                        "logoUrl": logo_url,
                        "type": asset_type,
                        "quantity": quantity,
                        "avg_buy_price": avg_buy,
                        "current_price": price,
                        "currency": currency or pos.get("currency"),
                        "market_value": market_value,
                        "profit_loss_abs": profit_loss_abs,
                        "profit_loss_pct": profit_loss_pct,
                        "broker": pos.get("broker", "unknown"),
                        "unmapped": unmapped,
                        "last_price_update": quote.get("timestamp"),
                        "transactions": asset_transactions,
                        "repair_suggestions": search_candidates.get(symbol, []),
                    }
                )

            total_cash_invested = compute_total_cash_invested(transactions, symbol_asset_types) if transactions else 0.0
            total_profit_loss_unrealized = total_value - total_active_invested
            total_profit_loss = total_profit_loss_unrealized + realized_profit_loss
            total_profit_loss_pct = ((total_profit_loss / total_cash_invested) * 100) if total_cash_invested else 0

            # Persist unmapped symbols for repairs visibility
            unmapped_unique = sorted(set(unmapped_symbols))
            prev_unmapped = set(self.entry.data.get("unmapped_symbols", []))
            if self.entry.data.get("unmapped_symbols") != unmapped_unique:
                await self._update_entry_data({"unmapped_symbols": unmapped_unique})

            name_by_symbol = {a.get("symbol"): a.get("name") for a in assets}
            new_unmapped = set(unmapped_unique)
            to_remove = prev_unmapped - new_unmapped
            for symbol in new_unmapped:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id=f"unmapped_{self.entry.entry_id}_{symbol}",
                    is_fixable=True,
                    is_persistent=True,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="unmapped_symbol",
                    translation_placeholders={
                        "symbol": symbol,
                        "name": name_by_symbol.get(symbol) or symbol,
                    },
                    data={
                        "entry_id": self.entry.entry_id,
                        "symbol": symbol,
                        "name": name_by_symbol.get(symbol) or symbol,
                    },
                )
            for symbol in to_remove:
                ir.async_delete_issue(
                    self.hass,
                    DOMAIN,
                    issue_id=f"unmapped_{self.entry.entry_id}_{symbol}",
                )

            # Repairs are provided via repairs.py using unmapped_symbols

            return {
                "portfolio": {
                    "base_currency": self.entry.options.get("base_currency", self.entry.data.get("base_currency", "EUR")),
                },
                "assets": assets,
                "unmapped_symbols": unmapped_unique,
                "totals": {
                    "total_value": total_value,
                    "total_active_invested": total_active_invested,
                    "total_invested": total_cash_invested,
                    "total_profit_loss": total_profit_loss,
                    "total_profit_loss_pct": total_profit_loss_pct,
                    "total_profit_loss_realized": realized_profit_loss,
                    "total_profit_loss_unrealized": total_profit_loss_unrealized,
                },
            }
        except Exception as err:  # pragma: no cover
            raise UpdateFailed(str(err)) from err
