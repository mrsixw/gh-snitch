# Domain Context & Glossary

Canonical project terminology for **gh-snitch**, grounded in the as-built codebase.

| Term | Meaning | Code / Config Anchor |
|---|---|---|
| **Operative** | A GitHub user handle under surveillance. Must satisfy GitHub's login rules (`1–39` alphanumerics/hyphens, no leading/trailing/double hyphen); malformed handles are screened out before hitting the API. | `config.toml` `[operatives] users`, `api.is_valid_github_login` |
| **Cell / Team** | A named cohort of operatives configured under `[teams.<name>]`. Repeating `--team` produces independent, separately ranked and snapshotted reports in requested order. | `config.toml` `[teams.<name>]`, `cli.py` `--team` |
| **Handler** | The user running `gh-snitch` and managing its configuration and dossiers. | `config.py`, `cli.py` status output |
| **Surveillance Window** | One labelled UTC date range `(label, from_iso, to_iso)` queried against GitHub's GraphQL `contributionsCollection(from, to)`. Driven by `--years`, `--period`, `--last-months`, `--last-quarters`, `--last-weeks`, or `--since`/`--until`. | `api.get_year_ranges`, `api.get_period_range`, `api.get_rolling_*_ranges`, `api.get_custom_range` |
| **Contribution (Headline Total)** | The aggregate count returned by GitHub's `contributionCalendar.totalContributions` for one operative in one surveillance window. Always authoritative for leaderboard ranking, `--min-contributions` filtering, ghost detection, snapshots, and YoY trend indicators. | `api.build_contributions_query`, `report.build_contribution_report` |
| **Contribution Breakdown** | The per-window decomposition of an operative's contributions into four core GitHub scalar categories (`Commits`, `PRs`, `Reviews`, `Issues`) by default, or extended mode (`--breakdown-extended`) adding `Repos`, `Private`, and `Other` (`total - sum(6 categories)`). | `breakdown.ContributionBreakdown`, `api.fetch_contributions_with_breakdown`, `breakdown_ui.render_breakdown_table` |
| **Ghost Operative** | A valid GitHub account with zero contributions across **all** surveilled windows (marked `👻` in TTY or `[ghost]` in plain output). Distinct from a not-found/malformed handle, which is dropped before ranking and reported as an error on stderr. | `report.py` `ghost_usernames`, `cli.py` |
| **Snapshot** | Persisted JSON record of previous headline contribution counts and competition ranks per `(cohort, github_url, context_id)`, used to compute `±` rank deltas and `--delta` diffs. | `snapshot.py`, `report.py` |
| **Redaction** | Deterministic substitution of real GitHub handles with NATO phonetic codenames (`Operative Alpha`, `Bravo`, …) in alphabetical order of username, with OSC 8 hyperlinks suppressed. | `cli.py` `--redact`, `ui.make_operative_cell` |
| **Dossier** | A rendered surveillance report for one cohort (terminal table, breakdown layout, JSON/CSV/Markdown output, chart, or Excel workbook). | `ui.py`, `breakdown_ui.py`, `excel.py` |
