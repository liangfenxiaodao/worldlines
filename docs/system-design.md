# Worldlines — System Design Document

## 1. Purpose & Scope

### 1.1 Purpose of Worldlines
Worldlines is a long-term trend intelligence system designed to observe, organize, and synthesize information about **structural change over multi-year horizons**.

The system exists to support deep thinking about how the world evolves, not to provide answers, predictions, or investment recommendations.

Worldlines helps the user:
- Understand how forces evolve over time
- Identify emerging constraints and enabling factors
- Observe convergence, divergence, and persistence across domains

### 1.2 What This System Explicitly Does NOT Do
Worldlines does not:
- Generate trading signals
- Predict prices, markets, or outcomes
- Optimize for breaking news speed
- Rank assets, companies, or sectors by attractiveness
- Replace human judgment or strategic thinking

### 1.3 Time Horizon & Intended Use
Worldlines is designed for **multi-year (5+ year) thinking**.

Short-term events are only relevant insofar as they:
- Reveal underlying structural forces
- Expose constraints or inflection points
- Accumulate into longer-term patterns

The system is intended to be used continuously and reflectively, not reactively.

### 1.4 Relationship to Investment Decision-Making
Worldlines is a **decision-support system**, not a decision engine.

It informs the user’s mental models and long-term theses but never produces actionable investment advice.

---

## 2. Design Principles

### 2.1 Signal Over Noise
The system prioritizes structural signals over event frequency.

Incomplete coverage is acceptable.
Low-noise interpretation is not optional.

### 2.2 Structure Over Events
Events are treated as **surface manifestations** of deeper forces.

Worldlines focuses on:
- Patterns
- Constraints
- Directional shifts
- Persistent pressures

rather than isolated incidents.

### 2.3 Interpretability Over Optimization
All outputs must remain interpretable by a human reader.

Black-box scoring systems, opaque rankings, and unexplained conclusions are intentionally avoided.

### 2.4 Stability Over Speed
Latency is acceptable if it improves clarity.

Worldlines is not optimized for real-time alerting.

### 2.5 Evolution Over Finality
The system is designed to evolve.

Schemas, prompts, and classifications may change as understanding improves.
No component is treated as final.

---

## 3. Conceptual Model

### 3.1 Events vs Structures
An event is a point in time.
A structure is a trajectory over time.

Worldlines treats events as **data points along structural trajectories**.

### 3.2 Worldlines as Evolving Trajectories
Each structural force is conceptualized as a **worldline**:
- It has direction
- It has momentum
- It may strengthen, weaken, branch, or stall

Worldlines maps these trajectories rather than predicting endpoints.

### 3.3 Multi-Dimensional Observation
Structural change rarely occurs along a single axis.

Worldlines observes the world through **multiple concurrent dimensions**, allowing intersections and interactions to emerge organically.

### 3.4 Signal Accumulation Over Time
No single item is decisive.

Meaning emerges through accumulation, repetition, and persistence.

---

## 4. The Five Structural Dimensions

### 4.1 Compute & Computational Paradigms
This dimension observes how computation is produced, organized, and constrained.

Examples include:
- Compute architectures
- Hardware specialization
- Cost curves and efficiency limits
- Centralization vs distribution

Out of scope:
- Product feature announcements
- Performance benchmarks without structural relevance

### 4.2 Capital Flows & Business Models
This dimension observes how capital is allocated and monetized.

Examples include:
- Capital expenditure patterns
- Business model sustainability
- Shifts in incentive structures
- Return compression or expansion

Out of scope:
- Short-term earnings surprises without structural implications

### 4.3 Energy, Resources & Physical Constraints
This dimension observes real-world limits.

Examples include:
- Energy availability and cost
- Land, water, and material constraints
- Infrastructure bottlenecks
- Irreducible physical costs

Out of scope:
- Speculative or hypothetical constraints not grounded in reality

### 4.4 Technology Adoption & Industrial Diffusion
This dimension observes whether technology moves from experimentation to production.

Examples include:
- Enterprise-scale deployment
- Integration into core workflows
- Changes in organizational behavior
- Productivity impacts

Out of scope:
- Demos, prototypes, or isolated pilots without follow-through

### 4.5 Governance, Regulation & Societal Response
This dimension observes how institutions respond to change.

Examples include:
- Regulation and policy
- Subsidies or restrictions
- Social acceptance or backlash
- Jurisdictional divergence

Out of scope:
- Opinion pieces without institutional consequence

---

## 5. Information Lifecycle

### 5.1 Ingestion
Worldlines ingests information from multiple heterogeneous sources.

Sources are abstracted; the system does not privilege any single channel.

### 5.2 Normalization
All incoming information is transformed into a canonical internal representation:
- Title
- Source
- Timestamp
- Content
- Canonical link

### 5.3 De-duplication
Duplicate or near-duplicate items are merged.

Structural relevance is preserved while redundancy is reduced.

### 5.4 Temporal Persistence
All processed information is stored to enable longitudinal analysis.

---

## 6. AI-Assisted Analysis Layer

### 6.1 Role of AI in Worldlines
AI acts as a **structural classifier and summarizer**.

It assists human cognition; it does not replace it.

### 6.2 What AI Is Allowed to Do
AI may:
- Assign dimensions
- Identify change types
- Attribute time horizons
- Produce neutral summaries
- Extract key factual elements

### 6.3 What AI Must NOT Do
AI must not:
- Make predictions
- Express opinions
- Label information as good or bad
- Recommend actions
- Optimize for engagement

### 6.4 Structural Classification vs Interpretation
AI performs classification, not interpretation.

Interpretation remains the responsibility of the human user.

---

## 7. Analytical Outputs (Conceptual)

### 7.1 Dimension Assignment
Each item may map to one or more dimensions.

### 7.2 Change Type Classification
Change types include:
- Reinforcing
- Friction
- Early signal
- Neutral

### 7.3 Time Horizon Attribution
Each item is attributed a likely horizon:
- Short-term
- Medium-term
- Long-term

### 7.4 Neutral Summarization
Summaries are factual, restrained, and non-evaluative.

### 7.5 Importance & Notification Eligibility
Importance reflects **structural relevance**, not urgency.

---

## 8. Structural Exposure Mapping Layer

### 8.1 Purpose
Worldlines ultimately serves investment research. While the system does not produce predictions or recommendations, it must enable outputs to be mapped to **investable instruments** (e.g., public equities).

This layer provides a **neutral mapping** from observed structural signals (Worldlines outputs) to a set of relevant tickers, describing **exposure**, not expected returns.

### 8.2 Core Principle: Exposure, Not Direction
Structural exposure mapping must not:
- Label impacts as bullish/bearish
- Predict price movements
- Recommend buying/selling/holding

Instead, it answers:
- Which listed companies are structurally exposed to the described forces?
- Is the exposure direct or indirect?
- Is the exposure core to the company’s business, or peripheral?

### 8.3 When to Map to Tickers
Mapping is applied only when the underlying item has sufficient structural relevance, typically:
- importance is medium/high (or equivalent threshold)
- dimensions include at least one primary dimension with clear linkage
- the item implies a concrete mechanism (supply chain, capacity, regulation, capex shift, adoption)

Low-relevance or purely speculative items should not be mapped.

### 8.4 Exposure Taxonomy
Each mapped ticker is described using a small set of consistent attributes:

- **Exposure type**
  - direct: company is a primary actor in the signal
  - indirect: company is upstream/downstream or second-order affected
  - contextual: company provides context (peer benchmark) but is not causally involved

- **Business role (examples)**
  - infrastructure operator
  - upstream supplier
  - downstream adopter
  - platform intermediary
  - regulated entity
  - capital allocator

- **Exposure strength**
  - core: central to revenue/cost structure and strategic direction
  - material: meaningful but not dominant
  - peripheral: weak linkage; include only if necessary for completeness

- **Confidence**
  - high / medium / low based on source quality and clarity of mechanism

### 8.5 Output Contract (Conceptual)
Structural exposure mapping augments the analytical output with a `structural_exposure` field.

The system records:
- ticker(s)
- exposure attributes (type, role, strength, confidence)
- which dimensions are implicated
- brief neutral rationale (“why this ticker is linked”)

No directional claims are allowed.

### 8.6 Portfolio Interpretation Remains Human
Worldlines stops at exposure mapping. Portfolio construction, valuation, and risk decisions remain a human responsibility.

This separation protects Worldlines from collapsing into short-term narrative trading while still making it practically usable for investment research.

---

## 9. Storage & Historical Context

### 9.1 Why History Matters
Structural understanding requires memory.

Without persistence, trends cannot be observed.

### 9.2 Separation of Raw Data and Analysis
Raw inputs and analytical outputs are stored separately.

This allows reinterpretation as understanding evolves.

### 9.3 Temporal Linking
Signals may be related across time.

Worldlines preserves these relationships conceptually.

### 9.4 Re-analysis
Past items may be re-analyzed with updated frameworks.

---

## 10. Output & Review Surfaces

### 10.1 Telegram Daily Digest (MVP Primary Output)
The primary output surface is a **daily Telegram digest** delivered to a configured chat.

The digest includes:
- **Bilingual synthesis summary** (English and Chinese) — an AI-generated paragraph that synthesizes the day's structural signals into a cohesive narrative, placed at the top of the digest before individual items
- Number of items ingested and analyzed
- Breakdown by structural dimension
- High-importance items with neutral summaries
- Change type distribution (reinforcing / friction / early signal / neutral)

#### Digest Summary
Each digest begins with a short AI-generated summary that distills the day's items into key structural observations. The summary is produced in both **English** and **Chinese** (Simplified) to support bilingual readers.

Summary constraints:
- Neutral and non-predictive — follows the same analytical stance as item-level summaries
- Synthesizes across items rather than repeating individual summaries
- Highlights cross-dimensional patterns, emerging themes, or notable structural shifts
- Each language version is independently generated (not a translation) to ensure natural phrasing
- Persisted as `summary_en` and `summary_zh` in the digest record
- Empty-day digests do not include a summary

Design constraints:
- Messages follow Telegram's formatting and 4096-character limit
- Long digests are split across multiple messages
- Days with no new items produce a brief acknowledgment, not silence
- Bot token and chat ID are managed as secrets

### 10.2 Event-Level Notifications
Selective immediate notifications may be sent via Telegram for items classified as `importance: high`. This is optional and secondary to the daily digest.

### 10.3 Periodic Summaries (Post-MVP)
Regular summaries surface:
- Signal density
- Emerging constraints
- Persistent themes

### 10.4 Trend Observation
Trends are observed, not forecasted.

### 10.5 Human Role
The human user reflects, contextualizes, and decides.

---

## 11. Deployment Model

### 11.1 Platform: Fly.io
Worldlines is deployed to **Fly.io** (free tier), chosen for persistent volume support (required for SQLite) and simple container-based deployment.

### 11.2 Tech Stack
- **Backend:** Python
- **Database:** SQLite on a Fly.io persistent volume
- **Frontend:** Node.js (post-MVP, not needed initially)

### 11.3 Containerization
The application is packaged as a Docker container. A `Dockerfile` and `fly.toml` define the build and deployment configuration.

### 11.4 Scheduling
Ingestion and digest generation run on a cron schedule inside the container. The system runs as a long-lived process (not serverless) to support cron and persistent SQLite access.

### 11.5 Secrets Management
Secrets are managed via `fly secrets set`. The SQLite database path is configured in `fly.toml` to point to the persistent volume. See `docs/configuration.md` for the full variable reference.

---

## 12. Evolution Path

### 12.1 MVP: Ingest → Analyze → Telegram Digest
Current phase.

A single source adapter ingests information, the AI layer classifies it, and a daily Telegram digest is delivered. Deployed to cloud and running unattended.

### 12.2 Phase 2: Exposure Mapping & Additional Sources
Structural exposure mapping is added. Additional source adapters broaden coverage.

### 12.3 Phase 3: Signal Aggregation & Query Interface
Patterns and densities become visible. A review surface (CLI or web) enables browsing and filtering.

### 12.4 Phase 4: Temporal Linking & Hypothesis Tracking
Optional future phase.

Temporal links connect signals across time. Explicit hypotheses may be tracked, but never forced.

---

## 13. Non-Goals & Trade-offs

### 12.1 No Forecasting
Prediction is intentionally excluded.

### 12.2 Incomplete Coverage
No attempt is made to observe everything.

### 12.3 Deliberate Slowness
Speed is traded for clarity.

### 12.4 Known Limitations
Bias, missing data, and interpretive uncertainty are accepted realities.

---

## 14. Open Questions & Future Considerations

- How should conflicting signals be represented?
- How should diminishing relevance be handled?
- When does accumulation justify hypothesis formulation?

These questions remain open by design.
