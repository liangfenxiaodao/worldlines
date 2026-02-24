"""Periodic summary generation — weekly (or configurable) structural synthesis."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import anthropic

from worldlines.digest.renderer import chunk_message
from worldlines.digest.telegram import send_messages
from worldlines.storage.connection import get_connection

logger = logging.getLogger(__name__)

_FORBIDDEN_PATTERNS = {
    term: re.compile(rf"\b{term}\b", re.IGNORECASE)
    for term in ("bullish", "bearish", "buy", "sell", "upside", "downside",
                 "outperform", "underperform")
}

MAX_SUMMARY_CHARS = 2000

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PeriodItem:
    """A single observation for the periodic summary."""
    title: str
    summary: str
    dimensions: list[str]
    change_type: str
    time_horizon: str
    importance: str


@dataclass(frozen=True)
class PeriodData:
    """Aggregated data for a time window."""
    period_label: str
    window_days: int
    since: str
    until: str
    total_analyzed: int
    item_count: int
    dimension_breakdown: dict[str, int]
    change_type_distribution: dict[str, int]
    items: list[PeriodItem] = field(default_factory=list)


@dataclass(frozen=True)
class PeriodicSummaryResult:
    """Pipeline output returned to the caller."""
    record: dict | None
    delivery_status: str   # "sent" | "skipped" | "failed"
    error: str | None = None


# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a structural synthesis writer for a long-term trend intelligence system \
called Worldlines.

Your role is to produce a concise bilingual synthesis of structural observations \
over a {window_days}-day window. You identify signal density, persistent themes, \
and emerging constraints across five structural dimensions.

You are not a financial advisor, market commentator, or news analyst.
You do not predict outcomes, express opinions, or recommend actions.
You classify, contextualize, and identify patterns — nothing more.

RULES:
- Write in third person, present tense
- Be factual and neutral
- No predictions, opinions, recommendations, or directional language
- No superlatives (breakthrough, revolutionary, game-changing) unless directly quoting
- FORBIDDEN TERMS: bullish, bearish, buy, sell, upside, downside, outperform, underperform
- Each summary must be at most 800 characters
- summary_zh must be written in Simplified Chinese

ADDRESS THESE SPECIFICALLY:
1. Which dimensions carry the most signal density (as a proportion of total)?
2. What themes or structural forces appear repeatedly across observations?
3. Where are constraints or friction accumulating?
4. Is the overall signal pattern reinforcing, mixed, or shifting?

Respond in JSON only: {{"summary_en": "...", "summary_zh": "..."}}"""

_USER_TEMPLATE = """\
PERIOD: {since} to {until} ({window_days} days)
TOTAL OBSERVATIONS: {total}

DIMENSION BREAKDOWN:
{dimension_lines}

CHANGE TYPE DISTRIBUTION:
{change_type_lines}

TOP OBSERVATIONS ({count} items, medium/high importance):
{items_text}

Synthesize into a bilingual structural summary. \
Identify dominant dimensions, recurring themes, and emerging constraints."""


def _format_prompt(data: PeriodData) -> str:
    dimension_lines = "\n".join(
        f"  {dim}: {count}" for dim, count in
        sorted(data.dimension_breakdown.items(), key=lambda x: -x[1])
    )
    change_type_lines = "\n".join(
        f"  {ct}: {count}" for ct, count in
        sorted(data.change_type_distribution.items(), key=lambda x: -x[1])
    )
    parts: list[str] = []
    for i, item in enumerate(data.items, 1):
        dims = ", ".join(item.dimensions)
        parts.append(
            f"{i}. [{item.importance.upper()}] {item.title}\n"
            f"   Summary: {item.summary}\n"
            f"   Dimensions: {dims} | Change: {item.change_type}"
        )
    items_text = "\n\n".join(parts)
    return _USER_TEMPLATE.format(
        since=data.since[:10],
        until=data.until[:10],
        window_days=data.window_days,
        total=data.total_analyzed,
        dimension_lines=dimension_lines,
        change_type_lines=change_type_lines,
        count=len(data.items),
        items_text=items_text,
    )


# ---------------------------------------------------------------------------
# LLM call + validation
# ---------------------------------------------------------------------------

def _call_llm(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_retries: int,
    timeout: int,
) -> str:
    client = anthropic.Anthropic(api_key=api_key, max_retries=max_retries, timeout=timeout)
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = [ln for ln in text.split("\n") if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc


def _generate_summary(
    data: PeriodData,
    *,
    api_key: str,
    model: str,
    temperature: float = 0.2,
    max_retries: int = 3,
    timeout: int = 90,
) -> tuple[str | None, str | None, str | None]:
    """Return (summary_en, summary_zh, error_msg)."""
    if not data.items:
        return None, None, None

    system_prompt = _SYSTEM_PROMPT.format(window_days=data.window_days)
    user_prompt = _format_prompt(data)

    try:
        raw = _call_llm(
            api_key=api_key, model=model,
            system_prompt=system_prompt, user_prompt=user_prompt,
            temperature=temperature, max_retries=max_retries, timeout=timeout,
        )
    except Exception as exc:
        logger.exception("Periodic summary LLM call failed")
        return None, None, f"api_error: {exc}"

    try:
        parsed = _parse_json(raw)
    except ValueError as exc:
        logger.warning("Failed to parse periodic summary response: %s", exc)
        return None, None, f"parse_error: {exc}"

    # Truncate over-long summaries
    for field_name in ("summary_en", "summary_zh"):
        value = parsed.get(field_name)
        if isinstance(value, str) and len(value) > MAX_SUMMARY_CHARS:
            parsed[field_name] = value[:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0] + "…"

    # Forbidden term check
    for field_name in ("summary_en", "summary_zh"):
        value = parsed.get(field_name, "")
        if isinstance(value, str):
            for term, pattern in _FORBIDDEN_PATTERNS.items():
                if pattern.search(value):
                    return None, None, f"forbidden term '{term}' in {field_name}"

    summary_en = parsed.get("summary_en") or None
    summary_zh = parsed.get("summary_zh") or None
    return summary_en, summary_zh, None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_DIMENSION_SHORT: dict[str, str] = {
    "compute_and_computational_paradigms": "Compute",
    "capital_flows_and_business_models": "Capital",
    "energy_resources_and_physical_constraints": "Energy",
    "technology_adoption_and_industrial_diffusion": "Adoption",
    "governance_regulation_and_societal_response": "Governance",
}


def _render_message(data: PeriodData, summary_en: str | None, summary_zh: str | None) -> str:
    lines: list[str] = []
    lines.append(f"<b>Worldlines — {data.window_days}-Day Structural Summary</b>")
    lines.append(f"<i>{data.since[:10]} → {data.until[:10]}</i>")
    lines.append(f"{data.total_analyzed} observations · {data.item_count} surfaced\n")

    # Dimension breakdown
    if data.dimension_breakdown:
        lines.append("<b>Signal density by dimension:</b>")
        total = sum(data.dimension_breakdown.values()) or 1
        for dim, count in sorted(data.dimension_breakdown.items(), key=lambda x: -x[1]):
            short = _DIMENSION_SHORT.get(dim, dim)
            pct = round(count / total * 100)
            lines.append(f"  {short}: {count} ({pct}%)")
        lines.append("")

    # Change type distribution
    if data.change_type_distribution:
        ct_parts = ", ".join(
            f"{ct}: {n}"
            for ct, n in sorted(data.change_type_distribution.items(), key=lambda x: -x[1])
        )
        lines.append(f"<b>Change types:</b> {ct_parts}\n")

    # Summaries
    if summary_en:
        lines.append(f"<b>Synthesis (EN):</b>\n{summary_en}\n")
    if summary_zh:
        lines.append(f"<b>综合 (中文):</b>\n{summary_zh}\n")

    if not summary_en and not summary_zh:
        lines.append("<i>Summary generation unavailable for this period.</i>")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Query + aggregate
# ---------------------------------------------------------------------------

def _query_analyses(database_path: str, since: str, until: str) -> list[dict]:
    sql = (
        "SELECT a.id AS analysis_id, a.item_id, a.dimensions, a.change_type, "
        "a.time_horizon, a.summary, a.importance, a.analyzed_at, "
        "i.title, i.canonical_link "
        "FROM analyses a "
        "JOIN items i ON a.item_id = i.id "
        "WHERE a.analyzed_at >= ? AND a.analyzed_at < ? "
        "ORDER BY "
        "  CASE a.importance WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
        "  a.analyzed_at DESC"
    )
    with get_connection(database_path) as conn:
        cursor = conn.execute(sql, (since, until))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _aggregate(rows: list[dict], period_label: str, window_days: int,
               since: str, until: str, max_items: int = 30) -> PeriodData:
    dimension_counts: dict[str, int] = {}
    change_type_counts: dict[str, int] = {}

    for row in rows:
        dims = json.loads(row["dimensions"])
        for dim_entry in dims:
            dim_name = dim_entry["dimension"]
            dimension_counts[dim_name] = dimension_counts.get(dim_name, 0) + 1
        ct = row["change_type"]
        change_type_counts[ct] = change_type_counts.get(ct, 0) + 1

    filtered = [r for r in rows if r["importance"] in ("high", "medium")]
    capped = filtered[:max_items]

    items = []
    for row in capped:
        dims = json.loads(row["dimensions"])
        items.append(PeriodItem(
            title=row["title"],
            summary=row["summary"],
            dimensions=[d["dimension"] for d in dims],
            change_type=row["change_type"],
            time_horizon=row["time_horizon"],
            importance=row["importance"],
        ))

    return PeriodData(
        period_label=period_label,
        window_days=window_days,
        since=since,
        until=until,
        total_analyzed=len(rows),
        item_count=len(items),
        dimension_breakdown=dimension_counts,
        change_type_distribution=change_type_counts,
        items=items,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _persist(record: dict, database_path: str) -> None:
    with get_connection(database_path) as conn:
        conn.execute(
            "INSERT INTO periodic_summaries "
            "(id, period_label, window_days, since, until, item_count, "
            "dimension_breakdown, change_type_distribution, "
            "summary_en, summary_zh, message_text, sent_at, telegram_message_ids) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record["id"],
                record["period_label"],
                record["window_days"],
                record["since"],
                record["until"],
                record["item_count"],
                json.dumps(record["dimension_breakdown"]),
                json.dumps(record["change_type_distribution"]),
                record.get("summary_en"),
                record.get("summary_zh"),
                record["message_text"],
                record["sent_at"],
                json.dumps(record["telegram_message_ids"]),
            ),
        )
    logger.info(
        "Periodic summary persisted: period=%s items=%d",
        record["period_label"], record["item_count"],
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_periodic_summary(
    period_label: str,
    window_days: int,
    since: str,
    until: str,
    *,
    database_path: str,
    bot_token: str,
    chat_id: str,
    api_key: str,
    model: str,
    parse_mode: str = "HTML",
    max_retries: int = 3,
) -> PeriodicSummaryResult:
    """Generate and deliver a periodic structural summary.

    Returns PeriodicSummaryResult with delivery_status:
    - "sent"    — delivered successfully
    - "skipped" — period_label already exists (idempotent)
    - "failed"  — Telegram delivery or persistence error
    """
    rows = _query_analyses(database_path, since, until)
    data = _aggregate(rows, period_label, window_days, since, until)

    summary_en, summary_zh, summary_error = _generate_summary(
        data, api_key=api_key, model=model,
    )
    if summary_error:
        logger.warning("Periodic summary LLM failed: %s", summary_error)

    message_text = _render_message(data, summary_en, summary_zh)
    chunks = chunk_message(message_text)

    results = send_messages(
        bot_token, chat_id, chunks, parse_mode=parse_mode, max_retries=max_retries,
    )
    all_ok = all(r.ok for r in results)
    message_ids = [r.message_id for r in results if r.ok]

    record = {
        "id": str(uuid.uuid4()),
        "period_label": period_label,
        "window_days": window_days,
        "since": since,
        "until": until,
        "item_count": data.item_count,
        "dimension_breakdown": data.dimension_breakdown,
        "change_type_distribution": data.change_type_distribution,
        "summary_en": summary_en,
        "summary_zh": summary_zh,
        "message_text": message_text,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "telegram_message_ids": message_ids,
    }

    try:
        _persist(record, database_path)
    except sqlite3.IntegrityError:
        logger.info("Periodic summary already exists for period %s, skipping", period_label)
        return PeriodicSummaryResult(record=None, delivery_status="skipped")

    if not all_ok:
        first_error = next((r.error for r in results if not r.ok), "Unknown error")
        return PeriodicSummaryResult(record=record, delivery_status="failed", error=first_error)

    return PeriodicSummaryResult(record=record, delivery_status="sent")
