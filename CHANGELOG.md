# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com)
and the project adheres to [Semantic Versioning](https://semver.org).

## [0.1.0] - 2026-11-21

### Added

- `merged_pr_probability`, `maintainer_responsiveness` and `stack_match` scores built from external merge rate,
  median time-to-merge, repository freshness, maintainer replies, open-issue load and label evidence.
- Verdict ladder: `rejected-not-fixable` > `blocked-competing-pr` > `needs-reproduction` > `qualified` > `watch`.
- `issuefit demo` (offline fixture), `issuefit score`, `issuefit scan`, all with `--json`.
- GitHub client on the standard library only: issue search, closed-PR sample, comment associations, timeline
  cross-references.
- 25 tests: 8 signal tests, 9 scoring tests, 4 CLI contract tests and 4 client tests; CI runs Linux + Windows on
  Python 3.11-3.13, then builds and runs the Docker image.
