"""issuefit - score GitHub issues for contribution fit.

Public API:
    from issuefit import score_issue, IssueSignals, Scorecard
"""

from __future__ import annotations

from .models import IssueSignals, IssueView, PullSample, Scorecard
from .score import score_issue

__all__ = ["IssueSignals", "IssueView", "PullSample", "Scorecard", "score_issue"]
__version__ = "0.1.0"
