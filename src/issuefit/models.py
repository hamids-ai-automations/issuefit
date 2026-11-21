"""Plain dataclasses for the inputs and outputs of the scoring engine.

Everything here is transport-agnostic: the same objects can be built from live
GitHub API payloads (:mod:`issuefit.github`) or from a recorded fixture, which is
what makes the scores unit-testable without a network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# GitHub author_association values that mean "already trusted by the repository".
INSIDER_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
# Labels that signal a maintainer wants outside help.
FRIENDLY_LABELS = {
    "good first issue",
    "help wanted",
    "docs",
    "documentation",
    "bug",
    "enhancement",
    "easy",
    "beginner",
}
# Labels that mean the thread is not actionable code work.
NON_ACTIONABLE_LABELS = {"dependency dashboard", "dependencies", "stale", "wontfix", "question", "support"}


def parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp as GitHub emits it (``2026-11-21T13:39:21Z``)."""
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


@dataclass(slots=True)
class PullSample:
    """One closed pull request used as evidence of merge behaviour."""

    number: int
    author_association: str
    created_at: str
    merged_at: str | None

    @property
    def external(self) -> bool:
        return self.author_association.upper() not in INSIDER_ASSOCIATIONS

    @property
    def merged(self) -> bool:
        return bool(self.merged_at)

    def hours_to_merge(self) -> float | None:
        created, merged = parse_dt(self.created_at), parse_dt(self.merged_at)
        if not created or not merged:
            return None
        return max(0.0, (merged - created).total_seconds() / 3600.0)


@dataclass(slots=True)
class IssueView:
    """The issue under evaluation plus the repository context around it."""

    repo: str
    number: int
    title: str
    body: str = ""
    labels: list[str] = field(default_factory=list)
    comments: int = 0
    created_at: str = ""
    updated_at: str = ""
    stars: int = 0
    language: str = ""
    open_issues: int = 0
    pushed_at: str = ""
    comment_author_associations: list[str] = field(default_factory=list)
    competing_open_prs: list[str] = field(default_factory=list)
    pulls: list[PullSample] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://github.com/{self.repo}/issues/{self.number}"

    def lower_labels(self) -> set[str]:
        return {label.strip().lower() for label in self.labels}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> IssueView:
        return cls(
            repo=str(payload.get("repo", "")),
            number=int(payload.get("number", 0)),
            title=str(payload.get("title", "")),
            body=str(payload.get("body") or ""),
            labels=[str(item) for item in payload.get("labels") or []],
            comments=int(payload.get("comments") or 0),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
            stars=int(payload.get("stars") or 0),
            language=str(payload.get("language") or ""),
            open_issues=int(payload.get("open_issues") or 0),
            pushed_at=str(payload.get("pushed_at") or ""),
            comment_author_associations=[str(a) for a in payload.get("comment_author_associations") or []],
            competing_open_prs=[str(p) for p in payload.get("competing_open_prs") or []],
            pulls=[
                item
                if isinstance(item, PullSample)
                else PullSample(
                    number=int(item.get("number", 0)),
                    author_association=str(item.get("author_association") or ""),
                    created_at=str(item.get("created_at") or ""),
                    merged_at=item.get("merged_at"),
                )
                for item in payload.get("pulls") or []
            ],
        )


@dataclass(slots=True)
class IssueSignals:
    """Normalised, human-checkable facts derived from an :class:`IssueView`."""

    merge_rate: float
    median_merge_hours: float | None
    external_prs: int
    external_merged: int
    days_since_push: float | None
    maintainer_in_thread: bool
    friendly_labels: list[str]
    non_actionable_labels: list[str]
    body_chars: int
    has_reproduction: bool
    stack_match: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "merge_rate": round(self.merge_rate, 3),
            "median_merge_hours": None if self.median_merge_hours is None else round(self.median_merge_hours, 1),
            "external_prs": self.external_prs,
            "external_merged": self.external_merged,
            "days_since_push": None if self.days_since_push is None else round(self.days_since_push, 1),
            "maintainer_in_thread": self.maintainer_in_thread,
            "friendly_labels": self.friendly_labels,
            "non_actionable_labels": self.non_actionable_labels,
            "body_chars": self.body_chars,
            "has_reproduction": self.has_reproduction,
            "stack_match": round(self.stack_match, 3),
        }


@dataclass(slots=True)
class Scorecard:
    """The scored verdict for one issue."""

    url: str
    repo: str
    number: int
    title: str
    merged_pr_probability: float
    maintainer_responsiveness: float
    stack_match: float
    score: float
    verdict: str
    reasons: list[str]
    signals: IssueSignals

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "repo": self.repo,
            "number": self.number,
            "title": self.title,
            "merged_pr_probability": round(self.merged_pr_probability, 1),
            "maintainer_responsiveness": round(self.maintainer_responsiveness, 1),
            "stack_match": round(self.stack_match, 1),
            "score": round(self.score, 1),
            "verdict": self.verdict,
            "reasons": self.reasons,
            "signals": self.signals.as_dict(),
        }
