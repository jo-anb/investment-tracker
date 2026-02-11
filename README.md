# Investment Tracker

![Investment Tracker](/branding/readme_banner.svg)

A Home Assistant integration that gathers brokerage balances, normalizes symbols, and exposes a structured portfolio model as sensors. The companion custom Lovelace card (`investment-tracker-card`) renders the same data with market totals, historical charts, allocation pies, and a fully interactive plan panel that tracks ongoing investments, weekly progress, and lets you edit the plan directly from the card.

## Table of contents
1. [Installation](#installation)
2. [Core data model](#core-data-model)
3. [Data ingestion](#data-ingestion)
4. [Entities and sensors](#entities-and-sensors)
5. [Lovelace card data contract](#lovelace-card-data-contract)
6. [Development notes](#development-notes)

## Installation
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jo-anb&repository=investment-tracker&category=integration)

OR

1. Install HACS if you don't have it already
2. Open HACS in Home Assistant
3. On the top right side, click the three dot and click `Custom repositories`
4. Where asked for a URL, paste the link of this repository:
https://github.com/jo-anb/investment-tracker
5. Where asked for a type, select `integration`
6. Click the download button. ⬇️
7. Install the [investment-tracker-card](https://github.com/jo-anb/investment-tracker-card) card for your dashboard (optional)

OR Manual

1. Copy `custom_components/investment_tracker` and the `investment-tracker-card` source to your Home Assistant configuration (see `custom_components` and `www/community`).
2. Restart Home Assistant so the manifest resources, icons, and Lovelace card assets are registered.
3. Configure the integration via the UI: choose a broker name, set `broker_type` (`api`, `csv`, or `manual`), optionally provide a CSV file or directory, and pick your market-data provider (default `yahoo_public`).
4. Add the Lovelace card with `type: custom:investment-tracker-card` and target the service sensor that appears as `sensor.<your_integration>_service`.

## Core data model
The integration enforces a broker-agnostic model so any provider that supplies the required fields can be tracked.

### Assets
Each asset includes:
- `symbol`, `name`, `type` (equity, ETF, bond, commodity, crypto, cash)
- `quantity`, `avg_buy_price`, `currency`
- `current_price`, `market_value`, `profit_loss_abs`, `profit_loss_pct`
- `broker`, `unmapped`, `last_price_update`, `transactions`

Constraints:
- `symbol` must be unique per `broker` (key = `broker:symbol`).
- `avg_buy_price >= 0`, `quantity > 0`.
- Unmapped assets (`unmapped=true`) still expose quantity + transaction history without live pricing.

### Portfolio totals
- `total_value`: sum of all asset market values in the base currency.
- `total_invested`: total cost basis (`avg_buy_price * quantity`).
- `total_profit_loss`/`total_profit_loss_pct`: net returns derived in the base currency (default EUR).
- `base_currency`: entry-level currency used for display in the card and plan panel.

### Brokers
Each config entry represents a broker:
- `broker_name`: unique identifier exposed via the service sensor.
- `broker_type`: enum (`api`, `csv`, `manual`).
- `connected`: attribute toggled when data refresh succeeds.
- `broker_names`/`broker_slugs`: lists every broker feeding assets for that entry (useful when importing multiple CSV files under the same entry).

### Transactions (optional)
If provided alongside position CSVs, transaction files include rows with:
- `symbol`, `date` (ISO 8601), `quantity`, `price`, `currency`, `broker`.
The helper rebuilds positions and feeds plan progress without editing `positions.csv`.

## Data ingestion
### CSV import
- Files must be UTF-8 and contain headers such as `symbol`, `name`, `type`, `quantity`, `avg_buy_price`, `currency`, `broker`.
- Optional columns: `current_price`, `market_value`, `unmapped`, `last_price_update`.
- Place files under `config/www/investment_tracker_imports/`; the integration watches `*.csv`, ingests them, and renames them to `.processed` once merged.
- Matching transaction files should be named `{broker}_transactions.csv` in the same directory.
- Revolut-style exports (quoted rows, optional BOM) are supported; any extra brokers (e.g., `revolut_roboadvisor`) appear as additional assets with their own broker metadata.

### API and market data providers
- Quotes are pulled from Yahoo Public (`yahoo_public`) or Alpha Vantage (optional API key).
- Symbol mapping runs before every fetch so unmapped assets are highlighted but still expose their quantity/transactions.
- The `InvestmentTrackerCoordinator` refreshes quotes every 15 minutes via a `DataUpdateCoordinator` pattern.

### Manual transactions/positions
Use the options flow to add manual symbols or transactions when other feeds cannot report certain holdings (cash vaults, private equity, or precious metals). Manual entries show up alongside broker assets via the same sensors.

## Entities and sensors
### Service sensor (`sensor.<service>_service`)
Carries metadata such as `broker_name`, `broker_type`, `broker_names`, `broker_slugs`, the active plan, and whether the `alpha_vantage_api_key` is configured. The custom card reads this sensor for plan definitions, allocations, and metadata for each broker.

### Aggregations
- `sensor.<service>_investment_total_value`
- `sensor.<service>_investment_total_invested`
- `sensor.<service>_investment_total_profit_loss`
- `sensor.<service>_investment_total_profit_loss_pct`
- `sensor.<service>_investment_total_active_invested`
- `sensor.<service>_investment_total_profit_loss_realized`
- `sensor.<service>_investment_total_profit_loss_unrealized`

These sensors power the header totals displayed by the Lovelace card.

### Asset entities
Each asset generates two sensors:
- `asset_value`: `sensor.<broker>_<symbol>` exposes `market_value`, `currency`, `quantity`, `profit_loss_abs`, build metadata, and transaction summaries.
- `asset_profit_loss_pct`: `sensor.<broker>_<symbol>_pl_pct` carries the percentage delta attributes.

The card deduplicates assets by `symbol+broker` and hides duplicates when multiple feeds expose the same asset.

## Lovelace card data contract
The `investment-tracker-card` reads the sensors listed above and fetches history for day-change calculations. It offers:
- Header with total value, day change (zero when history is unavailable), and total return with realized/unrealized splits plus the day-change breakdown.
- Asset list showing price, quantities, profit/loss figures, remap/history actions, and a weekly-invested progress strip that stacks new buys per symbol within the plan panel.
- Charts for portfolio history, allocation pies, and the investment plan grid, including a plan editor modal that uses the `investment_tracker.update_plan` service to persist plan targets, recurring amounts, and allocation blocks.

## Development notes
- `custom_components/investment_tracker/`: integration helpers, coordinator, sensors, config flow, and services (including `refresh`, `refresh_asset`, and plan commands).
- `investment-tracker-card/src/`: Lovelace card logic with plan rendering, transaction aggregation, weekly progress helpers, and the plan editor UI.
- Examples live under `examples/` for both the integration and card.
- Run `npm install` inside `investment-tracker-card` before bundling the card for production builds.
- The manifest exposes `icon_color`, `icon_dark`, and `resources` so Home Assistant can display the icon in the integration picker, as well as the plan palette for the card theme.

Contributions, issues, and feature discussions are welcome via GitHub issues.
