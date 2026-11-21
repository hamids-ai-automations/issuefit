"""Client plumbing tests that stay offline: URL parsing and payload assembly."""

from __future__ import annotations

import pytest

from issuefit import github


def test_repo_from_api_url():
    url = "https://api.github.com/repos/example-org/ha-mcp/issues/3166"
    assert github.repo_from_url(url) == "example-org/ha-mcp"


def test_repo_from_html_url():
    assert github.repo_from_url("https://github.com/example-org/ha-mcp/issues/3166") == "example-org/ha-mcp"


def test_missing_token_raises_actionable_error(monkeypatch):
    for key in ("ISSUEFIT_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: pytest.fail("must not hit the network"))
    with pytest.raises(github.GitHubError, match="ISSUEFIT_TOKEN"):
        github.search_issues("mcp in:title")


def test_build_view_maps_search_payload(monkeypatch):
    issue_payload = {
        "number": 3166,
        "title": "bulk entity update",
        "body": "b" * 400,
        "labels": [{"name": "enhancement"}],
        "comments": 4,
        "created_at": "2026-11-20T22:39:20Z",
        "updated_at": "2026-11-21T13:33:20Z",
    }
    repo_payload = {
        "stargazers_count": 8031,
        "language": "Python",
        "open_issues_count": 14,
        "pushed_at": "2026-11-21T10:57:21Z",
    }
    monkeypatch.setattr(github, "_token", lambda: "fake")
    monkeypatch.setattr(github, "comment_associations", lambda repo, number: ["MEMBER"])
    monkeypatch.setattr(github, "competing_pull_requests", lambda repo, number: [])
    monkeypatch.setattr(github, "closed_pulls", lambda repo, sample=github.PULL_SAMPLE_SIZE: [])
    monkeypatch.setattr(github, "_get", lambda path, params=None: repo_payload if path.endswith("/ha-mcp") else [])
    view = github.build_view(issue_payload, repo="example-org/ha-mcp")
    assert view.repo == "example-org/ha-mcp"
    assert view.labels == ["enhancement"]
    assert view.stars == 8031
    assert view.comment_author_associations == ["MEMBER"]
    assert view.url.endswith("/issues/3166")
