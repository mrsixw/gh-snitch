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

## Specifying Year Range

Control how many prior years are included alongside the current year:

```bash
gh-snitch --years 5
```

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

## One-Shot Command

Combine flags for a quick ad-hoc sweep without touching your config:

```bash
GITHUB_TOKEN=ghp_... gh-snitch --users alice,bob --years 2 --no-update-check
```
