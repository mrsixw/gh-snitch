# Usage

## Basic Usage

```bash
gh-snitch
```

Reads your config from `~/.config/gh-snitch/config.toml` and displays a contribution surveillance table.

## Surveillance by Username

Override or supplement your config file using `--users`:

```bash
gh-snitch --users octocat,torvalds,gvanrossum
```

## Surveilling a Named Team

Define named teams in your config file under `[teams.<name>]`:

```toml
[teams.platform]
users = ["alice", "bob"]

[teams.backend]
users = ["carol", "dave"]
```

Then select a team at runtime with `--team`:

```bash
gh-snitch --team platform
gh-snitch --team backend
```

This is equivalent to passing `--users alice,bob` (or whichever users are listed under that team), but lets you switch between pre-defined groups without editing config or typing out usernames each time.

If you pass both `--team` and `--users`, `--users` wins — the team is ignored.

If the team name is not found, gh-snitch exits with an error listing the known cells:

```
🚨 Team 'discovery' not found in config. Known cells: backend, platform.
```

## Specifying Year Range

Control how many prior years are included alongside the current year:

```bash
gh-snitch --years 5
```

## Reporting on a Specific Time Window

Instead of fetching full calendar years, use `--period` to focus on a named window:

```bash
# Contributions since the start of this week (Monday)
gh-snitch --users alice,bob --period week

# Contributions this month
gh-snitch --users alice,bob --period month

# Contributions this year (Jan 1 → today)
gh-snitch --users alice,bob --period year
```

When `--period` is set the table shows a single column labelled `This Week`, `This Month`, or `This Year` and the `--years` option is ignored. The Trend column is also suppressed (there is no prior period to compare against).

You can set a default period in your config file:

```toml
[surveillance]
period = "month"
```

## Rolling Monthly or Weekly Columns

Use `--last-months N` or `--last-weeks N` to produce a multi-column view where each column is one calendar month or one ISO week:

```bash
# Last 6 calendar months as separate columns
gh-snitch --users alice,bob --last-months 6

# Last 8 ISO weeks as separate columns
gh-snitch --users alice,bob --last-weeks 8
```

Month columns are labelled `Apr 2026`, `Mar 2026`, … most-recent first.
Week columns are labelled `2026-W15`, `2026-W14`, … most-recent first.

The current (partial) month or week is always the first column.  The Trend column is suppressed because month-to-month and week-to-week comparisons are not annualised.

Set defaults in your config file:

```toml
[surveillance]
last_months = 6
last_weeks = 8
```

## Custom Date Range

Use `--since` and optionally `--until` to query an arbitrary window:

```bash
# Q1 2025
gh-snitch --users alice,bob --since 2025-01-01 --until 2025-03-31

# Everything since a specific date up to today
gh-snitch --users alice,bob --since 2025-06-01
```

The resulting table shows a single column labelled `2025-01-01–2025-03-31` (or `Since 2025-06-01` when no end date is given).  `--until` cannot be used without `--since`.

## Initial Setup

```bash
gh-snitch --init-config
```

Creates a default config at `~/.config/gh-snitch/config.toml`. Edit this file to add your operatives.

## Reviewing Your Config

```bash
gh-snitch --show-config
```

Prints the currently loaded configuration.

## GitHub Enterprise Server

To surveil operatives on a GitHub Enterprise Server instance, set the base URL either in your config file:

```toml
[network]
github_url = "https://github.example.com"
```

Or pass it directly on the command line:

```bash
gh-snitch --github-url https://github.example.com --users alice,bob
```

The GraphQL API endpoint is derived automatically (`<host>/api/graphql`). Your `GITHUB_TOKEN` should be a personal access token issued by the Enterprise instance.

## Filtering Inactive Operatives

Suppress operatives whose current-year contribution count falls below a threshold:

```bash
gh-snitch --min-contributions 10
```

Operatives below the threshold are hidden from the table. A footnote reports how many were suppressed:

```
🔕 3 operative(s) below threshold suppressed.
```

You can also set this in your config file to apply it by default:

```toml
[display]
min_contributions = 10
```

## Delta Mode — Changes Since Last Run

Every successful run saves a snapshot of contribution counts to `~/.cache/gh-snitch/snapshot.json`. Pass `--delta` on a subsequent run to replace the current-year column with the change since the previous snapshot:

```bash
gh-snitch --users alice,bob --delta
```

```
#  Operative     Δ Today   2024   2023
1  alice         +14       380    310
2  bob           +3        195    180
```

- Positive deltas are green, negative are red, zero is dim
- The Trend column is suppressed in delta mode (comparing a delta to a prior full year is meaningless)
- If no prior snapshot exists, absolute counts are shown and a note is printed; the new snapshot is saved for next time

To clear the snapshot:

```bash
gh-snitch --reset-snapshot
```

## Totals and Percentage Breakdown

Show a **Total column** (per-operative sum across all years) and a **Total footer row** (per-year sum across all operatives):

```bash
gh-snitch --totals
```

Annotate each contribution cell with the operative's percentage share of that year's total:

```bash
gh-snitch --percent
```

Combine both for a full breakdown:

```bash
gh-snitch --users alice,bob,charlie --years 2 --totals --percent
```

```
#  Operative     Trend    2025              2024              Total
1  alice         +        412 (52%)         380 (48%)           792
2  bob           =        210 (27%)         195 (25%)           405
3  charlie       -        170 (21%)         210 (27%)           380
   Total                  792               785                1577
```

Percentages are colour-graded in TTY mode. The totals row and total column use neutral styling.

Both options can be set permanently in your config file:

```toml
[display]
totals = true
percent = true
```

## Machine-Readable Output

By default gh-snitch renders a coloured terminal table. Use `--format` to get clean, scriptable output instead:

```bash
# JSON array — one object per operative
gh-snitch --users alice,bob --format json

# CSV — header row + one row per operative
gh-snitch --users alice,bob --format csv

# GitHub-Flavoured Markdown table
gh-snitch --users alice,bob --format markdown
```

All non-`table` formats:
- Write **only data** to stdout (no ANSI codes, no emoji status lines)
- Send status messages (`🔍 Initiating…`, `🗂️ Dossier compiled…`) to **stderr** so pipes stay clean
- Skip the update-check footer

Works with every time-period option:

```bash
# JSON for the last 6 months
gh-snitch --users alice,bob --last-months 6 --format json

# CSV for a custom date range
gh-snitch --users alice,bob --since 2025-01-01 --until 2025-06-30 --format csv

# Markdown for this week
gh-snitch --users alice,bob --period week --format markdown
```

Set a permanent default in your config file:

```toml
[display]
format = "json"
```

## Terminal Graph Output

Render contribution data as a grouped horizontal bar chart directly in the terminal:

```bash
gh-snitch --users alice,bob --years 3 --format graph
```

This provides a visual alternative to the ranked table, using `plotext` to generate coloured bars.

- **Y-axis:** Operatives (ranked descending by current-period count)
- **X-axis:** Contribution count
- **Bars:** Grouped and colour-coded per time period

It supports all time-period options:

```bash
# Graph of the last 6 months
gh-snitch --users alice,bob --last-months 6 --format graph

# Comparison of named teams
gh-snitch --team platform --delta --format graph
```

**Note:** The `--totals` and `--percent` flags are ignored in graph mode.

## One-Shot Command

Combine flags for a quick ad-hoc sweep without touching your config:

```bash
GITHUB_TOKEN=ghp_... gh-snitch --users alice,bob --years 2 --no-update-check
```
