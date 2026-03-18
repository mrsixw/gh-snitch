# Options Reference

| Option | Default | Description |
|---|---|---|
| `--config PATH` | `~/.config/gh-snitch/config.toml` | Path to TOML config file |
| `--users TEXT` | (from config) | Comma-separated GitHub usernames to surveil |
| `--years INTEGER` | (from config, default 3) | Number of prior complete years to include |
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
```

CLI flags `--users` and `--years` always override config file values.
