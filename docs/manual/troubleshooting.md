# Troubleshooting

## `GITHUB_TOKEN not set`

```
🚨 GITHUB_TOKEN not set. Operatives cannot be surveilled without credentials.
```

**Fix:** Export a valid GitHub personal access token:
```bash
export GITHUB_TOKEN=ghp_...
```

The token needs `read:user` scope to query contribution data.

## `No handler config found`

```
⚠️  No handler config found at ~/.config/gh-snitch/config.toml. Run gh-snitch --init-config to establish a cover.
```

**Fix:** Run `gh-snitch --init-config` to create a default config, then edit it to add usernames.

## `No operatives configured`

```
⚠️  No operatives configured. Add users to your config or use --users.
```

**Fix:** Either add users to your config file:
```toml
[operatives]
users = ["alice", "bob"]
```

Or pass them via `--users`:
```bash
gh-snitch --users alice,bob
```

## `Signal lost. Operative unreachable`

```
📡 Signal lost. Operative unreachable: <error>
```

**Fix:** Check your network connection and verify your `GITHUB_TOKEN` is valid and not expired. GitHub's API may also be temporarily unavailable.

## Colours not showing

If you see raw ANSI escape codes instead of colours, your terminal may not support them. Set `NO_COLOR=1` to disable colour output entirely:

```bash
NO_COLOR=1 gh-snitch
```

## Hyperlinks not working

OSC 8 hyperlinks require a supported terminal (e.g. iTerm2, Kitty, WezTerm). In unsupported terminals, operative names appear as plain text — this is expected behaviour.
