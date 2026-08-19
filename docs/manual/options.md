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
| `--format TEXT` | `table` (from config) | Output format: `table`, `json`, `csv`, `markdown`, `graph`, or `stack`. Non-table formats write clean data to stdout and send status messages to stderr. |
| `--no-rank-delta` | off | Hide the `±` rank-change column (rank delta is shown by default) |
| `--redact` | off | Replace operative usernames with NATO phonetic codenames (Operative Alpha, Bravo, …); suppresses hyperlinks. Codenames are assigned in alphabetical order of the real username and are deterministic across runs. Works with all output formats. |
| `--delta` | off | Replace the current-year column with `Δ Today` showing the change since the last saved snapshot; green/red-coded |
| `--reset-snapshot` | off | Clear the saved contribution snapshot and exit |
| `--no-trend` | off | Hide the Trend column |
| `--show-config` | off | Print current config and exit |
| `--export-config` | off | Print a TOML config scaffolded from the current CLI arguments and exit. Reflects `--users`, `--years`, `--github-url` overrides. Does not require `GITHUB_TOKEN`. Pipe to a file to save: `gh-snitch --users alice,bob --export-config > config.toml` |
| `--init-config` | off | Write default config file and exit |
| `--no-update-check` | off | Skip checking for new releases. Also honoured via `GH_SNITCH_NO_UPDATE_CHECK`, or the `no_update_check` config key — see [Silencing the update check](#silencing-the-update-check) |
| `--api-stats` | off | Print GraphQL request counts, points remaining and used, and the rate-limit reset time to stderr after output. The diagnostics lookup is best-effort and never changes a successful run into a failure. |
| `--version` | — | Show version and exit |
| `--help` | — | Show help and exit |

## Commands

Alongside the options above, gh-snitch has two subcommands. Both run before any
config loading or token validation, so they work on a fresh machine with nothing
set up.

### `completions SHELL`

Print the tab-completion script for `SHELL` to stdout and exit. `SHELL` must be
one of `bash`, `zsh`, or `fish`.

```bash
gh-snitch completions bash
gh-snitch completions zsh
gh-snitch completions fish | source
```

`install.sh` installs these permanently and prints the one line your shell needs
to load them — dropping the files into place is not enough on its own. See
[Usage → Shell completions](usage.md#shell-completions).

### `update`

Download the latest release and replace the running executable with it.

```bash
gh-snitch update
```

The replacement is atomic, so an interrupted download leaves the working binary
in place. Nothing is written unless a newer release actually exists.

The man page is not refreshed — re-run `install.sh` for that. Completion scripts
need no refresh: they call back into the binary, so they follow it automatically.

Not to be confused with `--update-config`, which merges new keys into your config
file, or `--no-update-check`, which silences the passive "new intelligence
package" notice.

## Silencing the update check

Three ways, in increasing order of permanence:

```bash
# Just this run
gh-snitch --users alice --no-update-check

# This shell session, or CI (useful in scripts)
export GH_SNITCH_NO_UPDATE_CHECK=1
```

```toml
# Permanently, in your config file
[updates]
no_update_check = true
```

Any one of the three switching the check off is enough; none of them can switch
it back on.

Like `NO_COLOR`, `GH_SNITCH_NO_UPDATE_CHECK` is resolved by presence: any
non-empty value disables the check, and only unset or empty leaves it enabled.
The value is never parsed, so a stray `GH_SNITCH_NO_UPDATE_CHECK=maybe` in a
shell profile is harmless rather than fatal.

## Automatic Indicators

Some behaviours are always-on and require no flag:

| Indicator | Condition | Output |
|---|---|---|
| 👻 / `[ghost]` | Operative has zero contributions across **all** surveilled windows | Appended to name in the Operative column; summary line on stderr |

Ghost detection is suppressed in `--delta` mode.

Network retries and GraphQL error handling are also automatic. Transient
502/503/504 and connection failures receive three retries with backoff.
Contribution sweeps use bounded range concurrency; resource-limited queries are
retried with progressively smaller operative batches. Rate limits,
unrecoverable resource limits, and other fatal GraphQL errors exit non-zero with
a concise message on stderr; structured stdout is never populated with partial
surveillance data.

## API Diagnostics

Use `--api-stats` to append a spy-themed GraphQL diagnostics summary to stderr:

```bash
gh-snitch --users alice,bob --years 3 --api-stats
```

```text
🛰️  API intelligence
  Total elapsed:    1.42s
  Operatives:       2
  GraphQL calls:    4
  GQL rate limit:   4987 points remaining
  GQL points used:  13
  GQL rate resets:  2026-07-17T13:00:00Z
```

The call count includes retries but excludes the final diagnostics lookup.
Fields that are unavailable on a GitHub Enterprise Server endpoint are replaced
by `GQL rate status: unavailable`. All diagnostics go to stderr so stdout stays
safe for structured output.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GH_TOKEN` | Yes* | GitHub personal access token (needs `read:user` scope). Takes precedence over `GITHUB_TOKEN` if both are set. |
| `GITHUB_TOKEN` | Yes* | GitHub personal access token (needs `read:user` scope). Used if `GH_TOKEN` is not set. |
| `NO_COLOR` | No | Set to disable ANSI colour output |
| `XDG_CONFIG_HOME` | No | Override config directory base |
| `XDG_CACHE_HOME` | No | Override cache directory base |

\* One of `GH_TOKEN` or `GITHUB_TOKEN` is required.

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
# format = "table"      # table (default), json, csv, markdown, graph, or stack
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
