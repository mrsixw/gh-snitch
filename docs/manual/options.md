# Options Reference

| Option | Default | Description |
|---|---|---|
| `--config PATH` | `~/.config/gh-snitch/config.toml` | Path to TOML config file |
| `--users TEXT` | (from config) | Comma-separated GitHub usernames to surveil |
| `--years INTEGER` | (from config, default 3) | Number of prior complete years to include |
| `--github-url URL` | `https://github.com` | GitHub base URL — set to your GitHub Enterprise Server hostname |
| `--min-contributions INTEGER` | `0` (show all) | Hide operatives with fewer than N contributions in the current year |
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

[network]
# github_url = "https://github.example.com"  # omit for github.com

[display]
# min_contributions = 10  # hide operatives below this threshold
```

CLI flags `--users`, `--years`, `--github-url`, and `--min-contributions` always override config file values.
