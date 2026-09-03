# Stage 3: Statistical & Airfare Index Engine

> **Stage Status**: `PENDING`  
> **Prerequisites**: [Stage 2: Cleaning & Storage](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-02-cleaning-storage.md) must be complete.  
> **Next Stage**: [Stage 4: Testing, Robustness & DGCA Validation](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-04-testing-robustness.md)

---

## 1. Stage Objective

Stage 3 transforms raw database observations into actionable economic metrics:
1. **Route-Level Price Aggregates**: Robust medians and trimmed means.
2. **Day-0 Baseline Formulation**: Compute and store baseline prices $P_{r,w,0}$ from the first comprehensive collection run.
3. **Route Airfare Index**: Calculate index values per route and per booking window.
4. **Weighted National Airfare Index (NAI)**: Synthesize route indices into a single composite national metric.
5. **Lead-Time Price Dynamics**: Produce the booking-window curve ($T+45 \to T+1$).
6. **Swappable Baseline Interface**: Allow seamless transition to DGCA monthly benchmark data without altering calculation logic.

---

## 2. Mathematical Methodology

### 2.1 Baseline Price ($P_{r,w,0}$)
As decided in design alignment:
- Prototype Baseline: Median total payable fare across comparable observations collected during Day 0 for each `(route, booking_window)`.
- Stored as configurable metadata in database table `index_baselines`.
- Managed via `BaselineProvider` abstraction to facilitate future swap with official DGCA reference numbers.

### 2.2 Route-Window Index ($I_{r,w,t}$)
For route $r$, booking window $w$, on observation date $t$:

$$I_{r,w,t} = \left( \frac{\tilde{P}_{r,w,t}}{P_{r,w,0}} \right) \times 100$$

Where $\tilde{P}_{r,w,t}$ is the median of valid, comparable fares for that cell.

### 2.3 Route Composite Index ($I_{r,t}$)
Aggregates booking windows on a route using window weights $\omega_w$:

$$I_{r,t} = \sum_{w \in W} \omega_w \cdot I_{r,w,t}$$

*Standard Window Weights*:
- T+1: $0.15$
- T+7: $0.25$
- T+15: $0.30$
- T+30: $0.20$
- T+45: $0.10$

### 2.4 National Airfare Index ($\text{NAI}_t$)
Aggregates all routes in the representative basket using route traffic weights $W_r$:

$$\text{NAI}_t = \sum_{r \in R} W_r \cdot I_{r,t}$$

*Route Basket Weights*:
- DEL-BOM: $0.35$
- DEL-BLR: $0.25$
- BOM-BLR: $0.20$
- DEL-CCU: $0.12$
- BLR-HYD: $0.08$

### 2.5 Lead-Time Curve
For each route, the engine computes price progression as departure approaches:
$$\text{Curve}_r = [P_{\text{T+45}}, P_{\text{T+30}}, P_{\text{T+15}}, P_{\text{T+7}}, P_{\text{T+1}}]$$
Yields the surge coefficient: $\frac{P_{\text{T+1}}}{P_{\text{T+45}}}$.

---

## 3. Stage 3 Verification Checklist

- [ ] **Task 3.1: Statistical Aggregator & Median Calculation**
  - Implement `apex/engine/aggregators.py` computing route-window medians, IQR, and trimmed means from database queries.
  - *Verification command*: `python3 -m unittest tests/unit/test_aggregators.py`
- [ ] **Task 3.2: Configurable Baseline Provider Abstraction**
  - Implement `apex/engine/baseline.py` with `BaselineProvider`, `DayZeroMedianBaselineProvider`, and `ConfigurableMetadataBaselineProvider`.
  - *Verification command*: `python3 -m unittest tests/unit/test_baseline_provider.py`
- [ ] **Task 3.3: Route-Level Index Engine**
  - Implement `apex/engine/route_index.py` calculating $I_{r,w,t}$ and composite $I_{r,t}$.
  - *Verification command*: `python3 -m unittest tests/unit/test_route_index.py`
- [ ] **Task 3.4: Weighted National Index Engine**
  - Implement `apex/engine/national_index.py` aggregating route indices by basket weights into $\text{NAI}_t$.
  - *Verification command*: `python3 -m unittest tests/unit/test_national_index.py`
- [ ] **Task 3.5: Lead-Time Curve Generator**
  - Implement `apex/engine/lead_time.py` generating trajectory curves and surge multipliers.
  - *Verification command*: `python3 -m unittest tests/unit/test_lead_time.py`
- [ ] **Task 3.6: Deterministic Math Test with Known Inputs**
  - Test synthetic inputs (e.g. ₹4,000 base, ₹5,000 current $\to$ exactly 125.0) verifying numerical reproducibility without floating-point drift.
  - *Verification command*: `python3 -m unittest tests/unit/test_engine_math.py`

---

## 4. Exit Criteria for Stage 3

1. All checklist items marked `[x]`.
2. Given a database state, running `apex.engine.compute_daily_index()` generates and records:
   - National Index (e.g. 127.3)
   - 5 Route Indices (e.g. DEL-BOM: 132.1)
   - 25 Route-Window Cells
   - Lead-time surge multipliers
3. Every output is 100% reproducible from historical database records.
