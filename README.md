# gh-snitch 🕵️

**Spy-themed GitHub contribution surveillance tool.**

Monitor your operatives' GitHub contribution counts across years — rendered as a ranked, colour-graded table in your terminal.

## Installation

```bash
curl -sSL https://raw.githubusercontent.com/mrsixw/gh-snitch/main/install.sh | bash
```

The installer also drops in the man page and bash/zsh/fish completions, and
prints the one line your shell needs to activate them. Once installed,
`gh-snitch update` pulls down later releases without re-running the installer.

Or build and install from source:

```bash
git clone https://github.com/mrsixw/gh-snitch.git
cd gh-snitch
make build
sudo make install
```

*(Note: This compiles and installs the binary locally from your source checkout. If you want to download and install a pre-compiled binary instantly instead, use the `install.sh` script above).*

By default, this installs the executable to `/usr/local/bin`. You can customize the installation prefix using the `PREFIX` variable:

```bash
make install PREFIX=$HOME/.local
```

To uninstall:

```bash
sudo make uninstall
```

If installed with a custom `PREFIX`:

```bash
make uninstall PREFIX=$HOME/.local
```

## Quick Start

1. Set your GitHub token:
   ```bash
   export GITHUB_TOKEN=ghp_...
   ```
   (`GH_TOKEN` also works, and takes precedence if both are set — handy if you already use it for the `gh` CLI.)

2. Initialise your config:
   ```bash
   gh-snitch --init-config
   ```

3. Edit `~/.config/gh-snitch/config.toml` to add operatives:
   ```toml
   [operatives]
   users = ["octocat", "torvalds"]

   [surveillance]
   years = 3
   ```

4. Run surveillance:
   ```bash
   gh-snitch
   ```

## Options

| Flag | Description |
|---|---|
| `--users` | Comma-separated usernames (overrides config) |
| `--team` | Select a named team from config; repeat the flag for multiple independent team reports. Overridden by `--users` |
| `--years` | Number of prior years (overrides config) |
| `--period` | Report on a named window: `week`, `month`, or `year` (overrides `--years`) |
| `--last-months N` | Show last N calendar months as separate columns |
| `--last-quarters N` | Show last N calendar quarters as separate columns, including the current quarter-to-date |
| `--last-weeks N` | Show last N ISO weeks as separate columns |
| `--since DATE` | Start of a custom date range (`YYYY-MM-DD`); end defaults to today |
| `--until DATE` | End of a custom date range (`YYYY-MM-DD`); requires `--since` |
| `--min-contributions` | Hide operatives below this contribution count |
| `--totals` | Add a Total column per operative and a Total footer row |
| `--percent` | Annotate each cell with the operative's `(N%)` share of that year's total |
| `--format` | Output format: `table` (default), `json`, `csv`, `markdown`, `graph`, `stack`, `xlsx` |
| `--output PATH` | Destination workbook path; required with `--format xlsx` |
| `--no-rank-delta` | Hide the `±` rank-change column (shown by default) |
| `--redact` | Replace operative usernames with NATO phonetic codenames (Operative Alpha, Bravo, …) for shareable reports |
| `--delta` | Show change since last snapshot instead of current-year count |
| `--reset-snapshot` | Clear the saved contribution snapshot and exit |
| `--config` | Path to config file |
| `--init-config` | Write default config and exit |
| `--export-config` | Print TOML config scaffolded from current CLI args and exit (pipe to a file to save) |
| `--show-config` | Print current config and exit |
| `--no-update-check` | Skip update check |
| `--api-stats` | Print GraphQL request and rate-limit diagnostics to stderr |
| `--version` | Show version |
| `--help` | Show help |

### Commands

| Command | Description |
|---|---|
| `completions SHELL` | Print the shell completion script for `bash`, `zsh`, or `fish`. Eval in your shell config, e.g. `eval "$(gh-snitch completions bash)"`. |
| `update` | Download the latest release and replace the running executable, atomically. |

Transient GitHub 502/503/504 and connection failures are retried three times
with backoff. Contribution sweeps bound concurrent ranges and automatically
retry resource-limited GraphQL work with progressively smaller operative
batches. Unrecoverable GraphQL failures exit cleanly with a concise spy-themed
message on stderr, leaving stdout safe for JSON, CSV, and Markdown pipelines.
Use `--api-stats` to append GraphQL call counts, points remaining and used, and
the rate-limit reset time to stderr after a successful run.

## Output

The table shows contribution counts per operative per year, colour-graded:

- 🔴 Bottom quartile
- 🟡 Second quartile
- 🟢 Third quartile
- 💚 Top quartile (bright green)
- ⚪ Zero contributions (dim grey)
- 👻 Ghost operative — zero contributions across all surveilled periods

Operative names and counts are clickable hyperlinks in supporting terminals.

## Requirements

- Python 3.11+
- `GH_TOKEN` or `GITHUB_TOKEN` environment variable with `read:user` scope (`GH_TOKEN` takes precedence)

## Documentation

See [`docs/manual/`][manual-docs] for full documentation.

---

[manual-docs]: docs/manual/
