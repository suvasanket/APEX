# The development roadmap

```text
STAGE 0
Define exactly what we're measuring
↓
STAGE 1
Build the data acquisition system
↓
STAGE 2
Clean, normalize & store the data
↓
STAGE 3
Build the statistical/index engine
↓
STAGE 4
Test, validate & break the system
↓
STAGE 5
Advanced intelligence & trust layer
↓
STAGE 6
API + dashboard + hackathon polish
```

And importantly:

> **Do not start Stage 1 until Stage 0 is sufficiently defined.**

---

# STAGE 0 — Define the measurement

### Goal

Before writing a serious scraper, define exactly what a single piece of data means.

Think of this stage as answering:

> "When my database says ₹4,532 for DEL → BOM, what exactly does that ₹4,532 represent?"

---

## 0.1 Define a fare observation

Create the canonical object:

```text
FareObservation
│
├── source
├── airline
├── origin
├── destination
├── flight
├── departure date/time
├── collection timestamp
│
├── booking window
├── cabin
├── fare family
├── stops
│
├── base fare
├── taxes
├── fees
├── total fare
│
├── availability
└── metadata
```

This becomes the **contract between your scraper and everything else**.

Your scraper doesn't need to know anything about indexes.

It just has to produce valid `FareObservation`s.

---

## 0.2 Define the initial route basket

For V1, exactly what you suggested:

```text
5 routes
```

I would use:

```text
DEL → BOM
DEL → BLR
BOM → BLR
DEL → CCU
BLR → HYD
```

These are explicitly among the example representative routes in the problem statement.

Later:

```text
5 routes
↓
Top 20
↓
Top 50
↓
Pan-India
```

---

## 0.3 Define booking windows

Exactly:

```text
T+1
T+7
T+15
T+30
T+45
```

For example, if today is September 1:

```text
T+1  → Sep 2
T+7  → Sep 8
T+15 → Sep 16
T+30 → Oct 1
T+45 → Oct 16
```

This is critical because:

> ₹8,000 tomorrow and ₹4,000 45 days from now are not contradictory observations. They're different booking windows.

---

## 0.4 Define your "comparable flight"

For the first version, I'd make it:

```text
Domestic
Economy
Non-stop
Available
INR
Standard/lowest comparable fare
```

Then later we can make the specification more sophisticated.

---

## 0.5 Define exactly what "price" means

I'd start with:

```text
total_payable_fare
=
base_fare
+
taxes
+
mandatory_fees
```

Do not complicate this initially with optional baggage, seat selection, meals, etc.

But **store those fields when available** so you don't have to redesign the schema later.

---

## 0.6 Define the raw vs normalized distinction

This is extremely important.

Your database should contain both:

```text
RAW
What the website actually returned
```

and

```text
NORMALIZED
What our system decided the comparable price is
```

For example:

```text
RAW
Base: ₹3500
Tax: ₹600
Fee: ₹100

NORMALIZED
Total: ₹4200
```

Never throw away the raw information.

This gives us auditability later.

---

## Stage 0 deliverables

You should finish with:

```text
/docs
methodology.md
fare-observation-spec.md
route-basket.md
booking-windows.md
```

And:

```text
schemas/fare_observation.json
```

### Stage 0 is complete when:

You can hand the specification to the agent and say:

> "Write a scraper that outputs this exact object."

No ambiguity.

---

# STAGE 1 — Data acquisition

Now we actually touch the websites.

This is the stage you originally thought should come first, and you're right that it's one of the largest pieces.

---

# The architecture

Don't create:

```text
indigo_scraper.py
airindia_scraper.py
random_scraper.py
```

Create a common interface.

```text
Collector
│
├── IndigoAdapter
├── AirIndiaAdapter
├── AirIndiaExpressAdapter
├── AkasaAdapter
├── SpiceJetAdapter
│
└── OTA adapters
```

Each adapter must output:

```text
FareObservation[]
```

Nothing downstream should care **where** the data came from.

---

# 1.1 Build one source first

Don't start with all five airlines.

Start with:

```text
1 airline
↓
1 route
↓
1 booking window
↓
1 successful observation
```

Your first milestone is literally:

```text
DEL → BOM
T+15
IndiGo
₹xxxx
```

coming out as structured JSON.

---

# 1.2 Then expand

```text
1 source
↓
5 routes
↓
5 booking windows
↓
2 sources
↓
5 airlines
↓
OTAs
```

This prevents debugging hell.

---

# 1.3 Store raw responses

Every collection event should have something like:

```text
collection_run
------------------
run_id
source
started_at
completed_at
status
duration
records_found
error
```

And ideally:

```text
raw_payload
raw_hash
```

Do not keep enormous HTML forever, but during development it's incredibly useful.

---

# 1.4 Dynamic collection frequency

Yes — **absolutely make it dynamic.**

Don't hardcode:

    ```python
run_every_1_hour()
    ```

    Instead make the scheduler data-driven.

    For example:

    ```text
    collection_profiles
    -------------------------
    profile_id
    route_id
    source_id
    booking_window
    interval_seconds
    priority
    enabled
    next_run_at
    ```

    Then you can have:

    ```text
    Normal route:
    every 6 hours

    High-interest route:
    every 1 hour

    Before major event:
    every 15 minutes
    ```

    without changing your code.

    The scheduler simply asks:

    > "What needs collecting now?"

    This is much better.

    ---

# 1.5 Collection engine

    For V1 I'd use:

    ```text
    Python
    Playwright
    asyncio
    PostgreSQL
    ```

    And a lightweight scheduler.

    Don't introduce Kafka/Kubernetes/etc.

    You don't need them.

    Later, if scale requires it:

    ```text
    Scheduler
    ↓
    Queue
    ↓
    Workers
    ```

    ---

# 1.6 Important safety/compliance design

    Since the SIH statement explicitly calls for compliance with robots.txt, terms, rate limits and ethical collection, treat that as a **first-class configuration**, not an afterthought.

    Each source should have:

    ```text
    max_requests/min
    concurrency
    retry_limit
    timeout
    cooldown
    ```

    If a source starts failing:

    ```text
    failure rate ↑
    ↓
    circuit breaker
    ↓
    temporarily stop source
    ```

    Don't build the project around bypassing anti-bot protections.

    ---

# Stage 1 deliverable

    At the end:

    ```text
    5 routes
    ×
    5 booking windows
    ×
    multiple sources
    ```

    should be returning structured observations.

    Not necessarily millions of records.

    You just need **real, trustworthy observations**.

    ---

# STAGE 2 — Data synthesis + storage

    Now we take the messy collected information and turn it into something usable.

    This is where your original "Stage 2" idea is correct.

    ---

# 2.1 Recommended database

    I strongly recommend:

## PostgreSQL

    Not MongoDB.

    Not SQLite as the final system.

    Not a spreadsheet.

    Postgres gives you:

    * relational integrity
    * JSONB for raw/source-specific information
    * good indexing
    * aggregations
    * time-series-friendly queries
    * strong transaction guarantees
    * easy API integration

    And it is widely understood by future developers.

    For a free hosted version, **Neon is particularly attractive for the prototype**: its current free plan provides PostgreSQL, 0.5 GB storage per project, 50 CU-hours/month and 5 GB monthly egress. ([Neon][1])

Another option is Supabase, which also provides PostgreSQL, but its current free database quota is 500 MB before read-only behavior kicks in. ([Supabase][2])

    So for this project I'd lean:

    ```text
    Development
    MacBook

    Database
    Neon PostgreSQL

    Scraping/production worker
    Local initially
    ↓
    Oracle Cloud Always Free later
    ```

    Oracle currently offers Always Free Ampere A1 compute; the published allowance is enough for a small 2-OCPU/12-GB configuration, subject to regional capacity. ([Oracle Documentation][3])

    That is a very nice fit for Playwright workers.

    ---

# 2.2 Database structure

    I'd use something approximately like:

    ```text
    sources
    airports
    airlines
    routes
    flights
    fare_observations
    collection_runs
    quality_events
    index_values
    index_weights
    benchmarks
    ```

    The central table is:

    ```text
    fare_observations
    ```

    Conceptually:

    ```text
    id
    source_id
    airline_id
    route_id
    flight_id

    collected_at
    departure_at
    advance_days

    cabin
    fare_family
    stops

    base_fare
    taxes
    fees
    total_fare

    availability

    raw_payload_reference
    raw_hash

    quality_status
    quality_score
    ```

    ---

# 2.3 Raw and processed data

    Think:

    ```text
    RAW
    ↓
    NORMALIZED
    ↓
    VALIDATED
    ↓
    INDEX-READY
    ```

    Do **not** modify the original raw observation.

    Instead produce a processed record.

    That means if your normalization algorithm changes later, you can reprocess historical data.

    This is a major future-proofing decision.

    ---

# 2.4 Duplicate handling

    Suppose:

    ```text
    IndiGo website → ₹4,500
    OTA A          → ₹4,500
    OTA B          → ₹4,500
    ```

    That's potentially the **same flight**, not three independent pieces of evidence.

    Create a canonical flight identity:

    ```text
    airline
    flight number
    departure
    date
    origin
    destination
    ```

    Then tag the observations accordingly.

    ---

# 2.5 Missing data

    Never just delete it.

    Represent:

    ```text
    AVAILABLE
    SOLD_OUT
    SOURCE_ERROR
    PARSER_ERROR
    ROUTE_UNAVAILABLE
    TIMEOUT
    ```

    This becomes extremely useful later for your confidence score.

    ---

# Stage 2 deliverable

    You should be able to run:

    ```text
    raw data
    ↓
    normalization
    ↓
    PostgreSQL
    ```

    and query:

    > "Give me all valid comparable fares for DEL → BOM at T+15."

    ---

# STAGE 3 — Statistical engine

    **This is where the famous "math" finally happens.**

    And I deliberately placed this after the database.

    Because now you have clean data.

    ---

# 3.1 Start extremely simple

    Suppose base price:

    ```text
    ₹4,000
    ```

    Today:

    ```text
    ₹5,000
    ```

    Then:

    $$
    Index = \frac{5000}{4000}\times100 = 125
    $$

    Meaning:

    > prices are 25% higher than the base period.

    That's the core.

    ---

# 3.2 Route-level index

    For each route:

    ```text
    DEL-BOM → 125
    DEL-BLR → 112
    BOM-BLR → 118
    ...
    ```

    ---

# 3.3 National index

    Now apply weights.

    For example:

    ```text
    DEL-BOM  → 40%
    DEL-BLR  → 25%
    BOM-BLR  → 20%
    DEL-CCU  → 10%
    BLR-HYD  → 5%
    ```

    Then:

    ```text
    National index
    =
    route index × route weight
    +
    route index × route weight
    ...
    ```

    The exact weights should eventually be derived from the official methodology/traffic data rather than invented arbitrarily.

    ---

# 3.4 T+1 / T+7 / etc.

    Now you can calculate separate indices:

    ```text
    T+1 index
    T+7 index
    T+15 index
    T+30 index
    T+45 index
    ```

    And now your system can answer:

    > "Are prices rising because last-minute fares are becoming expensive, or because even fares booked 45 days early are becoming expensive?"

    That's where the analysis becomes interesting.

    ---

# 3.5 Lead-time curve

    From:

    ```text
    T+45 → ₹4,000
    T+30 → ₹4,200
    T+15 → ₹4,700
    T+7  → ₹5,800
    T+1  → ₹7,900
    ```

    you produce:

    ```text
    price
    ↑
    │             ●
    │         ●
    │      ●
    │   ●
    │ ●
    └────────────────→
    45 30 15  7  1
    ```

    This is one of the strongest analytical outputs of the project.

    ---

# Stage 3 deliverable

    At the end, you should be able to say:

    ```text
    Today's Airfare Index = 127.3

    DEL-BOM = 132.1
    DEL-BLR = 124.6
    ...

    T+1  = 151
    T+7  = 137
    T+15 = 129
    T+30 = 121
    T+45 = 118
    ```

    And every number should be reproducible from database records.

    ---

# STAGE 4 — Testing + robustness

    This should be much larger than ordinary unit testing.

    Your question isn't merely:

    > "Does the code run?"

    It's:

    > **"Can I trust the number?"**

    ---

# 4.1 Unit tests

    Test:

    ```text
    normalization
    duplicate detection
    fare calculation
    index calculation
    weight calculation
    outlier detection
    ```

    ---

# 4.2 Integration tests

    Test:

    ```text
    scraper
    ↓
    parser
    ↓
    normalizer
    ↓
    database
    ↓
    index
    ```

    as one pipeline.

    ---

# 4.3 Fake-data test suite

    This will be extremely useful.

    Create known input:

    ```text
    ₹100
    ₹100
    ₹100
    ₹100
    ```

    Expected:

    ```text
    Index = 100
    ```

    Then:

    ```text
    ₹110
    ₹120
    ₹130
    ```

    You already know what the output should approximately be.

    This lets you guarantee that future changes don't silently break the statistics.

    ---

# 4.4 Failure tests

    Intentionally introduce:

    ```text
    missing tax
    missing flight number
    negative fare
    duplicate flight
    ₹50,000 fare
    sold-out flight
    broken website
    timeout
    partial response
    ```

    Then verify the system behaves correctly.

    ---

# 4.5 Source failure testing

    Turn off an airline.

    Your system should say:

    ```text
    IndiGo collector
    ❌ unavailable

    Overall index
    ✓ still available

    Confidence
    94% → 87%
    ```

    That is much better than:

    ```text
    ERROR 500
    ```

    ---

# 4.6 Real-world testing

    This is where we run the system continuously.

    You want:

    ```text
    24 hours
    ↓
    3 days
    ↓
    7 days
    ```

    of actual collection.

    Monitor:

    ```text
    success rate
    coverage
    duplicate rate
    parser errors
    source downtime
    observation count
    ```

    ---

# 4.7 DGCA validation

    The problem explicitly requires a 30-day back-test against publicly available DGCA monthly average-fare data.

    Don't just write:

    ```text
    Our result looks similar.
    ```

    Calculate:

    ```text
    MAE
    MAPE
    RMSE
    correlation
    directional agreement
    ```

    For example:

    ```text
    Our index     127.4
    Benchmark     129.1

    MAPE          2.8%
    Correlation   0.94
    ```

    Those numbers become extremely valuable for the PPT later.

    ---

# STAGE 5 — Advanced intelligence

    **Only after the previous stages work.**

    This is your original Stage 4, but I would move it much later.

    ---

## 5.1 Confidence score

    Every index gets:

    ```text
    Confidence: 94%
    ```

    Based on things such as:

    ```text
    data coverage
    source diversity
    freshness
    missing observations
    cross-source agreement
    ```

    It doesn't have to be a scientifically perfect confidence interval at first.

    We can initially implement a transparent **data reliability score**, then evolve it into proper statistical uncertainty.

    ---

# 5.2 Data-quality score

    Example:

    ```text
    Data Quality: 96.2%

    Coverage       98%
    Freshness      95%
    Source health  99%
    Completeness   93%
    ```

    ---

# 5.3 Data provenance

    Click:

    ```text
    Index = 127.4
    ```

    and trace:

    ```text
    127.4
    ↓
    Route contributions
    ↓
    individual fare observations
    ↓
    source
    ↓
    timestamp
    ↓
    raw record
    ```

    This is a major differentiator.

    ---

# 5.4 Anomaly detection

    Detect:

    ```text
    DEL-BOM
    normally ₹4k–₹7k

    today:
    ₹13,900
    ```

    System says:

    ```text
    ⚠ anomaly
    ```

    But importantly:

    > **Don't automatically delete it.**

    Flag it for analysis.

    ---

# 5.5 Event intelligence

    Eventually:

    ```text
    Diwali
    Christmas
    IPL
    major airport disruption
    route launch
    ```

    can be associated with fare movements.

    Then you can show:

    ```text
    Airfare ↑ 17%

    Possible contributors:
    Festival demand
    Last-minute booking pressure
    Route-level capacity reduction
    ```

    Always distinguish correlation from proven causation.

    ---

# 5.6 Source health

    Your system should know:

    ```text
    IndiGo        98.7%
    Air India     96.1%
    Akasa         93.4%
    SpiceJet      89.7%
    OTA-A         94.2%
    ```

    This becomes part of the confidence calculation.

    ---

# STAGE 6 — API + final product

    Once the engine is trustworthy, expose it.

    ---

## API

    Something like:

    ```text
    GET /index/current

    GET /index/history

    GET /routes

    GET /routes/{route}

    GET /routes/{route}/lead-time

    GET /observations

    GET /data-quality

    GET /sources/health

    GET /methodology
    ```

    ---

# Dashboard

    The frontend team/PPT person can eventually consume the API.

    Your job is to make sure the API exposes **good data**, not just pretty charts.

    ---

# The final system

    By the end, you want:

    ```text
    ┌─────────────────┐
    │ Airlines / OTAs │
    └────────┬────────┘
    ↓
    ┌─────────────────┐
    │   Collectors    │
    └────────┬────────┘
    ↓
    ┌─────────────────┐
    │ Raw observations│
    └────────┬────────┘
    ↓
    ┌─────────────────┐
    │ Normalization   │
    └────────┬────────┘
    ↓
    ┌─────────────────┐
    │ Quality Control │
    └────────┬────────┘
    ↓
    PostgreSQL
    ↓
    ┌─────────────────┐
    │ Statistical     │
    │ Engine          │
    └────────┬────────┘
    ↓
    ┌────────────────┼────────────────┐
    ↓                ↓                ↓
    Airfare          Lead-time        Confidence
    Index              Index             score
    ↓                ↓                ↓
    ┌─────────────────┐
    │      API        │
    └────────┬────────┘
    ↓
    Dashboard
    ```

    ---

# How I would prioritize your time

    Because you're **one developer + an agent**, we need to be ruthless.

### Tier 1 — MUST WORK

    ```text
    ✅ 1+ real scraper
    ✅ 5 routes
    ✅ 5 booking windows
    ✅ normalized fare data
    ✅ PostgreSQL
    ✅ reproducible index
    ✅ route analysis
    ✅ basic API
    ✅ tests
    ```

### Tier 2 — SHOULD WORK

    ```text
    ✅ 5 airlines
    ✅ OTA collection
    ✅ dynamic scheduler
    ✅ source health
    ✅ DGCA validation
    ✅ lead-time analysis
    ✅ data-quality metrics
    ```

### Tier 3 — WINNING FEATURES

    ```text
    ✅ confidence score
    ✅ provenance
    ✅ anomaly detection
    ✅ event intelligence
    ✅ explanation of index movement
    ```

### Tier 4 — Don't waste time on this early

    ```text
    ❌ fancy AI chatbot
    ❌ unnecessarily complex microservices
    ❌ Kubernetes
    ❌ huge ML model
    ❌ elaborate authentication
    ❌ beautiful frontend before data works
    ```

    ---

# The development philosophy I'd use

    Your repository should grow roughly like this:

    ```text
    APEX/
    │
    ├── collectors/
    │   ├── base.py
    │   ├── indigo.py
    │   ├── air_india.py
    │   ├── air_india_express.py
    │   ├── akasa.py
    │   ├── spicejet.py
    │   └── ota/
    │
    ├── models/
    │   ├── fare.py
    │   ├── route.py
    │   └── flight.py
    │
    ├── normalization/
    │   ├── fare.py
    │   ├── duplicates.py
    │   └── outliers.py
    │
    ├── storage/
    │   ├── models.py
    │   ├── repositories.py
    │   └── migrations/
    │
    ├── statistics/
    │   ├── index.py
    │   ├── weights.py
    │   ├── lead_time.py
    │   └── confidence.py
    │
    ├── scheduler/
    │   └── scheduler.py
    │
    ├── validation/
    │   ├── dgca.py
    │   └── metrics.py
    │
    ├── api/
    │   └── ...
    │
    ├── tests/
    │   ├── unit/
    │   ├── integration/
    │   └── fixtures/
    │
    └── docs/
    ├── methodology.md
    ├── architecture.md
    └── data-specification.md
    ```

    The exact names can change; the important thing is the **separation of responsibilities**.

    ---

# One very important decision I'd make now

    Don't think of the project as:

    > **"a scraper that calculates an index."**

    Think of it as:

    > **"a statistical data pipeline whose first input happens to be airline/OTA websites."**

    That distinction will make your architecture much better.

    The scraper is replaceable.

    The database is replaceable.

    Even the sources are replaceable.

    But this should remain stable:

    ```text
    FareObservation
    ↓
    Normalization
    ↓
    Quality
    ↓
    Statistical engine
    ↓
    Index
    ```

    That is the **core product**.

    ---

# Your first actual development milestone

    I would make the first milestone extremely small:

    > **Given one route, one airline and one booking window, collect one real fare and successfully store a complete `FareObservation` in PostgreSQL.**

    Not a dashboard.

    Not AI.

    Not national index.

    Not five airlines.

    Just:

    ```text
    website
    ↓
    scraper
    ↓
    FareObservation
    ↓
    PostgreSQL
    ```

    Once that pipeline works, the rest becomes expansion rather than guessing.

    And there is one more thing I strongly recommend: **we should design Stage 0 together in detail before you start implementing Stage 1.** In the next step, we can define the exact `FareObservation` schema, what fields are mandatory/optional, the 5-route × 5-window collection matrix, and the first database schema. That will give your coding agent an unambiguous specification to work from.

    [1]: https://neon.com/blog/new-usage-based-pricing?utm_source=chatgpt.com "Neon’s New Pricing, Explained: Usage-Based, No Minimum - Neon"
    [2]: https://supabase.com/docs/guides/platform/compute-and-disk?utm_source=chatgpt.com "Compute and Disk | Supabase Docs"
    [3]: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm?utm_source=chatgpt.com "Always Free Resources"
