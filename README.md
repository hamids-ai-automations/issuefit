# issuefit

Score a GitHub issue before you spend a weekend on it.

`issuefit` answers three separate questions with evidence from the repository itself, then refuses to
pretend they are one number:

| Output | Question it answers | Evidence used |
| --- | --- | --- |
| `merged_pr_probability` | Will an outside PR actually get merged here? | external merge rate, median time-to-merge, open-issue load, contributor-friendly labels |
| `maintainer_responsiveness` | Is anyone awake on the other side? | days since last push, maintainer reply in this thread, discussion volume, review speed |
| `stack_match` | Is this near my Python / MCP / LLM / FastAPI / Docker stack? | repository language plus keyword evidence in title, body and labels |

The fit score is `0.50 * merged_pr_probability + 0.35 * maintainer_responsiveness + 0.15 * stack_match`,
minus penalties for a thread with no reproduction detail (`-8`) and a repository untouched for more than
30 days (`-10`). It is clamped to 0-100. Every point comes from a named rule in
[`src/issuefit/score.py`](src/issuefit/score.py), and the CLI prints those rules back as `reasons`.

## Verdicts

Ordered by how hard the blocker is, because a high score does not rescue a blocked issue:

1. `rejected-not-fixable` — `dependency dashboard`, `dependencies`, `stale`, `question`, `support` labels.
2. `blocked-competing-pr` — an open PR already cross-references the issue (checked via the timeline API).
3. `needs-reproduction` — labelled `bug` but the thread has no steps/stack trace/expected-vs-actual.
4. `qualified` — score is at or above 60 and none of the blockers apply.
5. `watch` — everything else.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Run the demo (offline, no token)

```bash
issuefit demo
issuefit demo --json
```

The demo scores a bundled fixture whose payload shapes are copied from real GitHub API responses but
whose values are synthetic. It is a demonstration, not a benchmark.

## Score live issues

```bash
export ISSUEFIT_TOKEN=...            # or GITHUB_TOKEN / GH_TOKEN; needs public read, repo read for private repos
issuefit score --repo example-org/ha-mcp --issue 3166
issuefit scan --query "mcp in:title is:issue is:open" --limit 15 --min-score 60 --out scored.json
```

`scan` writes the **full** scored list to `--out` (rejected and blocked issues included) and prints only
what clears `--min-score`, so nothing is silently dropped.

```console
$ issuefit demo
issuefit demo - fixture evaluated as of 2026-11-21T14:00:00+00:00 (no network, no token)

score  verdict               repo                        issue                                                     merge%  resp%  stack%
93.4   qualified             example-org/ha-mcp          #3166 [FEATURE] bulk entity update: optional compact r    94      90     100
76.8   blocked-competing-pr  example-org/agent-sdk       #7052 [Bug]: glob tool returns nothing for patterns wi    73      72     100
67.3   needs-reproduction    example-org/support-desk    #473 Problems connecting FastAPI app to the platform      92      41     100
66.1   rejected-not-fixable  example-org/design-system   #1204 Dependency Dashboard                                85      65      60

Top candidate reasoning:
  - repo baseline 40
  - external merges 6/8 (75%) -> +19
  - median merge 2.0h -> +20
  - 14 open issues -> +8
  - contributor-friendly label ['enhancement'] -> +7
  - pushed 0.1d ago -> +30
  - maintainer already replied -> +20
  - 4 comments -> +5
  - open-issue load 14 -> +15
  - review speed 2.0h -> +20
  - stack match 100% (weight 15%)
  - thread contains reproduction detail
```

## Design notes

- **Two stdlib-only layers.** `signals.py` derives facts, `score.py` turns facts into points. Anything
  that needs the network lives in `github.py`, so the scoring engine is testable as pure functions.
- **Injected clock.** `derive_signals(issue, now=...)` means freshness scoring never depends on the day
  the test runs.
- **Insiders are excluded** from merge-rate evidence (`OWNER`, `MEMBER`, `COLLABORATOR`), otherwise a
  maintainer-only repository looks like it merges everything.
- **No fabricated metrics.** The package ships no claims about accuracy, precision, or stars. Only the
  rule table above.

## Limitations

- A score is a prior, not a prediction. It cannot see whether the requested change conflicts with a
  roadmap the maintainers never wrote down.
- `merged_pr_probability` uses the last 60 closed PRs as its sample; very high-volume repositories with
  mixed policies will look noisier.
- Issues whose body is a screenshot image will score low on reproduction detail.

## Development

```bash
python -m pytest -q
ruff check .
ruff format --check .
```

CI (`.github/workflows/ci.yml`) runs both on Linux and Windows for Python 3.11, 3.12 and 3.13, then
builds the Docker image and executes the demo inside it.

## License

MIT — see [LICENSE](LICENSE).
