# Stage 0: Measurement & Data Contract Specification

> **Stage Status**: `ACTIVE`  
> **Prerequisites**: None  
> **Next Stage**: [Stage 1: Data Acquisition Engine](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-01-data-acquisition.md)

---

## 1. Stage Objective

Before scraping any website, we must unequivocally answer:
> *"When our database says ₹4,532 for DEL → BOM at T+15, what exact physical and economic unit does that ₹4,532 represent?"*

Stage 0 creates the **ironclad data contract** between the scrapers and all downstream systems (storage, normalization, statistical engine, and API). The scraper does not need to know about statistical indices; it only needs to produce valid `FareObservation` records.

---

## 2. Formal Specifications

### 2.1 The Canonical `FareObservation` Contract
Every collector must emit observations conforming to this structure:

```text
FareObservation
├── observation_id: UUID / string
├── collection_timestamp: ISO-8601 UTC
├── source_info
│   ├── source_code: string ("indigo_direct", "airindia_direct", etc.)
│   ├── source_type: string ("airline_direct" | "ota")
│   └── collection_run_id: string
├── flight_identity
│   ├── airline_iata: string (e.g. "6E", "AI", "QP", "SG")
│   ├── flight_number: string (e.g. "6E-2054")
│   ├── origin_iata: string (3 letters, e.g. "DEL")
│   ├── destination_iata: string (3 letters, e.g. "BOM")
│   ├── departure_datetime: ISO-8601 UTC
│   ├── arrival_datetime: ISO-8601 UTC
│   ├── stops: int (0 for non-stop)
│   └── is_nonstop: bool
├── booking_dimension
│   ├── booking_window: enum ("T+1", "T+7", "T+15", "T+30", "T+45")
│   ├── advance_days: int
│   ├── cabin_class: string ("economy")
│   └── fare_family: string (e.g. "Saver", "Standard", "Flexi")
├── fare_breakdown
│   ├── currency: string ("INR")
│   ├── base_fare: Decimal / float (>= 0)
│   ├── taxes: Decimal / float (>= 0)
│   ├── fees: Decimal / float (>= 0)
│   └── total_payable_fare: Decimal / float (base_fare + taxes + fees)
├── raw_audit
│   ├── raw_payload: string / JSON snippet
│   └── raw_hash: string (SHA-256 of raw response)
└── status: enum ("AVAILABLE", "SOLD_OUT", "UNAVAILABLE")
```

### 2.2 Standard 5-Route Basket
The initial prototype index measures these 5 representative high-density domestic routes:

| Route ID | Origin | Destination | Direction | Default Weight | Description |
|---|---|---|---|---|---|
| `DEL-BOM` | DEL (Delhi) | BOM (Mumbai) | One-way | 0.35 | Metro-to-Metro premier commercial corridor |
| `DEL-BLR` | DEL (Delhi) | BLR (Bengaluru) | One-way | 0.25 | Metro-to-Tech hub corridor |
| `BOM-BLR` | BOM (Mumbai) | BLR (Bengaluru) | One-way | 0.20 | Financial-to-Tech hub corridor |
| `DEL-CCU` | DEL (Delhi) | CCU (Kolkata) | One-way | 0.12 | North-to-East regional trunk route |
| `BLR-HYD` | BLR (Bengaluru) | HYD (Hyderabad) | One-way | 0.08 | Southern interstate short-haul trunk route |

### 2.3 Standard 5 Booking Windows
Observation dates are calculated relative to collection date $T_{coll}$:

| Window | Offset | Rationale |
|---|---|---|
| **T+1** | $T_{coll} + 1\text{ day}$ | Last-minute distress/surge demand pricing |
| **T+7** | $T_{coll} + 7\text{ days}$ | Short-term business/urgent travel pricing |
| **T+15** | $T_{coll} + 15\text{ days}$ | Typical domestic leisure/planned travel pricing |
| **T+30** | $T_{coll} + 30\text{ days}$ | Medium-range advance purchase baseline |
| **T+45** | $T_{coll} + 45\text{ days}$ | Long-range advance booking anchor |

### 2.4 Comparable Flight Standard
To avoid comparing apples to oranges:
- **Cabin**: Economy only.
- **Flight Type**: Non-stop flights only for V1.
- **Currency**: INR only.
- **Fare Basis**: Standard lowest available public adult fare. Excludes corporate fares, student discounts, and optional add-ons (meals, seat assignment, extra baggage).
- **Formula**:
  $$\text{Total Payable Fare} = \text{Base Fare} + \text{Taxes} + \text{Mandatory User Development / Airport Fees}$$

### 2.5 Raw vs Normalized Distinction
1. **Raw Tier**: Preserves exact strings and numbers returned by the scraper (even if inconsistent or partial).
2. **Normalized Tier**: The deterministic, typed, validated `FareObservation` record.

---

## 3. Stage 0 Verification Checklist

All items below must be implemented and verified before proceeding to Stage 1.

- [ ] **Task 0.1: Define Core Pydantic Domain Models**
  - Implement `apex/models/fare.py` with `FareObservation`, `FlightIdentity`, `FareBreakdown`, and validation rules (no negative fares, currency == "INR", departure before arrival).
  - *Verification command*: `python3 -m unittest tests/unit/test_fare_spec.py`
- [ ] **Task 0.2: Export Canonical JSONSchema**
  - Generate `docs/schemas/fare_observation.json` from the Pydantic model for language-agnostic scraper validation.
  - *Verification command*: `python3 -c "import json; json.load(open('docs/schemas/fare_observation.json'))"`
- [ ] **Task 0.3: Route Basket Specification**
  - Create `docs/methodology/route_basket.json` containing the 5 routes, IATA codes, and initial weights totaling 1.0.
  - *Verification command*: `python3 -c "import json; r=json.load(open('docs/methodology/route_basket.json')); assert len(r)==5 and abs(sum(x['weight'] for x in r)-1.0)<1e-6"`
- [ ] **Task 0.4: Booking Windows Specification**
  - Create `docs/methodology/booking_windows.json` containing the 5 windows (T+1, T+7, T+15, T+30, T+45) and offset calculator helper.
  - *Verification command*: `python3 -c "import json; w=json.load(open('docs/methodology/booking_windows.json')); assert len(w)==5"`
- [ ] **Task 0.5: Fixture Test Suite for Contract Compliance**
  - Write sample valid and invalid JSON fixtures in `tests/fixtures/observations/`.
  - Validate that invalid observations (negative fare, wrong currency, missing total) raise validation errors.
  - *Verification command*: `python3 -m unittest tests/unit/test_fare_spec.py`

---

## 4. Exit Criteria for Stage 0

1. All checklist items marked `[x]`.
2. Running `python3 -m unittest discover tests/unit` exits with code 0.
3. A scraper developer can inspect `docs/schemas/fare_observation.json` and build a collector without asking any questions about data format.
