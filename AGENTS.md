# APEX Agent Operational Protocol & Guidelines

Welcome to **APEX (Airfare Pricing & Economic Index Engine)**. This document is the mandatory protocol for any autonomous or pair-programming AI agent operating in this repository.

---

## 1. Golden Rule: Stage Isolation (Do Not Read All Stages)

To avoid context window bloat, hallucinations, and premature implementation:

1. **Check the Active Stage First**:
   - Inspect [`plan/CURRENT_STAGE.md`](file:///Users/suvasanketrout/Developer/APEX/plan/CURRENT_STAGE.md) to identify the currently active stage.
2. **Read ONLY the Active Stage Specification**:
   - Open and read **only** the designated stage file in `plan/stages/` (e.g., [`plan/stages/stage-00-measurement-spec.md`](file:///Users/suvasanketrout/Developer/APEX/plan/stages/stage-00-measurement-spec.md)).
   - **DO NOT** read any other stage specifications in `plan/stages/` unless:
     - You are explicitly asked by the user to perform cross-stage planning, OR
     - You need to verify an interface contract defined by an immediately preceding completed stage.
3. **Never Jump Ahead**:
   - If working on Stage 0, do not write scrapers (Stage 1).
   - If working on Stage 1, do not write index math (Stage 3).
   - Focus exclusively on fulfilling the checklist of the active stage.

---

## 2. Stage Execution & Checklist Protocol

Every stage specification in `plan/stages/` contains a markdown checklist:

```markdown
- [ ] Task description with explicit verification command
```

When executing tasks:
- **Work Atomically**: Implement one checklist item at a time.
- **Verify Before Checking**: Run the verification command specified for that task. **NEVER** mark a checkbox `[x]` until its automated test or verification script succeeds with exit code 0.
- **Update Checklist Progress**: Edit the active stage document to check off completed items as you progress.
- **Stage Completion Gate**: A stage is only complete when:
  1. All items in the stage's checklist are marked `[x]`.
  2. The full stage verification suite passes.
  3. The user or orchestrator is notified.
  4. Only then may `plan/CURRENT_STAGE.md` and `plan/ROADMAP.md` be updated to point to the next stage.

---

## 3. Core Architectural Contracts

1. **Decoupled Pipeline**:
   ```text
   Website/OTA → Collector → FareObservation → Normalization → Quality Control → PostgreSQL → Index Engine → API / Dashboard
   ```
   - Scrapers **only** know how to parse pages into raw data and emit `FareObservation` objects. Scrapers **must never** know about statistical indexes, weights, or national aggregates.
   - The Statistical Engine **only** reads validated, normalized database records. It **must never** know about HTTP headers, cookies, or Playwright selectors.

2. **Dual Data Tier (RAW vs NORMALIZED)**:
   - Never overwrite or discard raw scraper responses. Always store the raw payload (or snippet) and its SHA-256 hash alongside the normalized observation for audit provenance.
   - If normalization rules change, historical raw data must be re-processable.

3. **Offline & Synthetic Testability**:
   - All modules (normalizer, storage, statistical engine, lead-time analyzer) must be 100% testable using offline synthetic fixtures (`tests/fixtures/`) without requiring internet access or live airline scraping.

4. **Safety & Ethical Scraping**:
   - Every scraper adapter must implement rate limiting, backoff, and circuit breakers. Respect `robots.txt` and anti-abuse policies.

---

## 4. Environment & Package Management Rules

- **No Unauthorized Installations**:
  - Do NOT execute `pip install` or `brew install` without checking user instructions.
  - Maintain dependencies cleanly in `pyproject.toml` or `requirements.txt`.
- **Target Stack**:
  - Python: 3.11+ / 3.12 (modern typing, Pydantic v2, async).
  - Database: Local PostgreSQL (or SQLite fallback for offline unit tests).
  - Browser Automation: Playwright Python (async).
  - Web Framework: FastAPI + Uvicorn.
  - Data / Math: Pandas / NumPy for statistical validation.

---

## 5. Repository Layout Convention

```text
APEX/
├── AGENTS.md                  # This file (mandatory agent protocol)
├── plan/                      # Roadmap and active stage documents
│   ├── ROADMAP.md             # High-level stages overview & status
│   ├── CURRENT_STAGE.md       # Pointer to active stage
│   └── stages/                # Individual stage specs & checklists
│       ├── stage-00-measurement-spec.md
│       ├── stage-01-data-acquisition.md
│       ├── stage-02-cleaning-storage.md
│       ├── stage-03-index-engine.md
│       ├── stage-04-testing-robustness.md
│       ├── stage-05-intelligence-trust.md
│       └── stage-06-api-dashboard.md
├── apex/                      # Main Python package
│   ├── collectors/            # Scraper adapters (IndiGo, Air India, etc.)
│   ├── models/                # Core domain schemas (FareObservation, Route, Flight)
│   ├── normalization/         # Cleaning, deduplication, fare breakdown
│   ├── storage/               # PostgreSQL / SQLAlchemy models & repositories
│   ├── engine/                # Statistical math, Day-0 baseline, national index
│   ├── intelligence/          # Quality scores, confidence, anomaly flags
│   └── api/                   # FastAPI endpoints & routes
├── docs/                      # Formal methodology and specs
│   ├── methodology.md
│   └── schemas/
├── tests/                     # Unit, integration, and synthetic tests
│   ├── fixtures/              # Offline JSON / HTML fixtures
│   ├── unit/
│   └── integration/
└── pyproject.toml
```

---

## 6. How to Start a Turn as an Agent

1. Check [`plan/CURRENT_STAGE.md`](file:///Users/suvasanketrout/Developer/APEX/plan/CURRENT_STAGE.md).
2. Open the file indicated.
3. Review the first unchecked item `- [ ]`.
4. Implement the required code/documentation.
5. Run the verification command.
6. Check off the item `- [x]`.
7. Proceed to the next item or report completion.
