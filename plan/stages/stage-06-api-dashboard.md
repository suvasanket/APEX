# Stage 6: API, Presentation Layer & Demonstration Polish

> **Stage Status**: `PENDING`  
> **Prerequisites**: [Stage 5: Intelligence & Trust](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-05-intelligence-trust.md) must be complete.  
> **Next Stage**: Project Completion & Production Readiness

---

## 1. Stage Objective

Stage 6 exposes the entire APEX engine to consumers (frontend dashboards, regulatory inspectors, airline analysts, and competition evaluators).
It delivers:
1. **High-Performance FastAPI Service**: Production-ready, typed endpoints with automatic OpenAPI documentation.
2. **Provenance & Audit Endpoints**: Interactive endpoints showing why an index number is what it is.
3. **Lead-Time Visualization Data**: Rich JSON structures optimized for lead-time charts and price curves.
4. **Validation Demonstration Suite**: Ready-to-demo endpoints showcasing DGCA alignment metrics (MAPE, correlation).

---

## 2. API Endpoint Specification

All endpoints are versioned under `/api/v1`:

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/index/current` | Returns today's National Airfare Index, day-over-day $\Delta$, and confidence score |
| `GET` | `/api/v1/index/history` | Historical time series for national and individual route indices |
| `GET` | `/api/v1/routes` | Active route basket with current weights and route indices |
| `GET` | `/api/v1/routes/{route_id}/lead-time` | Lead-time price progression ($T+45 \to T+1$) and surge multipliers |
| `GET` | `/api/v1/provenance/{index_id}` | Full audit tree from index down to raw scraper observation SHA-256 hashes |
| `GET` | `/api/v1/quality` | Current data quality scores (coverage, freshness, completeness, collector health) |
| `GET` | `/api/v1/validation/dgca` | 30-day DGCA backtest metrics (MAE, MAPE, RMSE, Pearson $r$) |
| `GET` | `/api/v1/health` | Service and database health check |

---

## 3. Stage 6 Verification Checklist

- [ ] **Task 6.1: FastAPI Application Structure & Router Setup**
  - Implement `apex/api/app.py` with CORS, error handlers, and router registration.
  - *Verification command*: `python3 -m unittest tests/unit/test_api_base.py`
- [ ] **Task 6.2: Core Index Endpoints**
  - Implement `apex/api/routes/index.py` for `/api/v1/index/current` and `/api/v1/index/history`.
  - *Verification command*: `python3 -m unittest tests/unit/test_api_index.py`
- [ ] **Task 6.3: Route & Lead-Time Endpoints**
  - Implement `apex/api/routes/routes.py` for `/api/v1/routes` and `/api/v1/routes/{route_id}/lead-time`.
  - *Verification command*: `python3 -m unittest tests/unit/test_api_routes.py`
- [ ] **Task 6.4: Audit Provenance Endpoint**
  - Implement `apex/api/routes/provenance.py` for `/api/v1/provenance/{index_id}`.
  - *Verification command*: `python3 -m unittest tests/unit/test_api_provenance.py`
- [ ] **Task 6.5: Quality & DGCA Validation Endpoints**
  - Implement `apex/api/routes/quality.py` and `apex/api/routes/validation.py`.
  - *Verification command*: `python3 -m unittest tests/unit/test_api_quality_validation.py`
- [ ] **Task 6.6: Interactive OpenAPI Documentation & Smoke Test**
  - Verify that FastAPI server boots and OpenAPI schema (`/openapi.json`) validates with all endpoints documented.
  - *Verification command*: `python3 -m unittest tests/integration/test_api_smoke.py`
- [ ] **Task 6.7: Demo / PPT Summary Export Utility**
  - Implement `apex/api/export.py` generating a clean markdown/JSON summary of the system status, index values, and DGCA metrics for presentations.
  - *Verification command*: `python3 -m apex.api.export --format markdown --output demo_summary.md`

---

## 4. Exit Criteria for Stage 6

1. All checklist items marked `[x]`.
2. Running the API server allows complete navigation via Swagger UI (`/docs`).
3. Demonstration export report can be produced in one command for hackathon judges/stakeholders.
