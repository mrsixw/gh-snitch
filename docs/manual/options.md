# Options Reference

| Option | Default | Description |
|---|---|---|
| `--config PATH` | `~/.config/gh-snitch/config.toml` | Path to TOML config file |
| `--users TEXT` | (from config) | Comma-separated GitHub usernames to surveil |
| `--team TEXT` | (from config) | Select a named team defined under `[teams.<name>]`. Overridden by `--users`. |
| `--years INTEGER` | (from config, default 3) | Number of prior complete years to include |
| `--period TEXT` | (from config, default none) | Report on a named window instead of full years: `week` (Mon→today), `month` (1st→today), `year` (Jan 1→today). Overrides `--years`. |
| `--last-months INTEGER` | (from config, default none) | Show the last N calendar months as separate columns. Trend is suppressed. |
| `--last-weeks INTEGER` | (from config, default none) | Show the last N ISO weeks as separate columns. Trend is suppressed. |
| `--since DATE` | CLI only | Start of a custom date range (`YYYY-MM-DD`). End defaults to today. Produces a single column. |
| `--until DATE` | CLI only | End of a custom date range (`YYYY-MM-DD`). Must be used with `--since`. |
| `--github-url URL` | `https://github.com` | GitHub base URL — set to your GitHub Enterprise Server hostname |
| `--min-contributions INTEGER` | `0` (show all) | Hide operatives with fewer than N contributions in the current year |
| `--totals` | off | Add a `Total` column (per-operative sum across all years) and a `Total` footer row (per-year sum across all operatives) |
| `--percent` | off | Annotate each contribution cell with the operative's `(N%)` share of that year's total; percentages are colour-graded in TTY mode |
| `--format TEXT` | `table` (from config) | Output format: `table`, `json`, `csv`, `markdown`, or `graph`. Non-table formats write clean data to stdout and send status messages to stderr. |
| `--no-rank-delta` | off | Hide the `±` rank-change column (rank delta is shown by default) |
| `--delta` | off | Replace the current-year column with `Δ Today` showing the change since the last saved snapshot; green/red-coded |
| `--reset-snapshot` | off | Clear the saved contribution snapshot and exit |
| `--no-trend` | off | Hide the Trend column |
| `--show-config` | off | Print current config and exit |
| `--init-config` | off | Write default config file and exit |
| `--no-update-check` | off | Skip checking for new releases |
| `--version` | — | Show version and exit |
| `--help` | — | Show help and exit |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes | GitHub personal access token (needs `read:user` scope) |
| `NO_COLOR` | No | Set to disable ANSI colour output |
| `XDG_CONFIG_HOME` | No | Override config directory base |
| `XDG_CACHE_HOME` | No | Override cache directory base |

## Config File

The config file uses TOML format with the following sections:

```toml
[operatives]
users = ["alice", "bob"]

[surveillance]
years = 3
# period = "month"      # "week", "month", or "year" — overrides years when set
# last_months = 6       # last 6 calendar months as separate columns
# last_weeks = 8        # last 8 ISO weeks as separate columns

[network]
# github_url = "https://github.example.com"  # omit for github.com

[display]
# format = "table"      # table (default), json, csv, markdown, or graph
# min_contributions = 10  # hide operatives below this threshold
# totals = false           # show Total column and footer row
# percent = false          # annotate cells with (N%) share of year total
# rank_delta = true        # show ± rank-change column (set to false to hide)

# Named teams — select one at runtime with --team <name>
[teams.platform]
users = ["alice", "bob"]

[teams.backend]
users = ["carol", "dave"]
```

CLI flags `--users`, `--team`, `--years`, `--period`, `--last-months`, `--last-weeks`, `--format`, `--github-url`, `--min-contributions`, `--totals`, `--percent`, and `--no-rank-delta` always override config file values.  `--since` and `--until` are command-line only (they encode specific calendar dates and don't belong in a persistent config).
