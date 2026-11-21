"""CLI contract: the demo must run offline and emit parseable JSON."""

from __future__ import annotations

import json

from issuefit.cli import main


def test_demo_table_runs_without_token(capsys, monkeypatch):
    monkeypatch.delenv("ISSUEFIT_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "issuefit demo" in out
    assert "verdict" in out
    assert "qualified" in out


def test_demo_json_is_sorted_and_complete(capsys):
    assert main(["demo", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 4
    scores = [item["score"] for item in payload]
    assert scores == sorted(scores, reverse=True)
    for item in payload:
        assert set(item) >= {"url", "repo", "verdict", "score", "reasons", "signals"}
        assert isinstance(item["reasons"], list) and item["reasons"]


def test_demo_classifies_each_fixture_issue(capsys):
    assert main(["demo", "--json"]) == 0
    payload = {item["repo"]: item for item in json.loads(capsys.readouterr().out)}
    assert payload["example-org/ha-mcp"]["verdict"] == "qualified"
    assert payload["example-org/agent-sdk"]["verdict"] == "blocked-competing-pr"
    assert payload["example-org/design-system"]["verdict"] == "rejected-not-fixable"
    assert payload["example-org/support-desk"]["verdict"] == "needs-reproduction"


def test_unknown_subcommand_exits_with_usage_error():
    try:
        main(["nonsense"])
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover - argparse always exits
        raise AssertionError("expected SystemExit")
