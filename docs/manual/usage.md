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

## One-Shot Command

Combine flags for a quick ad-hoc sweep without touching your config:

```bash
GITHUB_TOKEN=ghp_... gh-snitch --users alice,bob --years 2 --no-update-check
```
