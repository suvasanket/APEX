# Stage 5: Advanced Intelligence & Trust Layer

> **Stage Status**: `PENDING`  
> **Prerequisites**: [Stage 4: Testing & Robustness](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-04-testing-robustness.md) must be complete.  
> **Next Stage**: [Stage 6: API & Demonstration Layer](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-06-api-dashboard.md)

---

## 1. Stage Objective

A raw index number is rarely convincing on its own. Stage 5 turns APEX into an enterprise-grade, defensible statistical system by layering:
1. **Confidence & Data Quality Scoring**: Transparent evaluation of data completeness and reliability.
2. **Full Data Provenance**: End-to-end lineage from index output back to the raw scraper byte hash.
3. **Anomaly Detection & Attribution**: Flagging fare surges and linking them to events (festivals, weather disruptions, capacity drops) without silently modifying raw data.
4. **Source Health Analytics**: Monitoring uptime, error rates, and response latency across all airline adapters.

---

## 2. Core Architecture

### 2.1 The Data Quality & Confidence Model
Every daily index calculation produces a companion `QualityReport`:

```text
QualityReport
├── overall_confidence_score: float (0.0 to 1.0)
├── dimensions
│   ├── coverage_score: float (routes & windows observed / expected)
│   ├── freshness_score: float (observation age relative to collection run)
│   ├── source_diversity_score: float (multi-carrier representation)
│   └── completeness_score: float (unbroken tax/fee itemization)
└── active_sources_health: dict[str, float]
```

### 2.2 Data Provenance Graph (Lineage Trace)
Given any `index_id`:
```text
National Airfare Index (127.4)
│
├── DEL-BOM Route Component (Weight: 0.35, Route Index: 132.1)
│   ├── T+15 Cell (Median Fare: ₹5,945)
│   │   ├── Observation #1: IndiGo 6E-2054, ₹5,800
│   │   │   └── Scraped: 2026-09-03 14:00 UTC | SHA256: 3a9f... | Raw Snapshot
│   │   └── Observation #2: Air India AI-805, ₹6,100
│   │       └── Scraped: 2026-09-03 14:05 UTC | SHA256: 7b1c... | Raw Snapshot
│   └── T+1 Cell ...
```

### 2.3 Anomaly Detection & Event Attribution
- **Detector**: Non-parametric rolling median & IQR bands. An observation is flagged `ANOMALY_HIGH` if:
  $$\text{Fare} > \text{Median}_{7d} + 2.5 \times \text{IQR}_{7d}$$
- **Event Associator**: Checks observation dates against a curated calendar of national holidays, festival peaks (Diwali, Chhath, Durga Puja), and cricket matches, proposing explanatory tags.

---

## 3. Stage 5 Verification Checklist

- [ ] **Task 5.1: Data Quality Scoring Engine**
  - Implement `apex/intelligence/quality.py` computing coverage, freshness, and completeness metrics.
  - *Verification command*: `python3 -m unittest tests/unit/test_quality_score.py`
- [ ] **Task 5.2: Composite Confidence Metric**
  - Implement `apex/intelligence/confidence.py` calculating overall score (e.g. 0.94) and degradation penalties when sources fail.
  - *Verification command*: `python3 -m unittest tests/unit/test_confidence_score.py`
- [ ] **Task 5.3: Provenance Drilldown Engine**
  - Implement `apex/intelligence/provenance.py` reconstructing the full lineage from an index row down to raw database hash references.
  - *Verification command*: `python3 -m unittest tests/unit/test_provenance.py`
- [ ] **Task 5.4: Anomaly Detector (IQR / Rolling Z-Score)**
  - Implement `apex/intelligence/anomaly.py` to flag price spikes without dropping rows from the database.
  - *Verification command*: `python3 -m unittest tests/unit/test_anomaly_detector.py`
- [ ] **Task 5.5: Event Intelligence & Attribution Tagger**
  - Implement `apex/intelligence/events.py` mapping route surge dates to major calendar events.
  - *Verification command*: `python3 -m unittest tests/unit/test_event_intelligence.py`
- [ ] **Task 5.6: Collector Health Monitor**
  - Implement `apex/intelligence/source_health.py` tracking rolling success rates and latencies per airline adapter.
  - *Verification command*: `python3 -m unittest tests/unit/test_source_health.py`

---

## 4. Exit Criteria for Stage 5

1. All checklist items marked `[x]`.
2. Every generated index output is packaged with a confidence score and data quality breakdown.
3. Any point on the index curve can be drilled down to raw observation hashes in $< 50\text{ms}$.
