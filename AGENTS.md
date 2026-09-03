# APEX AGENT PROTOCOL

## 1. STAGE ISOLATION (STRICT)
- Read `plan/CURRENT_STAGE.md` -> get active stage file.
- Open ONLY active stage spec (`plan/stages/stage-*.md`).
- FORBIDDEN: Reading other stages. No jumping ahead (e.g. no scrapers in Stage 0, no index math in Stage 1).

## 2. CHECKLIST & VERIFICATION
- Work atomic: 1 item `- [ ]` at a time.
- Run verify command. Exit code 0 REQUIRED before marking `- [x]`.
- Stage gate: All items `- [x]` + full test suite exit 0 -> notify user -> advance `plan/CURRENT_STAGE.md`.

## 3. ARCHITECTURE CONTRACTS
- Pipeline: Source -> Collector -> FareObservation -> Normalizer -> PostgreSQL -> IndexEngine -> API.
- Scraper: Emit `FareObservation` only. Zero index math knowledge.
- Engine: Read clean DB only. Zero scraper/HTTP knowledge.
- Provenance: Store raw payload + SHA-256 hash. Never mutate raw.
- Offline-first: 100% testable via `tests/fixtures/`. Zero live network in unit tests.
- Safety: Rate limits, backoff, circuit breaker.

## 4. ENVIRONMENT (ZERO UNAPPROVED INSTALLS)
- NO `pip install`, NO `brew install` Ask if required.
- Any pip install always in local project scope NO global.
- Stack: Python 3.11+, local PostgreSQL, Playwright async, FastAPI, Pydantic v2.

## 5. CODEBASE INDEX PROTOCOL (`CODEBASE_INDEX.md`)
- Scope: Codebase structure ONLY (files, symbols, tables, fixtures). ZERO plan/roadmap data.
- READ: Before writing code -> check existing classes/helpers. Prevent duplication.
- WRITE: Auto-update on new module, public class/function, DB model, or fixture.
- DO NOT WRITE: Internal logic edits, bug fixes, comments. Max 1 line per entry.

## 6. TURN EXECUTION LOOP
1. `plan/CURRENT_STAGE.md` -> active stage file.
2. Read active stage file ONLY.
3. Check `CODEBASE_INDEX.md` for existing symbols.
4. Implement 1 item `- [ ]`.
5. Update `CODEBASE_INDEX.md` if new file/symbol added.
6. Run verify command. Exit 0 -> mark `- [x]`.
7. Repeat or report stage gate.
