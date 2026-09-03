# Stage 4: Testing, Robustness & DGCA Validation

> **Stage Status**: `PENDING`  
> **Prerequisites**: [Stage 3: Statistical Engine](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-03-index-engine.md) must be complete.  
> **Next Stage**: [Stage 5: Advanced Intelligence & Trust Layer](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-05-intelligence-trust.md)

---

## 1. Stage Objective

Stage 4 answers the most critical question:
> **"Can regulators, airlines, and the public trust the numbers APEX produces?"**

This stage validates end-to-end data integrity, tests edge/failure cases under chaos conditions, and implements a formal backtesting module against official DGCA (Directorate General of Civil Aviation) benchmark data.

---

## 2. Core Validation Pillars

### 2.1 Synthetic Fixture & Mathematical Truth Suite
- Test suite with mathematical invariants:
  - Uniform shift: If all fares increase by 15%, the National Index must increase by exactly 15%.
  - Route weight sensitivity: A 10% increase on DEL-BOM (35% weight) must cause a 3.5-point increase in the national index.
  - Invariance under duplicates: Duplicate scraped records must not alter the median.

### 2.2 Fault Injection & Chaos Testing
Intentionally feed the pipeline malicious/corrupt records:
- Negative base fare or negative taxes.
- Missing mandatory airport fees.
- Erroneous 10x multiplier fares (e.g. ₹99,999 due to currency formatting glitch).
- Scraper timeouts and empty responses.
- Total carrier outage (e.g. IndiGo scraper unavailable $\to$ system degrades gracefully, logs quality event, recalculates index with carrier drop note, never crashes).

### 2.3 DGCA 30-Day Benchmark Validation Suite
Formal evaluation against publicly available DGCA monthly average route fare benchmarks:

$$\text{MAE} = \frac{1}{N}\sum |P_{\text{apex}} - P_{\text{dgca}}|$$

$$\text{MAPE} = \frac{1}{N}\sum \left| \frac{P_{\text{apex}} - P_{\text{dgca}}}{P_{\text{dgca}}} \right| \times 100\%$$

$$\text{RMSE} = \sqrt{\frac{1}{N}\sum (P_{\text{apex}} - P_{\text{dgca}})^2}$$

$$\text{Pearson } r = \frac{\sum (P_{\text{apex}} - \bar{P}_{\text{apex}})(P_{\text{dgca}} - \bar{P}_{\text{dgca}})}{\sigma_{\text{apex}}\sigma_{\text{dgca}}}$$

$$\text{Directional Agreement} = \frac{\text{matching sign changes}}{\text{total periods}} \times 100\%$$

---

## 3. Stage 4 Verification Checklist

- [ ] **Task 4.1: Synthetic Test Data Suite**
  - Implement `tests/synthetic/test_invariants.py` asserting mathematical properties (scale invariance, weight sensitivity, monotonicity).
  - *Verification command*: `python3 -m unittest tests/synthetic/test_invariants.py`
- [ ] **Task 4.2: Fault Injection & Malformed Data Suite**
  - Implement `tests/unit/test_fault_injection.py` testing negative fares, extreme outliers, missing fields, and corrupted payloads.
  - *Verification command*: `python3 -m unittest tests/unit/test_fault_injection.py`
- [ ] **Task 4.3: Source Failure & Graceful Degradation Test**
  - Simulate a complete outage of the IndiGo scraper; verify that `compute_daily_index()` runs on remaining available sources with an updated confidence flag.
  - *Verification command*: `python3 -m unittest tests/unit/test_source_resilience.py`
- [ ] **Task 4.4: DGCA Benchmark Parser & Loader**
  - Implement `apex/validation/dgca_loader.py` to ingest public DGCA monthly route fare tables from CSV/JSON.
  - *Verification command*: `python3 -m unittest tests/unit/test_dgca_loader.py`
- [ ] **Task 4.5: Validation Metrics Engine**
  - Implement `apex/validation/metrics.py` computing MAE, MAPE, RMSE, Pearson correlation, and directional concordance.
  - *Verification command*: `python3 -m unittest tests/unit/test_validation_metrics.py`
- [ ] **Task 4.6: Run 30-Day Simulated Backtest**
  - Execute 30-day synthetic backtest against DGCA baseline fixtures and verify MAPE $< 5\%$ and Pearson $r > 0.90$.
  - *Verification command*: `python3 -m apex.validation.run_backtest --fixture tests/fixtures/dgca_30day.json`

---

## 4. Exit Criteria for Stage 4

1. All checklist items marked `[x]`.
2. All mathematical invariants verified with zero rounding errors.
3. System handles missing/corrupt data without unhandled exceptions.
4. DGCA validation report generated with MAE, MAPE, RMSE, and correlation scores.
