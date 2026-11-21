"""Signal extraction: each test pins one fact the scores are allowed to depend on."""

from __future__ import annotations

from datetime import UTC, datetime

from issuefit.models import IssueView, PullSample
from issuefit.signals import derive_signals

NOW = datetime(2026, 11, 21, 14, 0, tzinfo=UTC)


def make_issue(**overrides) -> IssueView:
    payload = {
        "repo": "acme/tool",
        "number": 7,
        "title": "mcp server crashes on docker start",
        "body": "Steps to reproduce\n" + "detail " * 40,
        "labels": ["bug", "help wanted"],
        "comments": 3,
        "stars": 900,
        "language": "Python",
        "open_issues": 12,
        "pushed_at": "2026-11-21T10:00:00Z",
        "comment_author_associations": ["CONTRIBUTOR", "MEMBER"],
    }
    payload.update(overrides)
    return IssueView.from_dict(payload)


def test_merge_stats_ignore_insiders_and_unmerged():
    issue = make_issue(
        pulls=[
            PullSample(1, "CONTRIBUTOR", "2026-11-20T00:00:00Z", "2026-11-20T02:00:00Z"),
            PullSample(2, "FIRST_TIME_CONTRIBUTOR", "2026-11-20T00:00:00Z", "2026-11-20T04:00:00Z"),
            PullSample(3, "CONTRIBUTOR", "2026-11-20T00:00:00Z", None),
            PullSample(4, "MEMBER", "2026-11-20T00:00:00Z", "2026-11-20T01:00:00Z"),
        ]
    )
    signals = derive_signals(issue, now=NOW)
    assert signals.external_prs == 3
    assert signals.external_merged == 2
    assert signals.merge_rate == 2 / 3
    assert signals.median_merge_hours == 3.0


def test_no_pull_history_is_zero_rate_not_an_error():
    signals = derive_signals(make_issue(), now=NOW)
    assert signals.merge_rate == 0.0
    assert signals.median_merge_hours is None
    assert signals.external_prs == 0


def test_days_since_push_is_relative_to_now():
    signals = derive_signals(make_issue(pushed_at="2026-11-20T14:00:00Z"), now=NOW)
    assert signals.days_since_push == 1.0


def test_missing_push_date_yields_none():
    signals = derive_signals(make_issue(pushed_at=""), now=NOW)
    assert signals.days_since_push is None


def test_maintainer_detection_requires_insider_association():
    assert derive_signals(make_issue(), now=NOW).maintainer_in_thread is True
    outsider = derive_signals(make_issue(comment_author_associations=["NONE", "CONTRIBUTOR"]), now=NOW)
    assert outsider.maintainer_in_thread is False


def test_labels_are_split_into_friendly_and_non_actionable():
    signals = derive_signals(make_issue(labels=["Bug", "Dependency Dashboard", "stale"]), now=NOW)
    assert signals.friendly_labels == ["bug"]
    assert signals.non_actionable_labels == ["dependency dashboard", "stale"]


def test_reproduction_requires_both_length_and_markers():
    thin = derive_signals(make_issue(body="Steps to reproduce"), now=NOW)
    assert thin.has_reproduction is False
    long_no_markers = derive_signals(make_issue(body="this is a long complaint " * 30), now=NOW)
    assert long_no_markers.has_reproduction is False
    full = derive_signals(make_issue(), now=NOW)
    assert full.has_reproduction is True


def test_stack_match_from_language_and_body():
    python_mcp = derive_signals(make_issue(language="JavaScript"), now=NOW)
    assert python_mcp.stack_match == 1.0  # "mcp" appears in the title
    unrelated = derive_signals(make_issue(title="typo in docs", body="a" * 300, language="PHP"), now=NOW)
    assert unrelated.stack_match == 0.0
