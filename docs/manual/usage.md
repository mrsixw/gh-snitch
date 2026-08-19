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
last-months = 6
last-weeks = 8
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

## Shell completions

gh-snitch ships tab completion for bash, zsh and fish.

```bash
eval "$(gh-snitch completions bash)"   # bash
eval "$(gh-snitch completions zsh)"    # zsh
gh-snitch completions fish | source    # fish
```

`install.sh` installs these permanently into the standard user directories.
Dropping the files into place is only half the job, though: zsh needs the
directory on `fpath` above `compinit`, and bash needs either the
`bash-completion` package or an explicit `source` line. Only fish needs nothing.
The installer detects your shell from `$SHELL` and prints exactly the snippet you
need, falling back to all three when it cannot tell. It only prints — it never
edits your rc files, since it is normally run piped through curl.

## Updating

Once installed, gh-snitch can requisition its own replacement:

```bash
gh-snitch update
```

The swap is atomic — an interrupted download leaves the working binary in place —
and nothing is written unless a newer release actually exists. Re-run
`install.sh` if you also want a refreshed man page.

## Initial Setup

```bash
gh-snitch --init-config
```

Creates a default config at `~/.config/gh-snitch/config.toml`. Edit this file to add your operatives.

## Exporting a Config from the Command Line

Use `--export-config` to generate a ready-to-save TOML config from the operatives and options you specify on the command line. This is the reverse of the config-first flow — useful for bootstrapping a dossier from a one-liner and saving it for later.

```bash
gh-snitch --users alice,bob,carol --export-config
```

```toml
[operatives]
users = ["alice", "bob", "carol"]

[surveillance]
years = 3
# period = "month"      # "week", "month", or "year" — overrides years when set
# last-months = 6       # last 6 calendar months as separate columns
# last-weeks = 8        # last 8 ISO weeks as separate columns

[network]
# github-url = "https://github.example.com"  # omit for github.com

[display]
# format = "table"
# min-contributions = 0
# totals = false
# percent = false
# rank-delta = true
```

CLI overrides are reflected in the output:

```bash
gh-snitch --users alice,bob --years 5 --github-url https://ghe.corp.com --export-config
```

Pipe directly to your config file to save it:

```bash
gh-snitch --users alice,bob,carol --export-config > ~/.config/gh-snitch/config.toml
```

`--export-config` does not require `GITHUB_TOKEN` — it exits before any API calls are made.

## Reviewing Your Config

```bash
gh-snitch --show-config
```

Prints the currently loaded configuration.

## GitHub Enterprise Server

To surveil operatives on a GitHub Enterprise Server instance, set the base URL either in your config file:

```toml
[network]
github-url = "https://github.example.com"
```

Or pass it directly on the command line:

```bash
gh-snitch --github-url https://github.example.com --users alice,bob
```

The GraphQL API endpoint is derived automatically (`<host>/api/graphql`). Your `GH_TOKEN` (or `GITHUB_TOKEN`) should be a personal access token issued by the Enterprise instance.

## Network and GraphQL Failures

gh-snitch retries transient GitHub 502/503/504 responses and connection or
timeout failures three times with exponential backoff. If the signal remains
down, the command exits non-zero with one concise message on stderr.

Contribution sweeps limit concurrent date ranges and divide large operative
cohorts into bounded GraphQL batches. When GitHub reports a resource limit,
gh-snitch retries the rejected operative slice at progressively smaller sizes
and keeps the safer size for the remainder of that range.

GitHub rate limits, unrecoverable resource limits, and other fatal GraphQL
errors are not retried as network failures. The surveillance sweep stops
without rendering partial contribution data or saving a partial snapshot. This
keeps stdout clean for `--format json`, `csv`, and `markdown` consumers.

For recovery advice and example messages, see the troubleshooting guide.

## Inspecting API Usage

Add `--api-stats` to print GraphQL request and rate-limit diagnostics after a
successful sweep:

```bash
gh-snitch --users alice,bob --years 3 --api-stats
```

The stderr summary includes elapsed time, the number of operatives, every
GraphQL POST attempt made by the sweep (including retries), points used and
remaining, and GitHub's reset time. The final rate-limit lookup is excluded from
the reported call count. If GitHub or a GitHub Enterprise Server does not expose
the rate-limit data, the summary reports it as unavailable without failing the
otherwise successful command. Data output remains exclusively on stdout.

## Ghost Operative Detection

Operatives who have recorded zero contributions across **all** surveilled windows are automatically flagged as ghost operatives — dormant assets who have gone dark.

In TTY mode a 👻 indicator is appended to the operative's name in the table. In non-TTY mode (pipes, scripts, `--format csv/json/markdown`) a `[ghost]` annotation is used instead. A summary line is also printed to stderr:

```
👻 1 ghost operative(s) detected — zero activity across all surveilled windows.
```

Ghost detection is automatic and requires no extra flags. It is suppressed in `--delta` mode, where the column shows contribution changes rather than totals.

## Redacting Operative Identities

Use `--redact` to replace real GitHub usernames with NATO phonetic codenames before output is rendered. This lets you share reports publicly without exposing team members' handles.

```bash
gh-snitch --users alice,bob,carol --redact
```

```
#  Operative          2026   2025   2024
1  Operative Bravo     412    380    310
2  Operative Alpha     210    195    180
3  Operative Charlie   170    210    190
```

Codenames are assigned in alphabetical order of the real username, so the mapping is stable across runs:

| Real handle | Codename            |
|-------------|---------------------|
| alice       | Operative Alpha     |
| bob         | Operative Bravo     |
| carol       | Operative Charlie   |

If you have more than 26 operatives the sequence continues as Operative Alpha-2, Bravo-2, etc.

In redact mode:
- OSC 8 terminal hyperlinks are suppressed — no clickable links that could reveal the real handle
- The codename replaces the username in all output formats (`table`, `json`, `csv`, `markdown`, `graph`, `stack`)
- Ghost indicators (`👻` / `[ghost]`) are still shown alongside the codename
- Error messages for not-found operatives also use the codename

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
min-contributions = 10
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

## Rank Change Column

By default, gh-snitch shows a `±` column indicating each operative's rank movement since the previous run (once a snapshot exists). To suppress it:

```bash
gh-snitch --no-rank-delta
```

You can also disable it permanently in your config file:

```toml
[display]
rank-delta = false
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

# Terminal line graph — contribution trend over time
gh-snitch --users alice,bob --years 4 --format graph
```

The `graph` format renders a colour-coded time-series chart in the terminal showing each operative's contribution trend. The X-axis spans the requested years in chronological order and the Y-axis scales to the data. The chart is sized to your terminal width and height automatically.

Note: `--percent` and `--totals` are not applicable in graph format and are silently ignored.

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

Render contribution data as a time-series line graph directly in the terminal:

```bash
gh-snitch --users alice,bob --years 3 --format graph
```

This provides a visual alternative to the ranked table, using `asciichartpy` to generate coloured trend lines.

- **X-axis:** Time Period (chronological)
- **Y-axis:** Contribution count
- **Lines:** One line per operative, colour-coded

It supports all time-period options:

```bash
# Graph of the last 6 months
gh-snitch --users alice,bob --last-months 6 --format graph

# Comparison of named teams
gh-snitch --team platform --delta --format graph
```

**Note:** The `--totals` and `--percent` flags are ignored in graph mode.

## Stacked Bar Chart

Render a vertical stacked bar chart showing each operative's share of the team's total contributions per year:

```bash
gh-snitch --users alice,bob,charlie --years 3 --format stack
```

- **X-axis:** Years (chronological left→right)
- **Y-axis:** Contribution count (scaled to terminal height)
- **Stacking:** Each year's bar is divided into colour-coded segments, one per operative, proportional to their share of that year's total
- **Legend:** Displayed below the chart, left→right matching bottom→top stack order

The stacked view makes it easy to see team trajectory (bar height) and each person's relative contribution (segment size) at a glance. Combine with `--redact` to share publicly:

```bash
gh-snitch --team platform --years 3 --format stack --redact
```

**Note:** `--totals` and `--percent` are not applicable in stack format and are ignored.

## One-Shot Command

Combine flags for a quick ad-hoc sweep without touching your config:

```bash
GITHUB_TOKEN=ghp_... gh-snitch --users alice,bob --years 2 --no-update-check
```
