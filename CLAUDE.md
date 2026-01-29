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

## MVP Scope
The MVP delivers a working end-to-end system:
**Ingest → Analyze → Telegram Daily Digest**, deployed to the cloud and running unattended.

MVP includes:
- One source adapter (ingestion)
- Normalization and deduplication
- AI classification (dimensions, change type, time horizon, summary, importance)
- Daily Telegram digest as the primary output
- Cloud deployment with secrets management

Post-MVP (iterate after shipping):
- Structural exposure mapping
- Additional source adapters
- Query interfaces and review surfaces
- Temporal linking and re-analysis
- CI/CD, monitoring, periodic summaries

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
