"""Command line entry point: ``issuefit demo | scan | score``."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from importlib import resources
from typing import Any

from . import github
from .models import IssueView, parse_dt
from .score import score_issue
from .signals import derive_signals

EXIT_OK = 0
EXIT_USAGE = 2


def load_fixture(name: str = "demo_scan.json") -> dict[str, Any]:
    """Read a bundled fixture, so ``issuefit demo`` works with no token and no network."""
    text = resources.files("issuefit.fixtures").joinpath(name).read_text(encoding="utf-8")
    return json.loads(text)


def _columns(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    widths = [max(len(row[i]) for row in [*rows]) for i in range(len(rows[0]))]
    return "\n".join("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip() for row in rows)


def _table(cards) -> str:
    rows = [["score", "verdict", "repo", "issue", "merge%", "resp%", "stack%"]]
    for card in cards:
        rows.append(
            [
                f"{card.score:.1f}",
                card.verdict,
                card.repo,
                f"#{card.number} {card.title[:52]}",
                f"{card.merged_pr_probability:.0f}",
                f"{card.maintainer_responsiveness:.0f}",
                f"{card.stack_match:.0f}",
            ]
        )
    return _columns(rows)


def _score_payload(payload: dict[str, Any], *, now: datetime | None) -> Any:
    issue = IssueView.from_dict(payload)
    return score_issue(issue, signals=derive_signals(issue, now=now))


def cmd_demo(args: argparse.Namespace) -> int:
    fixture = load_fixture(args.fixture)
    now = parse_dt(fixture.get("as_of")) or datetime.now(UTC)
    cards = sorted((_score_payload(item, now=now) for item in fixture["issues"]), key=lambda c: -c.score)
    if args.json:
        print(json.dumps([card.as_dict() for card in cards], indent=2))
        return EXIT_OK
    print(f"issuefit demo - fixture evaluated as of {now.isoformat()} (no network, no token)\n")
    print(_table(cards))
    print("\nTop candidate reasoning:")
    best = cards[0]
    for reason in best.reasons:
        print(f"  - {reason}")
    print(f"\nVerdict: {best.verdict} ({best.url})")
    credible = [card for card in cards if card.verdict == "qualified"]
    print(f"\n{len(credible)} of {len(cards)} fixture issues qualify; the rest are blocked, rejected or need a repro.")
    return EXIT_OK


def cmd_score(args: argparse.Namespace) -> int:
    issues = github.search_issues(f"repo:{args.repo} {args.issue}", limit=5)
    match = next((item for item in issues if int(item["number"]) == args.issue), None)
    if match is None:
        print(f"issue {args.repo}#{args.issue} not found via search API", file=sys.stderr)
        return EXIT_USAGE
    card = score_issue(github.build_view(match, repo=args.repo))
    if args.json:
        print(json.dumps(card.as_dict(), indent=2))
        return EXIT_OK
    print(_table([card]))
    print()
    for reason in card.reasons:
        print(f"  - {reason}")
    return EXIT_OK


def cmd_scan(args: argparse.Namespace) -> int:
    items = github.search_issues(args.query, limit=args.limit)
    cards = []
    for item in items:
        repo = str(item["repository_url"]).split("/repos/", 1)[-1]
        cards.append(score_issue(github.build_view(item, repo=repo)))
    cards.sort(key=lambda card: -card.score)
    keep = [card for card in cards if card.score >= args.min_score]

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "query": args.query,
                    "scored": len(cards),
                    "kept": len(keep),
                    "results": [card.as_dict() for card in cards],
                },
                handle,
                indent=2,
            )
    if args.json:
        print(json.dumps([card.as_dict() for card in keep], indent=2))
        return EXIT_OK
    print(f"scored {len(cards)} issues from query {args.query!r}; {len(keep)} at or above {args.min_score}")
    print(_table(keep) if keep else "no issue reached the minimum score")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="issuefit", description="Score GitHub issues for contribution fit.")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="score the bundled fixture offline (no token needed)")
    demo.add_argument("--fixture", default="demo_scan.json")
    demo.add_argument("--json", action="store_true")
    demo.set_defaults(func=cmd_demo)

    score = sub.add_parser("score", help="score one live issue")
    score.add_argument("--repo", required=True, help="owner/name")
    score.add_argument("--issue", type=int, required=True)
    score.add_argument("--json", action="store_true")
    score.set_defaults(func=cmd_score)

    scan = sub.add_parser("scan", help="score the results of an issue search query")
    scan.add_argument("--query", required=True, help="GitHub issue search query, e.g. 'mcp in:title is:issue is:open'")
    scan.add_argument("--limit", type=int, default=10)
    scan.add_argument("--min-score", type=float, default=60.0)
    scan.add_argument("--out", help="write the full scored list to this JSON file")
    scan.add_argument("--json", action="store_true")
    scan.set_defaults(func=cmd_scan)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except github.GitHubError as exc:
        print(f"issuefit: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
