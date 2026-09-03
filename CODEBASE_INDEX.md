# APEX CODEBASE INDEX

> Structural registry only. No plans or roadmaps.
> Rules: Read before writing code. Update on new file/public symbol/fixture. Max 1 line/symbol.

## 1. REPOSITORY LAYOUT
```text
APEX/
├── apex/
│   ├── models/         # Pydantic schemas & contracts
│   ├── collectors/     # Scrapers & site adapters
│   ├── normalization/  # Cleaning, dedup, missing states
│   ├── storage/        # DB models, migrations, repos
│   ├── engine/         # Baseline, route/national index, lead-time
│   ├── validation/     # Benchmark backtests & stats
│   ├── intelligence/   # Quality, confidence, anomaly, provenance
│   └── api/            # FastAPI service & routers
├── docs/               # Schemas & methodology specs
├── tests/              # Fixtures, unit, synthetic tests
├── AGENTS.md           # Agent operational protocol
└── CODEBASE_INDEX.md   # This file
```

## 2. PACKAGE REGISTRY
- `apex.models`: Domain schemas & validation (`fare.py`, `route.py`).
- `apex.collectors`: Scrapers & adapters (`base.py`, `indigo.py`, `mock.py`).
- `apex.normalization`: Ingestion cleaner & dedup (`service.py`, `dedup.py`).
- `apex.storage`: DB access & ORM (`models.py`, `migrations.py`).
- `apex.engine`: Statistical math & index formulas (`route_index.py`, `national_index.py`, `baseline.py`, `lead_time.py`).
- `apex.validation`: Ground truth backtests (`dgca_loader.py`, `metrics.py`).
- `apex.intelligence`: Trust metrics & provenance (`quality.py`, `confidence.py`, `provenance.py`, `anomaly.py`).
- `apex.api`: HTTP endpoints & routers (`app.py`, `routes/`).

## 3. PUBLIC SYMBOL & CONTRACT REGISTRY
### Models (`apex.models`)
- `FareObservation`: Canonical immutable observation (flight identity, fare breakdown, raw hash, status).
- `FlightIdentity`: Airline, flight number, origin, destination, departure time, stops.
- `FareBreakdown`: Currency (INR), base fare, taxes, fees, total payable fare.

### Collectors (`apex.collectors`)
- `BaseCollector`: Abstract scraper class (`collect_route(origin, dest, date, window) -> CollectorResult`).
- `CollectorResult`: Container (`observations`, `raw_payload`, `raw_hash`, `meta`).
- `CircuitBreaker`: Failure/rate-limit circuit breaker decorator.

### Storage (`apex.storage`)
- `FareObservationRecord`: ORM model for `fare_observations` table.
- `RawPayloadRecord`: ORM model for `raw_payloads` table (keyed by SHA-256).
- `CollectionRunRecord`: ORM model for `collection_runs` execution logging.

### Engine (`apex.engine`)
- `BaselineProvider`: Interface for baseline fares ($P_{r,w,0}$).
- `DayZeroMedianBaselineProvider`: Computes initial medians from Day-0 collection.
- `DGCABaselineProvider`: Fetches historical route benchmarks from DGCA data.
- `RouteIndexEngine`: Calculates $I_{r,w,t}$ and route composite $I_{r,t}$.
- `NationalIndexEngine`: Calculates weighted $\text{NAI}_t = \sum W_r I_{r,t}$.
- `LeadTimeAnalyzer`: Computes surge curves across $T+45 \to T+1$.

### Intelligence (`apex.intelligence`)
- `QualityEngine`: Computes coverage, freshness, completeness, source health scores.
- `ConfidenceEngine`: Calculates system confidence score (0-100%).
- `ProvenanceTracer`: Reconstructs DAG from index ID to raw payload SHA-256.
- `AnomalyDetector`: Non-parametric IQR price spike detector.

### API Routes (`apex.api`)
- `GET /api/v1/index/current`: National Index, day-over-day change, confidence.
- `GET /api/v1/routes/{route_id}/lead-time`: Lead-time points and surge multipliers.
- `GET /api/v1/provenance/{index_id}`: Full audit trace down to observation raw hashes.
- `GET /api/v1/validation/dgca`: 30-day benchmark backtest metrics.

## 4. TEST FIXTURE REGISTRY
- `tests/fixtures/observations/valid_fare.json`: Valid IndiGo DEL-BOM sample.
- `tests/fixtures/observations/invalid_fares.json`: Malformed fares (negative, wrong currency).
- `tests/fixtures/dgca_30day.json`: 30-day historical DGCA route benchmark data.
- `tests/fixtures/synthetic_shocks.json`: Synthetic price shocks for mathematical invariant tests.
