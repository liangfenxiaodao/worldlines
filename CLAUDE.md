# Worldlines

Worldlines is a **long-term trend intelligence system** designed for long term investment research.

It is NOT:
- A trading signal system
- A short-term market alert tool
- A news aggregation product

It IS:
- A structured observation system
- A trend exploration and synthesis engine
- A decision-support system for long-horizon thinking

The system observes the world through **five structural dimensions**, without assuming conclusions in advance.

## Core Principle
Do NOT optimize for speed or coverage.
Optimize for:
- Signal over noise
- Structure over events
- Long-term relevance over short-term excitement

## Five Structural Dimensions
All information must be analyzed and organized into one or more of the following dimensions:

1. **Compute & Computational Paradigms**
   - How the world computes
   - Cost, scale, architecture, bottlenecks

2. **Capital Flows & Business Models**
   - Where capital is deployed
   - ROI structures, sustainability, shifts in incentives

3. **Energy, Resources & Physical Constraints**
   - Power, land, water, materials
   - Non-negotiable real-world limits

4. **Technology Adoption & Industrial Diffusion**
   - From demo to production
   - From tool to infrastructure

5. **Governance, Regulation & Societal Response**
   - Policy, regulation, backlash, alignment or resistance

## Analytical Stance
- Do NOT make investment recommendations
- Do NOT label news as bullish or bearish
- Do NOT assume trends are “good” or “bad”

Instead:
- Classify
- Contextualize
- Observe directionality
- Identify constraints and early signals

## Output Expectations
When analyzing information, always aim to:
- Place it within the five dimensions
- Indicate the type of structural change (reinforcing, friction, early signal, neutral)
- Indicate the likely time horizon (short / medium / long)
- Produce a neutral, factual summary

## Tech Stack
- **Backend:** Python
- **Frontend:** Node.js (https://worldlines.fly.dev/)
- **Database:** SQLite (single file, persistent volume)
- **Deployment:** Fly.io (persistent disk for SQLite)
- **LLM:** Anthropic Claude API

## MVP Scope
The MVP delivers a working end-to-end system:
**Ingest → Analyze → Telegram Daily Digest**, deployed to Fly.io and running unattended.

MVP includes:
- One source adapter (RSS feeds)
- Normalization and deduplication
- AI classification (dimensions, change type, time horizon, summary, importance)
- Daily Telegram digest as the primary output
- Fly.io deployment with secrets via `fly secrets set`

Post-MVP (iterate after shipping):
- Additional source adapters
- Temporal linking and re-analysis
- CI/CD, periodic summaries

Shipped post-MVP:
- Structural exposure mapping
- Web frontend (https://worldlines.fly.dev/)
- Monitoring, backups, and failure alerts

## Development Guidance
- Follow the documented system design, schemas, and API contracts strictly
- Do not introduce features or assumptions not discussed in the docs
- Prioritize shipping MVP over completeness
- Deploy early and iterate

## Tone & Style
- Analytical
- Calm
- Long-horizon
- Non-hype
- Explicit about uncertainty
