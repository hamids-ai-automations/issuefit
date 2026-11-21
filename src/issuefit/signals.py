"""Turn an :class:`IssueView` into facts a human can check in ten seconds."""

from __future__ import annotations

import statistics
from datetime import UTC, datetime

from .models import FRIENDLY_LABELS, NON_ACTIONABLE_LABELS, IssueSignals, IssueView, parse_dt

# Terms that indicate a thread someone can actually reproduce or reason about.
REPRODUCTION_MARKERS = (
    "steps to reproduce",
    "reproduce",
    "repro",
    "traceback",
    "stack trace",
    "```",
    "expected",
    "actual",
    "version",
)

STACK_HINTS = {
    "python": 1.0,
    "fastapi": 1.0,
    "docker": 0.9,
    "mcp": 1.0,
    "rag": 1.0,
    "llm": 0.9,
    "agent": 0.9,
    "pydantic": 0.9,
    "typescript": 0.6,
    "javascript": 0.6,
    "go": 0.6,
    "rust": 0.6,
}


def _days_since(moment: str, *, now: datetime) -> float | None:
    parsed = parse_dt(moment)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    delta = now - parsed
    return max(0.0, delta.total_seconds() / 86400.0)


def _merge_stats(pulls) -> tuple[float, float | None, int, int]:
    external = [p for p in pulls if p.external]
    if not external:
        return 0.0, None, 0, 0
    merged = [p for p in external if p.merged]
    rate = len(merged) / len(external)
    hours = [h for h in (p.hours_to_merge() for p in merged) if h is not None]
    median = statistics.median(hours) if hours else None
    return rate, median, len(external), len(merged)


def _has_reproduction(body: str) -> bool:
    text = body.lower()
    if len(text.strip()) < 200:
        return False
    return any(marker in text for marker in REPRODUCTION_MARKERS)


def _stack_match(issue: IssueView) -> float:
    """0.0-1.0 estimate of how close the issue is to a Python/MCP/LLM/FastAPI stack."""
    language = issue.language.strip().lower()
    score = STACK_HINTS.get(language, 0.0)
    haystack = " ".join([issue.title.lower(), issue.body.lower(), *issue.lower_labels()])
    hits = [weight for key, weight in STACK_HINTS.items() if key in haystack]
    if hits:
        score = max(score, max(hits))
    return min(1.0, score)


def derive_signals(issue: IssueView, *, now: datetime | None = None) -> IssueSignals:
    """Compute every fact the scoring engine is allowed to use."""
    reference = now or datetime.now(UTC)
    rate, median, external_prs, external_merged = _merge_stats(issue.pulls)
    labels = issue.lower_labels()
    return IssueSignals(
        merge_rate=rate,
        median_merge_hours=median,
        external_prs=external_prs,
        external_merged=external_merged,
        days_since_push=_days_since(issue.pushed_at, now=reference),
        maintainer_in_thread=any(
            assoc.upper() in {"OWNER", "MEMBER", "COLLABORATOR"} for assoc in issue.comment_author_associations
        ),
        friendly_labels=sorted(labels & FRIENDLY_LABELS),
        non_actionable_labels=sorted(labels & NON_ACTIONABLE_LABELS),
        body_chars=len(issue.body.strip()),
        has_reproduction=_has_reproduction(issue.body),
        stack_match=_stack_match(issue),
    )
