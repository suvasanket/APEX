# Stage 1: Data Acquisition Engine

> **Stage Status**: `PENDING`  
> **Prerequisites**: [Stage 0: Measurement & Data Contract](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-00-measurement-spec.md) must be complete.  
> **Next Stage**: [Stage 2: Cleaning, Normalization & Storage](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-02-cleaning-storage.md)

---

## 1. Stage Objective

Stage 1 builds the autonomous ingestion layer. Following our agreed strategy:
- **Acquisition Mechanism**: Strictly web scraping.
- **Priority**: Major airline carrier websites first (IndiGo 6E first via Playwright/network interception), followed by other carriers (Air India, Akasa) and OTAs subsequently.
- **Independence**: Scrapers only output `FareObservation` records. Downstream systems never care which scraper produced the record.

---

## 2. Architecture & Design

### 2.1 The Collector Interface
All scrapers must implement an abstract base class:

```python
class BaseCollector(ABC):
    @abstractmethod
    async def collect_route(
        self, origin: str, destination: str, travel_date: date, window_label: str
    ) -> CollectorResult:
        """Collect observations for a specific route and travel date."""
        ...
```

Where `CollectorResult` encapsulates:
- `observations: list[FareObservation]`
- `raw_payload: str` (raw JSON/HTML snippet)
- `raw_hash: str` (SHA-256 hash of payload)
- `execution_meta: dict` (duration_ms, http_status, error_log)

### 2.2 Phased Ingestion Milestones
1. **Milestone 1.1 (The Atomic Milestone)**:
   - Target: IndiGo (`goindigo.in`)
   - Scope: DEL → BOM, T+15 (single flight search)
   - Method: Headless Playwright browser with background network XHR/fetch request interception.
   - Result: 1 valid `FareObservation` with complete price breakdown and SHA-256 hash.
2. **Milestone 1.2 (Route × Window Matrix Expansion)**:
   - Expand IndiGo collector to the full matrix: 5 routes × 5 booking windows = 25 collection tasks.
3. **Milestone 1.3 (Multi-Carrier & OTA Stubs)**:
   - Implement `AirIndiaCollector` and `AkasaCollector` skeletons adhering to `BaseCollector`.
   - Prepare OTA aggregator adapter for rapid multi-carrier search.

### 2.3 Compliance, Ethical Scraping & Circuit Breaker
Each collector must adhere to configurable safety profiles:
- `min_delay_seconds`: Random delay with jitter between requests.
- `max_requests_per_minute`: Strict throttle per domain.
- `circuit_breaker`: If 3 consecutive failures or rate-limit blocks occur, trips open for 15 minutes to protect target servers and avoid IP bans.
- `user_agent`: Standard respectful identification headers.

---

## 3. Stage 1 Verification Checklist

- [ ] **Task 1.1: Base Collector Interface & Data Types**
  - Implement `apex/collectors/base.py` with `BaseCollector`, `CollectorResult`, and retry/circuit-breaker decorators.
  - *Verification command*: `python3 -m unittest tests/unit/test_collector_base.py`
- [ ] **Task 1.2: Mock / Fixture Collector for Offline Pipeline Testing**
  - Implement `apex/collectors/mock.py` that emits synthetic `FareObservation` objects from static recorded fixtures. Enables 100% offline verification of the pipeline.
  - *Verification command*: `python3 -m unittest tests/unit/test_mock_collector.py`
- [ ] **Task 1.3: IndiGo Playwright Network Interceptor Adapter**
  - Implement `apex/collectors/indigo.py`. Intercepts flight search API responses, extracts fare families, flight numbers, base fare, taxes, and fees.
  - *Verification command*: `python3 -m unittest tests/unit/test_indigo_parser.py`
- [ ] **Task 1.4: Raw Payload Storage & Hashing**
  - Implement payload hashing utility (`apex/collectors/audit.py`) computing SHA-256 digests on raw response strings.
  - *Verification command*: `python3 -m unittest tests/unit/test_raw_audit.py`
- [ ] **Task 1.5: End-to-End Live Single Route Spike**
  - Execute 1 live collection run on DEL → BOM at T+15 using IndiGo collector, producing valid JSON output.
  - *Verification command*: `python3 -m apex.collectors.cli --source indigo --route DEL-BOM --window T+15 --dry-run`

---

## 4. Exit Criteria for Stage 1

1. All checklist items marked `[x]`.
2. IndiGo collector reliably extracts structured `FareObservation` records matching the Stage 0 schema.
3. Raw JSON response and SHA-256 hash are recorded for every observation.
