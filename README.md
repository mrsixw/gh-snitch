# gh-snitch 🕵️

**Spy-themed GitHub contribution surveillance tool.**

Monitor your operatives' GitHub contribution counts across years — rendered as a ranked, colour-graded table in your terminal.

## Installation

```bash
curl -sSL https://raw.githubusercontent.com/mrsixw/gh-snitch/main/install.sh | bash
```

Or clone and build from source:

```bash
git clone https://github.com/mrsixw/gh-snitch.git
cd gh-snitch
make build
```

## Quick Start

1. Set your GitHub token:
   ```bash
   export GITHUB_TOKEN=ghp_...
   ```

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
| `--years` | Number of prior years (overrides config) |
| `--min-contributions` | Hide operatives below this contribution count |
| `--totals` | Add a Total column per operative and a Total footer row |
| `--percent` | Annotate each cell with the operative's `(N%)` share of that year's total |
| `--delta` | Show change since last snapshot instead of current-year count |
| `--rank-delta` | Show `±` column with rank position changes since the last snapshot |
| `--reset-snapshot` | Clear the saved contribution snapshot and exit |
| `--config` | Path to config file |
| `--init-config` | Write default config and exit |
| `--show-config` | Print current config and exit |
| `--no-update-check` | Skip update check |
| `--version` | Show version |
| `--help` | Show help |

## Output

The table shows contribution counts per operative per year, colour-graded:

- 🔴 Bottom quartile
- 🟡 Second quartile
- 🟢 Third quartile
- 💚 Top quartile (bright green)
- ⚪ Zero contributions (dim grey)

Operative names and counts are clickable hyperlinks in supporting terminals.

## Requirements

- Python 3.11+
- `GITHUB_TOKEN` environment variable with `read:user` scope

## Documentation

See [`docs/manual/`](docs/manual/) for full documentation.
