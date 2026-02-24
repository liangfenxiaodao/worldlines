"""Exposure mapping prompt template and output validation."""

from __future__ import annotations

from worldlines.analysis.prompt import (
    VALID_DIMENSIONS,
    _FORBIDDEN_PATTERNS,
)

SYSTEM_PROMPT = """\
You are a structural exposure mapper for a long-term trend intelligence system called Worldlines.

Your role is to map structural analyses to publicly listed companies that have \
meaningful exposure to the structural forces described. You identify which companies \
are structurally positioned — positively or negatively — relative to multi-year trends.

You are not a financial advisor, stock picker, or market commentator.
You do not recommend buying or selling. You do not predict stock prices.
You map structural exposure — nothing more.

EXPOSURE TAXONOMY:

exposure_type:
- direct: The company is a primary participant in the structural force described.
- indirect: The company is affected through supply chain, customer base, or competitive dynamics.
- contextual: The company operates in an adjacent space where the structural force creates second-order effects.

business_role:
- infrastructure_operator: Builds or operates physical/digital infrastructure (data centers, networks, grids).
- upstream_supplier: Provides inputs, components, or raw materials to the structural trend.
- downstream_adopter: Adopts or integrates the technology/trend into its products or operations.
- platform_intermediary: Operates a marketplace, exchange, or coordination layer.
- regulated_entity: Subject to regulation or policy changes described in the analysis.
- capital_allocator: Deploys capital (VC, PE, sovereign funds, banks) toward the trend.
- other: Does not fit the above categories.

exposure_strength:
- core: The structural force is central to the company's business model or competitive position.
- material: The structural force meaningfully affects the company but is not its primary driver.
- peripheral: The company has limited but identifiable exposure.

confidence:
- high: Clear, well-documented connection between the company and the structural force.
- medium: Reasonable inference based on known business activities.
- low: Plausible but requires assumptions or extrapolation.

RATIONALE RULES:
- Maximum 300 characters
- Neutral, factual language
- Describe the structural connection, not a prediction
- No forbidden terms: bullish, bearish, buy, sell, upside, downside, outperform, underperform

TICKER RULES:
- Use the primary exchange ticker symbol (e.g., AAPL, MSFT, 9984.T)
- Only include publicly listed companies
- Do not include private companies, government entities, or non-equity instruments
- For companies with multiple share classes, always use the most widely traded class:
  use GOOGL (not GOOG), BRK-B (not BRK-A), use the standard class not a restricted variant
- For companies dual-listed in the US and abroad, prefer the US ticker (NYSE/NASDAQ)
- Use a single canonical ticker per company — never list the same company twice under different symbols

WHEN TO RETURN EMPTY:
- The analysis describes abstract or theoretical discussions without identifiable company exposure
- The analysis only involves private companies or government entities
- The structural signal is too diffuse to attribute to specific companies
- You are not confident in any mapping at medium or higher confidence

When returning empty, provide a skipped_reason explaining why no exposures were mapped.
The skipped_reason and exposures array are mutually exclusive: if exposures is non-empty, \
skipped_reason must be null; if exposures is empty, skipped_reason must be a non-empty string."""

USER_PROMPT_TEMPLATE = """\
Map the following structural analysis to publicly listed companies with structural exposure.

ANALYSIS:
Summary: {summary}
Dimensions: {dimensions}
Change type: {change_type}
Time horizon: {time_horizon}
Importance: {importance}
Key entities: {key_entities}

ITEM CONTEXT:
Title: {title}
Source: {source_name} ({source_type})

INSTRUCTIONS:
1. Identify publicly listed companies with structural exposure to the forces described.
2. For each company, specify ticker, exposure_type, business_role, exposure_strength, \
confidence, dimensions_implicated (from the analysis dimensions), and a rationale.
3. If no companies can be confidently mapped, return an empty exposures array with a skipped_reason.
4. Limit to at most 5 companies. Prefer fewer, higher-confidence mappings.

Respond in the following JSON format only. Do not include any text outside the JSON.

{{
  "exposures": [
    {{
      "ticker": "...",
      "exposure_type": "direct|indirect|contextual",
      "business_role": "infrastructure_operator|upstream_supplier|downstream_adopter|platform_intermediary|regulated_entity|capital_allocator|other",
      "exposure_strength": "core|material|peripheral",
      "confidence": "high|medium|low",
      "dimensions_implicated": ["..."],
      "rationale": "..."
    }}
  ],
  "skipped_reason": null
}}"""

VALID_EXPOSURE_TYPES = frozenset({"direct", "indirect", "contextual"})
VALID_BUSINESS_ROLES = frozenset({
    "infrastructure_operator", "upstream_supplier", "downstream_adopter",
    "platform_intermediary", "regulated_entity", "capital_allocator", "other",
})
VALID_EXPOSURE_STRENGTHS = frozenset({"core", "material", "peripheral"})
VALID_CONFIDENCE = frozenset({"high", "medium", "low"})


def format_user_prompt(
    *,
    summary: str,
    dimensions: str,
    change_type: str,
    time_horizon: str,
    importance: str,
    key_entities: str,
    title: str,
    source_name: str,
    source_type: str,
) -> str:
    """Format the user prompt with analysis and item fields."""
    return USER_PROMPT_TEMPLATE.format(
        summary=summary,
        dimensions=dimensions,
        change_type=change_type,
        time_horizon=time_horizon,
        importance=importance,
        key_entities=key_entities,
        title=title,
        source_name=source_name,
        source_type=source_type,
    )


def validate_output(data: dict) -> list[str]:
    """Validate a parsed LLM response for exposure mapping.

    Returns a list of validation errors. Empty list means valid.
    """
    errors: list[str] = []

    exposures = data.get("exposures")
    if not isinstance(exposures, list):
        errors.append("exposures must be a list")
        return errors

    skipped_reason = data.get("skipped_reason")

    # Mutual exclusivity: exposures non-empty XOR skipped_reason non-empty
    if len(exposures) == 0 and not skipped_reason:
        errors.append("skipped_reason is required when exposures is empty")
    if len(exposures) > 0 and skipped_reason:
        errors.append("skipped_reason must be null when exposures are present")

    for i, exp in enumerate(exposures):
        if not isinstance(exp, dict):
            errors.append(f"exposures[{i}] must be an object")
            continue

        # ticker
        ticker = exp.get("ticker")
        if not isinstance(ticker, str) or not ticker.strip():
            errors.append(f"exposures[{i}].ticker must be a non-empty string")

        # exposure_type
        et = exp.get("exposure_type")
        if et not in VALID_EXPOSURE_TYPES:
            errors.append(f"exposures[{i}].exposure_type '{et}' is not valid")

        # business_role
        br = exp.get("business_role")
        if br not in VALID_BUSINESS_ROLES:
            errors.append(f"exposures[{i}].business_role '{br}' is not valid")

        # exposure_strength
        es = exp.get("exposure_strength")
        if es not in VALID_EXPOSURE_STRENGTHS:
            errors.append(f"exposures[{i}].exposure_strength '{es}' is not valid")

        # confidence
        conf = exp.get("confidence")
        if conf not in VALID_CONFIDENCE:
            errors.append(f"exposures[{i}].confidence '{conf}' is not valid")

        # dimensions_implicated
        dims = exp.get("dimensions_implicated")
        if not isinstance(dims, list) or len(dims) == 0:
            errors.append(f"exposures[{i}].dimensions_implicated must be a non-empty array")
        elif not all(d in VALID_DIMENSIONS for d in dims):
            errors.append(f"exposures[{i}].dimensions_implicated contains invalid dimension")

        # rationale
        rationale = exp.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"exposures[{i}].rationale must be a non-empty string")
        elif len(rationale) > 300:
            errors.append(
                f"exposures[{i}].rationale exceeds 300 characters ({len(rationale)})"
            )
        else:
            for term, pattern in _FORBIDDEN_PATTERNS.items():
                if pattern.search(rationale):
                    errors.append(
                        f"exposures[{i}].rationale contains forbidden term '{term}'"
                    )

    return errors
