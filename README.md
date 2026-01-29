# Worldlines

Worldlines traces long-term structural change across compute, capital, energy, adoption, and governance.

It is not a news reader.
It is not a signal generator.
It is not designed to answer “what should I buy today?”

Instead, it answers:
- What long-term forces are strengthening or weakening?
- Where are real-world constraints emerging?
- How are capital, technology, and institutions adapting?

## Core Philosophy
The system avoids premature hypotheses.

Rather than starting with assumptions and looking for confirmation, it:
1. Observes changes across five structural dimensions
2. Accumulates signals over time
3. Allows patterns and hypotheses to emerge organically

## The Five Dimensions
All information is processed through these lenses:

1. Compute & Computational Paradigms  
2. Capital Flows & Business Models  
3. Energy, Resources & Physical Constraints  
4. Technology Adoption & Industrial Diffusion  
5. Governance, Regulation & Societal Response  

A single event may touch multiple dimensions.

## What the System Produces
- Structured, neutral summaries of relevant information
- Classification by dimension, change type, and time horizon
- Periodic digests highlighting signal density and emerging patterns

## What the System Avoids
- Stock picking
- Price prediction
- Sensational or hype-driven narratives

## Intended Use
This system is intended to be used:
- Continuously
- Reflectively
- As a thinking aid, not a decision replacement

It is a tool for understanding, not forecasting.

## MVP

Ingest from RSS feeds, classify via LLM, deliver a daily Telegram digest — deployed to Fly.io and running unattended.

**Stack:** Python · SQLite · Fly.io · Anthropic Claude API

## Documentation

| Document | Description |
|---|---|
| [System Design](docs/system-design.md) | High-level architecture, dimensions, lifecycle, deployment model |
| [Data Schemas](docs/schemas.md) | JSON schemas for all data structures |
| [Storage Design](docs/storage-design.md) | Storage architecture, temporal linking, re-analysis support |
| [API Contracts](docs/api-contracts.md) | Inter-component contracts and query interfaces |
| [AI Prompt Spec](docs/ai-prompt-spec.md) | Prompt templates, classification guidelines, validation rules |
| [Source Adapters](docs/source-adapters.md) | Adapter interface, RSS adapter spec, future adapters |
| [Configuration](docs/configuration.md) | All environment variables, defaults, and secrets management |
