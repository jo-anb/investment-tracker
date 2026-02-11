# Investment Tracker

A Home Assistant integration that gathers brokerage balances, normalizes symbols, and exposes a structured portfolio model as sensors. The companion custom Lovelace card (`investment-tracker-card`) renders the same data with day-change totals, realized/unrealized splits, allocation pies, and a plan tracker.

## Table of contents
1. [Installation](#installation)
2. [Core data model](#core-data-model)
3. [Data ingestion](#data-ingestion)
4. [Entities and sensors](#entities-and-sensors)
5. [Lovelace card data contract](#lovelace-card-data-contract)
6. [Development notes](#development-notes)

## Installation
1. Copy `custom_components/investment_tracker` and the `investment-tracker-card` source to your Home Assistant configuration (see `custom_components` and `www/community`).
2. Restart Home Assistant.
3. Configure the integration via the UI: choose a broker name, set `broker_type` (api/csv/manual), optionally point to a CSV file or directory, and pick your market-data provider (default `yahoo_public`).
4. Add the Lovelace card using `type: custom:investment-tracker-card` and target the service sensor entity that appears under `sensor.<your_integration>`.

## Core data model
The integration enforces a broker-agnostic model so any provider that supplies the required fields can be tracked.

### Assets
Each asset includes:
- `symbol`, `name`, `type` (equity, etf, bond, commodity, crypto, cash)
- `quantity`, `avg_buy_price`, `currency`
- `current_price`, `market_value`, `profit_loss_abs`, `profit_loss_pct`
- `broker`, `unmapped`, `last_price_update`, `transactions`

Constraints:
- `symbol` must be unique per `broker` (key = `broker:symbol`).
- `avg_buy_price >= 0`, `quantity > 0`.
- If `unmapped=true`, live pricing is not required.

### Portfolio totals
- `total_value`: sum of asset market values.
- `total_invested`: sum of `avg_buy_price * quantity`.
- `total_profit_loss`/`total_profit_loss_pct`: derived totals in the chosen base currency (default EUR).
- `base_currency`: entry-level base currency; used for display by the custom card.

### Brokers
Each config entry represents a broker:
- `broker_name`: unique identifier.
- `broker_type`: enum (`api`, `csv`, `manual`).
- `connected`: service sensor attribute, toggled when data refresh succeeds.
- `broker_names`/`broker_slugs`: service attributes that list every broker feeding assets for that entry (helpful when directory imports add additional CSV brokers such as `revolut_roboadvisor`).

### Transactions (optional)
Transaction files can be provided beside positions. Each row needs:
- `symbol`, `date` (ISO), `quantity`, `price`, `currency`, `broker`.
Transactions rebuild positions without updating stored `positions.csv`.

## Data ingestion
### CSV import
- Position CSV files must be UTF-8 and include headers such as `symbol`, `name`, `type`, `quantity`, `avg_buy_price`, `currency`, `broker`.
- Optional columns: `current_price`, `market_value`, `unmapped`, `last_price_update`.
- Place files in `config/www/investment_tracker_imports/`; the integration watches `*.csv`, merges them, and renames them to `.processed` after ingestion.
- Transaction files follow the same directory and must be named `{broker}_transactions.csv`.
- The helper handles Revolut-style exports where every row is quoted and may carry a BOM; additional brokers (e.g., `revolut_roboadvisor`) simply appear as extra assets under the same entry because the service sensor now advertises every encountered broker name.

### API and market data providers
- Market data is fetched via Yahoo public endpoints (`yahoo_public` provider) or Alpha Vantage (optional API key).
- Symbol mapping runs before every fetch; unmapped assets are marked (`unmapped=true`) and still expose quantity + transactions without live prices.
- Quotes are refreshed every 15 minutes by the `InvestmentTrackerCoordinator` (DataUpdateCoordinator).

### Manual transactions/positions
Use the options flow to add manual symbols or transactions when other feeds cannot report certain assets (e.g., cash vaults, private equities, precious metals).

## Entities and sensors
### Service sensor (`sensor.<service>_service`)
Carries metadata such as `broker_name`, `broker_type`, `broker_names`, `broker_slugs`, plan details, and `alpha_vantage_api_key_set`.

### Aggregations
- `sensor.<service>_investment_total_value`
- `sensor.<service>_investment_total_invested`
- `sensor.<service>_investment_total_profit_loss`
- `sensor.<service>_investment_total_profit_loss_pct`
- `sensor.<service>_investment_total_active_invested`
- `sensor.<service>_investment_total_profit_loss_realized`
- `sensor.<service>_investment_total_profit_loss_unrealized`

These sensors back the Lovelace card totals.

### Asset entities
Each asset generates two sensors:
- `asset_value`: `sensor.<broker>_<symbol>` exposes `market_value`, `currency`, `quantity`, `profit_loss_abs`, etc.
- `asset_profit_loss_pct`: `sensor.<broker>_<symbol>_pl_pct` carries the percentage attribute.

The card deduplicates assets by `symbol+broker` and hides duplicates.

## Lovelace card data contract
The `investment-tracker-card` reads the sensors listed above and also fetches history for day change calculations. It offers:
- Header with total value, day change (zero when no history), and total return with realized/unrealized split.
- Asset list with price, quantity, profit/loss, and remap/history actions.
- Charts (portfolio history, allocation pies, investment plan).

Config highlights:
```yaml
type: custom:investment-tracker-card
title: My Portfolio
service_entity: sensor.investment_tracker_revolut
show_positions: true
show_charts: true
show_plan: true
hide_unmapped: false
default_service_entity: sensor.investment_tracker_csv
```
The card also lets you point to `service_entity` or `default_service_entity`, and it automatically finds assets from every broker the service exposes (`broker_names`).

## Development notes
- `custom_components/investment_tracker/`: integration source (coordinator, helpers, sensors, config flow, services).
- `investment-tracker-card/src/`: Lovelace card code.
- Examples live in `examples/`.
- Run `npm install` inside `investment-tracker-card` before bundling the card.
- The integration exposes services such as `investment_tracker.refresh` and `investment_tracker.refresh_asset` to request a data pull.

Contributions, issues, and feature ideas can be tracked inside this repository via GitHub issues.
