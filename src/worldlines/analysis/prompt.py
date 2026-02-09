"""AI classification prompt template and output validation."""

from __future__ import annotations

import re

SYSTEM_PROMPT = """\
You are a structural analyst for a long-term trend intelligence system called Worldlines.

Your role is to classify and summarize information about structural change across \
five dimensions. You observe forces that shape the world over multi-year horizons.

You are not a financial advisor, market commentator, or news analyst.
You do not predict outcomes, express opinions, or recommend actions.
You classify, contextualize, and summarize — nothing more.

DIMENSION GUIDELINES:

1. compute_and_computational_paradigms — Assign when the item is about how \
computation is produced, scaled, or constrained: chip architectures, hardware \
specialization, accelerator roadmaps, cost curves for compute, centralization vs \
distribution of compute resources, computational bottlenecks, or new computing \
paradigms with structural evidence. Do NOT assign for product launches without \
architectural shift, benchmarks without cost/scale implications, or software \
updates without hardware relevance.

2. capital_flows_and_business_models — Assign when the item is about where capital \
is deployed at scale (capex, acquisitions, funding rounds >$100M), business model \
shifts, return structure changes, incentive realignment, capital allocation \
priorities, or monetary policy effects on capital costs and credit conditions. \
Do NOT assign for routine earnings, routine funding rounds, or stock \
price movements without structural cause.

3. energy_resources_and_physical_constraints — Assign when the item is about energy \
availability/cost/policy, land/water/material constraints, supply chain bottlenecks \
for critical materials, physical infrastructure limits, or irreducible costs. Do NOT \
assign for short-term price fluctuations, speculative constraints, or environmental \
commentary without concrete resource implications.

4. technology_adoption_and_industrial_diffusion — Assign when the item is about \
technology moving from pilot to production, enterprise-scale adoption, integration \
into core workflows, organizational behavior change, or measurable productivity \
impacts at scale. Do NOT assign for demos/prototypes without deployment evidence, \
consumer adoption without enterprise relevance, or marketing claims without evidence.

5. governance_regulation_and_societal_response — Assign when the item is about \
legislation, regulation, executive orders, central bank decisions, monetary policy \
(interest rate decisions, quantitative easing/tightening), subsidies, tariffs, \
sanctions, regulatory frameworks, social backlash with institutional consequences, \
or jurisdictional divergence. Do NOT assign for opinion pieces without institutional \
action, political rhetoric without policy movement, or individual lawsuits without \
sector-wide impact.

RELEVANCE LEVELS:
- primary: The item is centrally about this dimension. Remove it and the item loses its core meaning.
- secondary: The item has meaningful implications for this dimension but is not primarily about it.

CHANGE TYPE CLASSIFICATION:
- reinforcing: Evidence that an existing structural trend is continuing or accelerating.
- friction: Resistance, constraint, or deceleration of a structural trend.
- early_signal: Potential new structural trajectory not yet established. Bar: "If this \
scales, it would change the trajectory of this dimension." Sector-level reporting may \
indicate early signals but typically requires corroboration before high importance.
- neutral: Factual context or background without clear directional implications.

TIME HORIZON:
- short_term: Likely to play out within 1-2 years.
- medium_term: Operates on a 2-5 year horizon.
- long_term: Operates on a 5+ year horizon.
When uncertain, prefer the longer horizon.

IMPORTANCE CALIBRATION:
- high: Materially changes understanding of a structural trajectory. Must meet at \
least two: involves a top-5 actor, >20% shift in key metric, creates/removes a \
constraint, first concrete evidence of a theoretical shift. Should be rare (~10-15%).
- medium: Meaningful data point along a known trajectory, significant actor, or \
quantitative evidence. Source type (e.g. filings) may support but not solely justify.
- low: Routine updates, small-scale events, confirmations without new data. Default.

SUMMARY RULES:
- Maximum 500 characters
- Third person, present tense
- Factual and neutral
- No predictions, opinions, recommendations, or directional language
- No superlatives (breakthrough, revolutionary, game-changing) unless directly quoting
- FORBIDDEN TERMS: bullish, bearish, buy, sell, upside, downside, outperform, underperform

KEY ENTITIES:
- Extract companies (common names, not legal entities), technologies, government bodies, regions
- Deduplicate, limit to 5-7 maximum
- Do not extract generic terms, analysts, or minor entities"""

USER_PROMPT_TEMPLATE = """\
Analyze the following item and produce a structured classification.

ITEM:
Title: {title}
Source: {source_name} ({source_type})
Date: {timestamp}
Content:
{content}

INSTRUCTIONS:
1. Assign one or more structural dimensions (with relevance: primary or secondary)
2. Classify the change type
3. Attribute a time horizon
4. Write a neutral summary (max 500 characters)
5. Assess structural importance
6. Extract key entities

Respond in the following JSON format only. Do not include any text outside the JSON.

{{
  "dimensions": [
    {{"dimension": "...", "relevance": "primary|secondary"}}
  ],
  "change_type": "reinforcing|friction|early_signal|neutral",
  "time_horizon": "short_term|medium_term|long_term",
  "summary": "...",
  "importance": "low|medium|high",
  "key_entities": ["..."]
}}"""

VALID_DIMENSIONS = frozenset({
    "compute_and_computational_paradigms",
    "capital_flows_and_business_models",
    "energy_resources_and_physical_constraints",
    "technology_adoption_and_industrial_diffusion",
    "governance_regulation_and_societal_response",
})

VALID_CHANGE_TYPES = frozenset({"reinforcing", "friction", "early_signal", "neutral"})
VALID_TIME_HORIZONS = frozenset({"short_term", "medium_term", "long_term"})
VALID_IMPORTANCE = frozenset({"low", "medium", "high"})

FORBIDDEN_SUMMARY_TERMS = frozenset({
    "bullish", "bearish", "buy", "sell",
    "upside", "downside", "outperform", "underperform",
})

# Pre-compiled patterns for word-boundary matching of forbidden terms.
_FORBIDDEN_PATTERNS = {
    term: re.compile(rf"\b{term}\b", re.IGNORECASE)
    for term in FORBIDDEN_SUMMARY_TERMS
}


def format_user_prompt(
    title: str,
    source_name: str,
    source_type: str,
    timestamp: str,
    content: str,
) -> str:
    """Format the user prompt with item fields."""
    return USER_PROMPT_TEMPLATE.format(
        title=title,
        source_name=source_name,
        source_type=source_type,
        timestamp=timestamp,
        content=content,
    )


def validate_output(data: dict) -> list[str]:
    """Validate a parsed LLM response against the AnalyticalOutput schema.

    Returns a list of validation errors. Empty list means valid.
    """
    errors: list[str] = []

    # dimensions
    dims = data.get("dimensions")
    if not isinstance(dims, list) or len(dims) == 0:
        errors.append("dimensions must be a non-empty array")
    else:
        has_primary = False
        for i, d in enumerate(dims):
            if not isinstance(d, dict):
                errors.append(f"dimensions[{i}] must be an object")
                continue
            dim_val = d.get("dimension")
            if dim_val not in VALID_DIMENSIONS:
                errors.append(
                    f"dimensions[{i}].dimension '{dim_val}' is not valid"
                )
            rel_val = d.get("relevance")
            if rel_val not in ("primary", "secondary"):
                errors.append(
                    f"dimensions[{i}].relevance '{rel_val}' must be 'primary' or 'secondary'"
                )
            elif rel_val == "primary":
                has_primary = True
        if not has_primary and len(dims) > 0:
            errors.append("at least one dimension must have relevance 'primary'")

    # change_type
    ct = data.get("change_type")
    if ct not in VALID_CHANGE_TYPES:
        errors.append(f"change_type '{ct}' is not valid")

    # time_horizon
    th = data.get("time_horizon")
    if th not in VALID_TIME_HORIZONS:
        errors.append(f"time_horizon '{th}' is not valid")

    # summary
    summary = data.get("summary")
    if not isinstance(summary, str) or len(summary) == 0:
        errors.append("summary must be a non-empty string")
    elif len(summary) > 500:
        errors.append(f"summary exceeds 500 characters ({len(summary)})")
    else:
        for term, pattern in _FORBIDDEN_PATTERNS.items():
            if pattern.search(summary):
                errors.append(f"summary contains forbidden term '{term}'")

    # importance
    imp = data.get("importance")
    if imp not in VALID_IMPORTANCE:
        errors.append(f"importance '{imp}' is not valid")

    # key_entities
    entities = data.get("key_entities")
    if not isinstance(entities, list) or len(entities) == 0:
        errors.append("key_entities must be a non-empty array")
    elif not all(isinstance(e, str) for e in entities):
        errors.append("key_entities must contain only strings")

    return errors
