"""HTML rendering and message chunking for Telegram digests."""

from __future__ import annotations

import html
import logging

logger = logging.getLogger(__name__)

DIMENSION_DISPLAY = {
    "compute_and_computational_paradigms": "Compute & Computational Paradigms",
    "capital_flows_and_business_models": "Capital Flows & Business Models",
    "energy_resources_and_physical_constraints": "Energy, Resources & Physical Constraints",
    "technology_adoption_and_industrial_diffusion": "Technology Adoption & Industrial Diffusion",
    "governance_regulation_and_societal_response": "Governance, Regulation & Societal Response",
}

CHANGE_TYPE_DISPLAY = {
    "reinforcing": "Reinforcing",
    "friction": "Friction",
    "early_signal": "Early Signal",
    "neutral": "Neutral",
}

TELEGRAM_MAX_LENGTH = 4096


def render_digest_html(data) -> str:
    """Render a full digest as Telegram-flavoured HTML.

    ``data`` is a DigestData instance (imported at call-time to avoid circular
    imports — only its attributes are accessed).
    """
    lines: list[str] = []

    # Header
    lines.append("<b>Worldlines Daily Digest</b>")
    lines.append(f"<i>{data.digest_date} | {data.total_analyzed} items analyzed</i>")
    lines.append("")

    # Dimension breakdown
    lines.append("<b>Dimension Breakdown</b>")
    for dim_key, count in data.dimension_breakdown.items():
        label = DIMENSION_DISPLAY.get(dim_key, dim_key)
        lines.append(f"  {label}: {count}")
    lines.append("")

    # Change type distribution
    lines.append("<b>Change Types</b>")
    parts = []
    for ct_key, count in data.change_type_distribution.items():
        label = CHANGE_TYPE_DISPLAY.get(ct_key, ct_key)
        parts.append(f"{label}: {count}")
    lines.append("  " + " | ".join(parts))
    lines.append("")

    # Key items
    lines.append("<b>Key Items</b>")
    lines.append("")
    for idx, item in enumerate(data.items, start=1):
        lines.append(f"{idx}. <b>{html.escape(item.title)}</b>")
        lines.append(
            f"   <i>{item.change_type} | {item.time_horizon} | {item.importance}</i>"
        )
        lines.append(f"   {html.escape(item.summary)}")
        dim_labels = [DIMENSION_DISPLAY.get(d, d) for d in item.dimensions]
        lines.append(f"   {', '.join(dim_labels)}")
        if item.canonical_link:
            lines.append(f'   <a href="{html.escape(item.canonical_link)}">Source</a>')
        lines.append("")

    return "\n".join(lines).rstrip()


def render_empty_day_html(digest_date: str) -> str:
    """Render a short message for days with no items to report."""
    lines = [
        "<b>Worldlines Daily Digest</b>",
        f"<i>{html.escape(digest_date)}</i>",
        "",
        "No items to report today.",
    ]
    return "\n".join(lines)


def chunk_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> list[str]:
    """Split *text* into chunks that each fit within *max_length*.

    Splitting strategy (in order of preference):
    1. Paragraph boundaries (``\\n\\n``)
    2. Line boundaries (``\\n``)
    3. Hard split at *max_length*
    """
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Try paragraph boundary
        split_pos = _find_split(remaining, "\n\n", max_length)
        if split_pos == -1:
            # Try line boundary
            split_pos = _find_split(remaining, "\n", max_length)
        if split_pos == -1:
            # Hard split
            split_pos = max_length

        chunk = remaining[:split_pos].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_pos:].lstrip("\n")

    return chunks


def _find_split(text: str, delimiter: str, max_length: int) -> int:
    """Find the last occurrence of *delimiter* within *max_length* characters."""
    pos = text.rfind(delimiter, 0, max_length)
    if pos <= 0:
        return -1
    return pos
