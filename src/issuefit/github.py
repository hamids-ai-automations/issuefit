"""Minimal GitHub REST client (stdlib only).

The only job of this module is to assemble an :class:`issuefit.models.IssueView`
from live API responses. All judgement lives in :mod:`issuefit.signals` and
:mod:`issuefit.score`, which is why the scoring tests never touch the network.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .models import IssueView, PullSample

API_ROOT = "https://api.github.com"
USER_AGENT = "issuefit/0.1.0"
PULL_SAMPLE_SIZE = 60


class GitHubError(RuntimeError):
    """Raised when the API call cannot be completed; message is safe to print."""


def _token() -> str:
    for key in ("ISSUEFIT_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(key)
        if value:
            return value.strip()
    raise GitHubError("no token found; set ISSUEFIT_TOKEN (or GITHUB_TOKEN / GH_TOKEN) with repo+public read scopes")


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{API_ROOT}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {_token()}",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https host
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        raise GitHubError(f"HTTP {exc.code} for {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GitHubError(f"network failure for {path}: {exc.reason}") from exc


def search_issues(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """Run an issue search. The query must be URL-safe; GitHub rejects raw punctuation."""
    payload = _get("/search/issues", {"q": query, "sort": "updated", "order": "desc", "per_page": min(limit, 100)})
    return payload.get("items", [])[:limit]


def closed_pulls(repo: str, *, sample: int = PULL_SAMPLE_SIZE) -> list[PullSample]:
    """Recent closed PRs, used solely as evidence of this repo's merge behaviour."""
    items = _get(f"/repos/{repo}/pulls", {"state": "closed", "per_page": min(sample, 100), "sort": "updated"})
    return [
        PullSample(
            number=int(item["number"]),
            author_association=str(item.get("author_association") or ""),
            created_at=str(item.get("created_at") or ""),
            merged_at=item.get("merged_at"),
        )
        for item in items
    ]


def comment_associations(repo: str, number: int) -> list[str]:
    items = _get(f"/repos/{repo}/issues/{number}/comments", {"per_page": 100})
    return [str(item.get("author_association") or "") for item in items]


def competing_pull_requests(repo: str, number: int) -> list[str]:
    """Open PRs that cross-reference this issue and are not yet merged."""
    events = _get(f"/repos/{repo}/issues/{number}/timeline", {"per_page": 100})
    found: list[str] = []
    for event in events:
        source = (event.get("source") or {}).get("issue") or {}
        if not source.get("pull_request"):
            continue
        if source.get("state") == "open" and source.get("html_url") not in found:
            found.append(str(source["html_url"]))
    return found


def build_view(issue_payload: dict[str, Any], *, repo: str, with_pulls: bool = True) -> IssueView:
    """Assemble one IssueView from a search-API issue plus repository context."""
    repo_payload = _get(f"/repos/{repo}")
    number = int(issue_payload["number"])
    return IssueView(
        repo=repo,
        number=number,
        title=str(issue_payload.get("title") or ""),
        body=str(issue_payload.get("body") or ""),
        labels=[str(item.get("name")) for item in issue_payload.get("labels") or []],
        comments=int(issue_payload.get("comments") or 0),
        created_at=str(issue_payload.get("created_at") or ""),
        updated_at=str(issue_payload.get("updated_at") or ""),
        stars=int(repo_payload.get("stargazers_count") or 0),
        language=str(repo_payload.get("language") or ""),
        open_issues=int(repo_payload.get("open_issues_count") or 0),
        pushed_at=str(repo_payload.get("pushed_at") or ""),
        comment_author_associations=comment_associations(repo, number),
        competing_open_prs=competing_pull_requests(repo, number),
        pulls=closed_pulls(repo) if with_pulls else [],
    )


def repo_from_url(url: str) -> str:
    """Extract ``owner/name`` from an api or html issue URL."""
    if "/repos/" in url:
        return url.split("/repos/", 1)[1].rsplit("/issues/", 1)[0]
    parts = url.split("github.com/", 1)[-1].split("/")
    return f"{parts[0]}/{parts[1]}"
