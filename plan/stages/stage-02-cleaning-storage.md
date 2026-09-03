# Stage 2: Data Cleaning, Normalization & Local Storage

> **Stage Status**: `PENDING`  
> **Prerequisites**: [Stage 0: Measurement Spec](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-00-measurement-spec.md) and [Stage 1: Acquisition](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-01-data-acquisition.md) must be complete.  
> **Next Stage**: [Stage 3: Statistical & Index Engine](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-03-index-engine.md)

---

## 1. Stage Objective

Raw scraped data is inherently noisy: numbers have commas or currency symbols, flights are duplicated across OTAs, seats sell out, and some fields are missing.

Stage 2 ensures:
1. **Relational Integrity**: Persists data into local PostgreSQL using a structured schema.
2. **Raw vs Normalized Immutability**: The raw payload is never mutated or discarded; normalized records can always be recomputed.
3. **Deduplication**: Multi-source reports for the same physical flight are unified under a canonical flight identity.
4. **Transparent Missing Data**: Missing observations are explicitly classified (`SOLD_OUT`, `TIMEOUT`, `PARSER_ERROR`), preserving data completeness metrics.

---

## 2. Database Schema Design (Local PostgreSQL)

```text
┌──────────────┐       ┌──────────────┐       ┌──────────────────────┐
│   sources    │       │    routes    │       │     raw_payloads     │
├──────────────┤       ├──────────────┤       ├──────────────────────┤
│ id (PK)      │       │ id (PK)      │       │ raw_hash (PK)        │
│ code         │       │ origin_iata  │       │ payload_json (JSONB) │
│ source_type  │       │ dest_iata    │       │ created_at           │
│ rate_limit   │       │ base_weight  │       └──────────┬───────────┘
└──────┬───────┘       └──────┬───────┘                  │
       │                      │                          │
       │                      │                          │
┌──────┴───────────────┐      │               ┌──────────┴───────────┐
│   collection_runs    │      │               │  fare_observations   │
├──────────────────────┤      │               ├──────────────────────┤
│ run_id (PK)          │      │               │ id (UUID / PK)       │
│ source_id (FK)       │      │               │ run_id (FK)          │
│ started_at           │      │               │ route_id (FK)        │
│ status               │      │               │ airline_iata         │
│ record_count         │      │               │ flight_number        │
└──────────────┬───────┘      │               │ departure_datetime   │
               │              │               │ booking_window       │
               │              │               │ advance_days         │
               └──────────────┼───────────────┤ base_fare            │
                              │               │ taxes                │
                              │               │ fees                 │
                              │               │ total_payable_fare   │
                              │               │ raw_hash (FK)        │
                              │               │ quality_status       │
                              │               │ is_comparable        │
                              │               └──────────────────────┘
```

### 2.1 Deduplication Strategy
When multiple sources report on the same flight:
- **Canonical Flight Key**: `(airline_iata, flight_number, origin_iata, destination_iata, departure_datetime)`
- If multiple records exist for the same canonical flight key in the same collection window, the system groups them and marks the primary carrier observation as canonical, tagging secondary OTA observations as cross-verification records.

### 2.2 Missing Data States
A missing fare is never silently deleted. It is recorded as:
- `AVAILABLE`: Valid comparable price.
- `SOLD_OUT`: Flight operated but zero seats in economy.
- `SOURCE_ERROR`: Scraper encountered HTTP 4xx/5xx or IP block.
- `TIMEOUT`: Playwright browser page load timed out.
- `PARSER_ERROR`: DOM structure changed; needs scraper adjustment.

---

## 3. Stage 2 Verification Checklist

- [ ] **Task 2.1: PostgreSQL & SQLAlchemy Models Definition**
  - Implement `apex/storage/models.py` with tables: `sources`, `routes`, `collection_runs`, `raw_payloads`, `fare_observations`.
  - Include dual-engine support (PostgreSQL for development, SQLite for fast in-memory unit tests).
  - *Verification command*: `python3 -m unittest tests/unit/test_storage_models.py`
- [ ] **Task 2.2: Database Migration & Schema Initializer**
  - Implement `apex/storage/migrations.py` with automated schema creation and seed data for the 5 standard routes and major airlines.
  - *Verification command*: `python3 -m unittest tests/unit/test_database_init.py`
- [ ] **Task 2.3: Raw-to-Normalized Ingestion Service**
  - Implement `apex/normalization/service.py` to accept `CollectorResult`, persist raw payloads by SHA-256 hash, validate records, and insert clean `FareObservation` rows.
  - *Verification command*: `python3 -m unittest tests/unit/test_normalization_service.py`
- [ ] **Task 2.4: Deduplication & Canonical Flight Resolution**
  - Implement `apex/normalization/dedup.py` resolving multi-source records into unified canonical flight entities.
  - *Verification command*: `python3 -m unittest tests/unit/test_dedup.py`
- [ ] **Task 2.5: Missing Data & Anomaly Status Tagging**
  - Ensure scraper errors and sold-out states produce explicit tracking rows with quality tags.
  - *Verification command*: `python3 -m unittest tests/unit/test_missing_data.py`

---

## 4. Exit Criteria for Stage 2

1. All checklist items marked `[x]`.
2. Clean database records can be queried: `"Select all valid comparable fares for DEL-BOM at T+15"`.
3. Every stored fare is linked to an exact raw payload hash for auditability.
