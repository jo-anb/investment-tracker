# Investment Tracker Project Definition

---

# 🧩 **1. Naam & Positionering**
### **Integratie:**  
**Investment Tracker**  
→ Een Home Assistant integratie die portfolio‑data verzamelt, normaliseert en exposeert als entities.

### **Frontend Card:**  
**Portfolio‑card**  
→ Een Lovelace custom card die de data visualiseert.

### **Doelgroep**
- Iedereen met een broker (Revolut, DeGiro, Trading212, eToro, Binance, etc.)
- Mensen die hun portfolio willen monitoren in Home Assistant
- Gebruikers die DCA‑schema’s willen tracken
- Mensen die hun investeringsgedrag willen automatiseren of visualiseren

---

# 🧩 **2. Wat de integratie moet verzamelen**
We definiëren een **minimaal datamodel** dat broker‑agnostisch is.  
Dat betekent: elke broker kan worden gekoppeld zolang hij deze velden kan leveren.

### **A. Portfolio inhoud**
Per asset:
- `symbol` (NVDA, VWCE, XAU, etc.)
- `name`
- `type` (equity, etf, bond, commodity, crypto, cash)
- `quantity`
- `avg_buy_price`
- `current_price`
- `currency`
- `market_value`
- `profit_loss_abs`
- `profit_loss_pct`
- `broker` (Revolut, DeGiro, etc.)
- `unmapped` (true/false) → true als het symbool niet door yfinance kan worden gemapt; dan geen live prijs.

**Datamodel regels (Asset)**
- `symbol`: verplicht, uniek per broker + asset (key: `broker:symbol`).
- `name`: verplicht, fallback = `symbol`.
- `type`: verplicht, enum (equity, etf, bond, commodity, crypto, cash).
- `quantity`: verplicht, > 0.
- `avg_buy_price`: verplicht, >= 0.
- `current_price`: optioneel als `unmapped=true`, anders verplicht, >= 0.
- `currency`: verplicht, ISO‑4217 (EUR, USD, GBP, etc.).
- `market_value`: afgeleid = `quantity * current_price` (indien mapped).
- `profit_loss_abs`: afgeleid = `(current_price - avg_buy_price) * quantity`.
- `profit_loss_pct`: afgeleid = `(current_price - avg_buy_price) / avg_buy_price` (0 als avg_buy_price=0).
- `broker`: verplicht, verwijst naar `Broker`.
- `unmapped`: verplicht, default `false`.
- `last_price_update`: optioneel, timestamp van laatste prijsupdate.
- `transactions`: optioneel, lijst van aankopen (voor unmapped of detaillering).

**Transaction (optioneel per asset)**
- `date`: verplicht (YYYY‑MM‑DD)
- `quantity`: verplicht, > 0
- `price`: verplicht, >= 0
- `currency`: verplicht, ISO‑4217

### **B. Investering per maand**
- `monthly_investment_target`
- `monthly_investment_actual`
- `monthly_investment_per_asset`
- `monthly_investment_per_category`

### **C. Aankoop frequentie**
Per asset:
- `frequency` (weekly, monthly, custom)
- `next_buy_date`
- `amount_per_buy`

### **D. Brokers**
- `broker_name`
- `broker_type` (api, csv, manual)
- `connected` (true/false)
- `last_sync`

**Datamodel regels (Broker)**
- `broker_name`: verplicht, uniek.
- `broker_type`: verplicht, enum (api, csv, manual).
- `connected`: verplicht, default `false`.
- `last_sync`: optioneel, timestamp.
- `accounts`: optioneel, lijst met account‑ids (voor multi‑account brokers).

### **E. Totale investering**
- `total_value`
- `total_invested`
- `total_profit_loss`
- `total_profit_loss_pct`

**Datamodel regels (Portfolio)**
- `total_value`: afgeleid, som van `market_value` (mapped assets).
- `total_invested`: afgeleid, som van `avg_buy_price * quantity`.
- `total_profit_loss`: afgeleid, `total_value - total_invested`.
- `total_profit_loss_pct`: afgeleid, `total_profit_loss / total_invested` (0 als total_invested=0).
- `base_currency`: verplicht (default EUR).
- `assets`: lijst van `Asset`.

**Datamodel regels (MarketData)**
- `symbol`: verplicht.
- `price`: verplicht (>=0).
- `currency`: verplicht.
- `timestamp`: verplicht.
- `source`: verplicht, fixed = `yfinance`.

---

# 🧩 **3. Hoe de integratie data verzamelt**
We ontwerpen drie mogelijke datastromen:

## **0. Data‑flow & normalisatie (globaal)**
1. **Ingest** vanuit broker (API/CSV/handmatig) → ruwe posities + transacties.
2. **Symbol mapping** → map broker‑symbol naar Yahoo Finance symbol.
3. **Market data fetch** via `yfinance` (best‑effort elke 1 minuut).
4. **Normalisatie** → valuta, numerieke afronding, berekende velden.
5. **Opslag** → assets + portfolio totals + `unmapped` status.
6. **Expose** → Home Assistant entities & sensors.

### **Symbol mapping regels**
- Als broker‑symbool direct werkt in Yahoo → use as‑is.
- Als broker‑symbool afwijkt → mapping tabel (per broker) in `helpers.py`.
- Als mapping faalt → `unmapped=true`, skip `current_price` en berekende waardes die prijs vereisen.
- `unmapped` assets blijven wel zichtbaar met quantity + transacties.

### **Currency normalisatie**
- `base_currency` = EUR (default), kan later configurabel worden.
- Als Yahoo prijs in andere valuta levert → omrekenen naar `base_currency` via FX rate (later toevoegen).
- Indien FX ontbreekt → behoud originele currency en markeer asset als `currency_mismatch=true` (toekomstig attribuut).

### **Refresh & caching**
- Market data refresh = **best‑effort 1 minuut**.
- Bij rate‑limit of timeouts → exponential backoff (max 15 min) + log waarschuwing.
- Cached prices worden hergebruikt tot volgende succesvolle refresh.

## **A. API‑koppelingen (automatisch)**
Voor brokers die een API hebben:
- Revolut (unofficial API)
- Binance
- Coinbase
- Alpaca
- Interactive Brokers (TWS API)
- Yahoo Finance (market data)
- Finnhub (market data)
- Alpha Vantage (market data)

### **Market data API**
- Yahoo Finance via yfinance (primary, fixed)
  - best‑effort refresh: elke 1 minuut
  - geen user override
  - historische prijzen: optioneel
  - als ticker niet mapbaar is: markeer unmapped=true en sla transactiegegevens op

De integratie haalt:
- actuele prijzen
- historische prijzen
- dividend data (optioneel)

## **B. CSV‑import (semi‑automatisch)**
Voor brokers zonder API:
- DeGiro
- Trading212
- eToro

Gebruiker uploadt CSV → integratie parse’t → slaat op.

### **CSV‑schema (canoniek)**
Bestand moet UTF‑8 zijn en een header bevatten. Kolomnamen zijn case‑insensitive.

**Verplicht**
- `symbol`
- `name`
- `type` (equity, etf, bond, commodity, crypto, cash)
- `quantity`
- `avg_buy_price`
- `currency`
- `broker`

**Optioneel**
- `current_price`
- `market_value`
- `unmapped` (true/false)
- `last_price_update`

**Transactie‑CSV (optioneel, apart bestand)**
- `symbol` (verplicht)
- `date` (YYYY‑MM‑DD, verplicht)
- `quantity` (verplicht)
- `price` (verplicht)
- `currency` (verplicht)
- `broker` (verplicht)

**Validatieregels**
- Numerieke velden moeten > 0 of >= 0 volgens datamodel.
- Als `unmapped=true` → `current_price` mag leeg zijn.
- Als `current_price` ontbreekt en `unmapped=false` → log waarschuwing.

## **C. Handmatige invoer (fallback)**
Voor exotische assets:
- goud/zilver
- crypto op cold wallets
- private equity

---

# 🧩 **4. Entities die de integratie exposeert**
We maken een **entity per asset** en een aantal **aggregatie‑sensors**.

### **A. Asset entities**
`investment.nvda`  
`investment.msft`  
`investment.vwce`  
`investment.xau`  
etc.

Met attributen:
- quantity
- avg_buy_price
- current_price
- market_value
- profit_loss_abs
- profit_loss_pct
- broker
- category

### **B. Aggregatie‑sensors**
- `sensor.investment_total_value`
- `sensor.investment_total_invested`
- `sensor.investment_total_profit_loss`
- `sensor.investment_total_profit_loss_pct`
- `sensor.investment_monthly_target`
- `sensor.investment_monthly_actual`
- `sensor.investment_monthly_remaining`

### **C. Category sensors**
- `sensor.investment_equities_value`
- `sensor.investment_etf_value`
- `sensor.investment_bonds_value`
- `sensor.investment_metals_value`
- `sensor.investment_crypto_value`
- `sensor.investment_cash_value`

---

# 🧩 **5. Portfolio‑card (frontend design)**
De card moet modulair zijn, met secties:

## **A. Header**
- totale waarde
- dagrendement
- totaalrendement

## **B. Allocatie donut**
- equities
- etf
- bonds
- metals
- crypto
- cash

## **C. Maandelijkse inleg**
- target vs actual
- progress bar
- breakdown per asset

## **D. Posities**
Lijst met:
- logo
- naam
- waarde
- winst/verlies
- percentage

## **E. DCA schema**
- frequentie
- volgende aankoop
- bedrag

---

## **Portfolio‑card data‑contract (v1)**
De card leest Home Assistant entities en verwacht een gestructureerde dataset.

**Verplicht (entities)**
- `sensor.investment_total_value`
- `sensor.investment_total_invested`
- `sensor.investment_total_profit_loss`
- `sensor.investment_total_profit_loss_pct`

**Optioneel (entities)**
- `sensor.investment_monthly_target`
- `sensor.investment_monthly_actual`
- `sensor.investment_monthly_remaining`
- Category sensors (`sensor.investment_*_value`)

**Asset entity attributen**
- `quantity`
- `avg_buy_price`
- `current_price` (optioneel bij `unmapped=true`)
- `market_value` (optioneel bij `unmapped=true`)
- `profit_loss_abs`
- `profit_loss_pct`
- `broker`
- `category`
- `unmapped`
- `last_price_update` (optioneel)

---

## **Portfolio‑card config (YAML schema, v1)**
- `type`: `custom:portfolio-card`
- `title`: optioneel
- `show_header`: true/false
- `show_allocation`: true/false
- `show_monthly`: true/false
- `show_positions`: true/false
- `show_dca`: true/false
- `base_currency`: optioneel (default uit integratie)
- `sort_by`: `market_value` | `profit_loss_pct` | `name`
- `hide_unmapped`: true/false

---

# 🧩 **6. Integratie structuur (backend)**
De integratie zou bestaan uit:

```
custom_components/investment_tracker/
│── __init__.py
│── manifest.json
│── const.py
│── config_flow.py
│── api/
│     ├── yahoo.py
│     ├── broker_revolut.py
│     ├── broker_degiro.py
│── coordinator.py
│── sensor.py
│── helpers.py
│── models.py
│── services.yaml
│── translations/
│     ├── en.json
│     ├── nl.json
```

### **Scaffold details (Home Assistant)**
- `manifest.json`: metadata, version, dependencies, `config_flow=true`, `requirements` (yfinance).
- `__init__.py`: setup entry, init van `DataUpdateCoordinator`.
- `config_flow.py`: setup van broker(s), API keys (indien nodig), polling‑interval en base‑currency.
- `const.py`: domein, defaults, platform names, update interval.
- `api/yahoo.py`: primary market data via `yfinance`.
- `api/broker_*.py`: broker‑specifieke parsing en authenticatie.
- `coordinator.py`: data‑flow, mapping, refresh/backoff, normalisatie.
- `sensor.py`: asset sensors + aggregatie sensors.
- `helpers.py`: symbol mapping, csv parsing helpers, FX (later).
- `models.py`: `Asset`, `Portfolio`, `Broker`, `MarketData` dataclasses.
- `services.yaml`: services zoals `investment_tracker.refresh` of csv‑import.
- `translations/*`: UI strings voor config‑flow en services.

### **manifest.json (spec)**
- `domain`: `investment_tracker`
- `name`: `Investment Tracker`
- `version`: `0.1.0`
- `documentation`: link naar README/GitHub
- `issue_tracker`: link naar GitHub issues
- `requirements`: `yfinance==<pinned>`
- `config_flow`: `true`
- `codeowners`: `@<github-username>`
- `iot_class`: `cloud_polling`
- `loggers`: `yfinance`

### **config_flow (spec)**
**Stap 1: Broker type**
- Kies `api`, `csv`, of `manual`

**Stap 2: Broker details (API)**
- `broker_name` (required)
- `api_key` / `username` / `password` (optioneel, per broker)

**Stap 2: CSV**
- `csv_path` of upload‑flow (later)

**Stap 2: Manual**
- Geen extra velden

**Stap 3: Preferences**
- `base_currency` (default EUR)
- `update_interval` (default 60s, best‑effort)

**Options flow (later)**
- Wijzig `base_currency`
- Wijzig `update_interval`
- Re‑sync / force refresh

### **Coordinator**
- haalt data op
- normaliseert
- update sensors

### **Models**
- Asset
- Portfolio
- Broker
- MarketData

---

# 🧩 **7. Wat we nu moeten doen**
We kunnen nu drie richtingen op:

### **A. Het datamodel verder uitwerken**  
(hoe ziet een Asset object eruit, welke velden zijn verplicht)

### **B. De API‑strategie bepalen**  
(welke market data provider gebruiken we als basis)

### **C. De eerste versie van `manifest.json` en folderstructuur schetsen**

### **D. De Portfolio‑card UI ontwerpen**  
(mockup in YAML of HTML)

---

# 🔥 Wat wil je als volgende stap?  
Wil je:

- het **datamodel** verder uitwerken  
- de **API‑architectuur** bepalen  
- de **folderstructuur** opzetten  
- of de **Portfolio‑card UI** ontwerpen  

Jij bepaalt de richting, ik bouw met je mee.

---

# ✅ MVP‑implementatieplan (v0.1)
Doel: **basis integratie + minimale card**, alleen Yahoo Finance via `yfinance`.

## **Backend (Home Assistant integratie)**
1. **Scaffold files**
  - `manifest.json`, `__init__.py`, `const.py`, `config_flow.py`, `coordinator.py`, `sensor.py`, `models.py`, `helpers.py`.
2. **Market data**
  - `api/yahoo.py` → prijs ophalen via `yfinance`.
  - best‑effort refresh elke 60s + caching.
3. **Data model**
  - `Asset`, `Portfolio`, `Broker`, `MarketData` dataclasses.
4. **Coordinator**
  - Fetch market data, map symbols, bereken totals, set `unmapped`.
5. **Sensors**
  - Asset entities + 4 hoofd aggregaties (total value, invested, profit/loss, profit/loss %).
6. **CSV‑import**
  - Alleen canonieke CSV, parsing via `helpers.py`.

## **Frontend (Portfolio‑card)**
1. **Minimal card layout**
  - Header (total value + total P/L)
  - Positions list (name, value, P/L)
2. **Config support**
  - `show_header`, `show_positions`, `hide_unmapped`.
3. **No charts in MVP**
  - Donut/graphs komen in v0.2.

## **Nice‑to‑have (na MVP)**
- Category allocation donut
- Monthly target/actual
- DCA schedule
- FX conversion
- Historical prices
