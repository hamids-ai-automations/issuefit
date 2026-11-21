"""Deterministic scoring.

Two independent numbers, each 0-100, then one blended fit score. Every point is
attached to a named rule in :data:`RULES` so the CLI can explain itself and the
tests can pin the behaviour. No randomness, no LLM, no hidden weights.
"""

from __future__ import annotations

from .models import IssueSignals, IssueView, Scorecard
from .signals import derive_signals

RULES = {
    "merge_base": 40.0,
    "merge_rate_weight": 25.0,
    "merge_speed": [(24.0, 20.0), (72.0, 12.0), (168.0, 5.0)],
    "merge_low_open_issues": [(50, 8.0), (200, 4.0)],
    "merge_friendly_label": 7.0,
    "resp_push_freshness": [(1.0, 30.0), (3.0, 22.0), (7.0, 14.0), (30.0, 6.0)],
    "resp_maintainer_in_thread": 20.0,
    "resp_has_discussion": 5.0,
    "resp_open_issue_load": [(50, 15.0), (200, 10.0), (800, 5.0)],
    "resp_merge_speed": [(24.0, 20.0), (72.0, 12.0)],
    "resp_merge_speed_slow": 5.0,
}

WEIGHTS = {"merged_pr_probability": 0.50, "maintainer_responsiveness": 0.35, "stack_match": 0.15}
QUALIFIED_THRESHOLD = 60.0
PENALTY_NO_REPRODUCTION = 8.0
PENALTY_STALE_DAYS = 10.0


def _bracket(value: float | None, table: list[tuple[float, float]]) -> float | None:
    if value is None:
        return None
    for limit, points in table:
        if value <= limit:
            return points
    return None


def merged_pr_probability(signals: IssueSignals, issue: IssueView) -> tuple[float, list[str]]:
    """How likely is an outside PR to get merged here? Evidence: this repo's own history."""
    points = RULES["merge_base"]
    reasons = [f"repo baseline {RULES['merge_base']:.0f}"]

    if signals.external_prs:
        contribution = RULES["merge_rate_weight"] * signals.merge_rate
        points += contribution
        reasons.append(
            f"external merges {signals.external_merged}/{signals.external_prs} "
            f"({signals.merge_rate:.0%}) -> +{contribution:.0f}"
        )
    else:
        reasons.append("no external PR history in the sample -> no rate points")

    speed = _bracket(signals.median_merge_hours, RULES["merge_speed"])
    if speed:
        points += speed
        reasons.append(f"median merge {signals.median_merge_hours:.1f}h -> +{speed:.0f}")

    low_load = _bracket(float(issue.open_issues), [(float(a), b) for a, b in RULES["merge_low_open_issues"]])
    if low_load:
        points += low_load
        reasons.append(f"{issue.open_issues} open issues -> +{low_load:.0f}")

    if signals.friendly_labels:
        points += RULES["merge_friendly_label"]
        reasons.append(f"contributor-friendly label {signals.friendly_labels} -> +{RULES['merge_friendly_label']:.0f}")

    return max(0.0, min(100.0, points)), reasons


def maintainer_responsiveness(signals: IssueSignals, issue: IssueView) -> tuple[float, list[str]]:
    """Is anyone awake on the other side of the thread?"""
    points = 0.0
    reasons: list[str] = []

    freshness = _bracket(signals.days_since_push, RULES["resp_push_freshness"])
    if freshness:
        points += freshness
        reasons.append(f"pushed {signals.days_since_push:.1f}d ago -> +{freshness:.0f}")
    else:
        reasons.append("no recent push evidence")

    if signals.maintainer_in_thread:
        points += RULES["resp_maintainer_in_thread"]
        reasons.append(f"maintainer already replied -> +{RULES['resp_maintainer_in_thread']:.0f}")
    if issue.comments:
        points += RULES["resp_has_discussion"]
        reasons.append(f"{issue.comments} comments -> +{RULES['resp_has_discussion']:.0f}")

    load = _bracket(float(issue.open_issues), [(float(a), b) for a, b in RULES["resp_open_issue_load"]])
    if load:
        points += load
        reasons.append(f"open-issue load {issue.open_issues} -> +{load:.0f}")

    speed = _bracket(signals.median_merge_hours, RULES["resp_merge_speed"])
    if speed:
        points += speed
        reasons.append(f"review speed {signals.median_merge_hours:.1f}h -> +{speed:.0f}")
    elif signals.median_merge_hours is not None:
        points += RULES["resp_merge_speed_slow"]
        reasons.append(f"review speed {signals.median_merge_hours:.1f}h -> +{RULES['resp_merge_speed_slow']:.0f}")

    return max(0.0, min(100.0, points)), reasons


def verdict_for(issue: IssueView, signals: IssueSignals, score: float) -> str:
    """Explainable verdict, ordered by how hard the blocker is."""
    if signals.non_actionable_labels:
        return "rejected-not-fixable"
    if issue.competing_open_prs:
        return "blocked-competing-pr"
    if not signals.has_reproduction and "bug" in signals.friendly_labels:
        return "needs-reproduction"
    if score >= QUALIFIED_THRESHOLD:
        return "qualified"
    return "watch"


def score_issue(issue: IssueView, *, signals: IssueSignals | None = None) -> Scorecard:
    """Score one issue. Pass ``signals`` to reuse pre-computed facts."""
    derived = signals or derive_signals(issue)
    probability, merge_reasons = merged_pr_probability(derived, issue)
    responsiveness, resp_reasons = maintainer_responsiveness(derived, issue)
    stack_points = derived.stack_match * 100.0

    blended = (
        WEIGHTS["merged_pr_probability"] * probability
        + WEIGHTS["maintainer_responsiveness"] * responsiveness
        + WEIGHTS["stack_match"] * stack_points
    )
    reasons = [*merge_reasons, *resp_reasons]
    reasons.append(f"stack match {derived.stack_match:.0%} (weight {WEIGHTS['stack_match']:.0%})")
    if derived.has_reproduction:
        reasons.append("thread contains reproduction detail")
    else:
        blended -= PENALTY_NO_REPRODUCTION
        reasons.append(f"no reproduction detail -> -{PENALTY_NO_REPRODUCTION:.0f}")
    if derived.days_since_push is not None and derived.days_since_push > 30:
        blended -= PENALTY_STALE_DAYS
        reasons.append(f"repo untouched for {derived.days_since_push:.0f}d -> -{PENALTY_STALE_DAYS:.0f}")

    total = max(0.0, min(100.0, blended))
    return Scorecard(
        url=issue.url,
        repo=issue.repo,
        number=issue.number,
        title=issue.title,
        merged_pr_probability=probability,
        maintainer_responsiveness=responsiveness,
        stack_match=stack_points,
        score=total,
        verdict=verdict_for(issue, derived, total),
        reasons=reasons,
        signals=derived,
    )
