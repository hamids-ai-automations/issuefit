"""Scoring behaviour: monotonicity, explainability and verdict ordering."""

from __future__ import annotations

from datetime import UTC, datetime

from issuefit.models import IssueView, PullSample
from issuefit.score import QUALIFIED_THRESHOLD, score_issue
from issuefit.signals import derive_signals

NOW = datetime(2026, 11, 21, 14, 0, tzinfo=UTC)


def healthy(**overrides) -> IssueView:
    payload = {
        "repo": "acme/tool",
        "number": 42,
        "title": "add retry budget to docker client",
        "body": "Expected: bounded retries.\nActual: unbounded.\nSteps to reproduce\n" + "x " * 200,
        "labels": ["enhancement", "help wanted"],
        "comments": 3,
        "stars": 4000,
        "language": "Python",
        "open_issues": 15,
        "pushed_at": "2026-11-21T10:00:00Z",
        "comment_author_associations": ["MEMBER"],
        "pulls": [PullSample(i, "CONTRIBUTOR", "2026-11-20T00:00:00Z", "2026-11-20T02:00:00Z") for i in range(1, 6)],
    }
    payload.update(overrides)
    return IssueView.from_dict(payload)


def test_healthy_issue_qualifies():
    card = score_issue(healthy(), signals=derive_signals(healthy(), now=NOW))
    assert card.verdict == "qualified"
    assert card.score >= QUALIFIED_THRESHOLD
    assert 0 <= card.merged_pr_probability <= 100
    assert 0 <= card.maintainer_responsiveness <= 100


def test_competing_pr_blocks_even_high_scores():
    card = score_issue(
        healthy(competing_open_prs=["https://github.com/acme/tool/pull/43"]),
        signals=derive_signals(healthy(competing_open_prs=["https://github.com/acme/tool/pull/43"]), now=NOW),
    )
    assert card.verdict == "blocked-competing-pr"
    assert card.score >= QUALIFIED_THRESHOLD  # the number stays, the verdict changes


def test_dependency_dashboard_is_rejected_regardless_of_score():
    issue = healthy(labels=["dependencies", "dependency dashboard"], open_issues=1)
    card = score_issue(issue, signals=derive_signals(issue, now=NOW))
    assert card.verdict == "rejected-not-fixable"


def test_bug_without_reproduction_needs_reproduction():
    issue = healthy(labels=["bug"], body="it does not work")
    card = score_issue(issue, signals=derive_signals(issue, now=NOW))
    assert card.verdict == "needs-reproduction"


def test_score_is_monotonic_in_merge_rate():
    low = healthy(pulls=[PullSample(1, "CONTRIBUTOR", "2026-11-20T00:00:00Z", None)])
    high = healthy()
    low_card = score_issue(low, signals=derive_signals(low, now=NOW))
    high_card = score_issue(high, signals=derive_signals(high, now=NOW))
    assert high_card.merged_pr_probability > low_card.merged_pr_probability
    assert high_card.score > low_card.score


def test_stale_repo_loses_points():
    stale = healthy(pushed_at="2026-08-01T00:00:00Z")
    fresh = healthy()
    stale_card = score_issue(stale, signals=derive_signals(stale, now=NOW))
    fresh_card = score_issue(fresh, signals=derive_signals(fresh, now=NOW))
    assert stale_card.maintainer_responsiveness < fresh_card.maintainer_responsiveness
    assert any("untouched" in reason for reason in stale_card.reasons)


def test_every_score_has_reasons_and_serialises():
    card = score_issue(healthy(), signals=derive_signals(healthy(), now=NOW))
    assert len(card.reasons) >= 5
    payload = card.as_dict()
    assert payload["verdict"] == "qualified"
    assert payload["signals"]["external_prs"] == 5
    assert payload["url"].endswith("/issues/42")


def test_scores_are_clamped_to_0_100():
    monster = healthy(
        open_issues=1,
        comments=50,
        pulls=[PullSample(i, "CONTRIBUTOR", "2026-11-21T00:00:00Z", "2026-11-21T00:10:00Z") for i in range(1, 40)],
    )
    card = score_issue(monster, signals=derive_signals(monster, now=NOW))
    assert card.merged_pr_probability <= 100
    assert card.maintainer_responsiveness <= 100
    assert card.score <= 100


def test_score_is_deterministic():
    first = score_issue(healthy(), signals=derive_signals(healthy(), now=NOW)).as_dict()
    second = score_issue(healthy(), signals=derive_signals(healthy(), now=NOW)).as_dict()
    assert first == second
