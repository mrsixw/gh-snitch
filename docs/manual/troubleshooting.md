# Troubleshooting

## `GH_TOKEN or GITHUB_TOKEN not set`

```
🚨 GH_TOKEN or GITHUB_TOKEN not set. Operatives cannot be surveilled without credentials.
```

**Fix:** Export a valid GitHub personal access token as either `GH_TOKEN` or `GITHUB_TOKEN`:
```bash
export GITHUB_TOKEN=ghp_...
```

If both are set, `GH_TOKEN` takes precedence. The token needs `read:user` scope to query contribution data.

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

## Operative not found — "gone dark" warning

```
⚠️  Operative 'username' not found — they may have gone dark.
🚨 1 operative(s) could not be located. Verify their handles and try again.
```

One or more of the supplied usernames could not be resolved to a GitHub account. The tool still renders the table for valid operatives and exits with a non-zero status code.

**Fix:** Check the spelling of the username(s). GitHub usernames are case-insensitive but must otherwise be exact. Usernames containing dots (`.`) or hyphens (`-`) must be specified exactly as they appear on GitHub.

## `Signal lost after retries. Operative unreachable`

```
📡 Signal lost after retries. Operative unreachable: <error>
```

gh-snitch automatically retries connection failures, timeouts, and GitHub
502/503/504 responses three times with exponential backoff before showing this
message.

**Fix:** Check your network connection and verify your `GITHUB_TOKEN` is valid
and not expired. GitHub's API may also be temporarily unavailable.

## `Surveillance rate limit reached`

```
⏱️  Surveillance rate limit reached. GitHub signals reset at <time>. Stand down and retry after that time.
```

GitHub rejected the query because the token's GraphQL rate limit is exhausted.
When GitHub supplies a reset time, gh-snitch includes it in UTC.

**Fix:** Wait until the reported reset time, reduce the number of time ranges,
or use a token with an available rate-limit budget.

## `Surveillance query exceeded GitHub's resource limits`

```
🕵️  Surveillance query exceeded GitHub's resource limits. Reduce the number of operatives or time ranges and try again.
```

gh-snitch normally recovers from GitHub resource limits automatically. It limits
concurrent date-range requests, queries operatives in bounded batches, and
retries a rejected batch at progressively smaller sizes. A reduced size remains
in use for the rest of that range.

This message appears only when GitHub still rejects a single-operative batch.
gh-snitch then stops the complete sweep and does not render or save partial
contribution data.

**Fix:** Reduce the number of operatives in `--users` or the selected team.
Alternatively, request fewer years, months, or weeks before trying again.

## Other fatal GraphQL errors

```
🕵️  Surveillance query failed: <bounded error summary>
```

Authentication, scope, and other GraphQL failures are summarized by error type
and count. The full GitHub error array is never printed to the terminal or
normal logs, even when GitHub repeats an error hundreds of times.

All operational errors are written to stderr and exit non-zero. Data formats
remain exclusive to stdout, so redirected JSON, CSV, and Markdown output cannot
be contaminated by a traceback or partial result.

## GitHub Enterprise Server: `Signal lost` or GraphQL errors

If you're targeting a GHES instance and see network or GraphQL errors, check:

1. **Correct URL** — use the base hostname, e.g. `https://github.example.com` (no path, no trailing slash).
2. **Token source** — the `GITHUB_TOKEN` must be issued by the Enterprise instance, not github.com.
3. **Token scope** — the token needs `read:user` scope on the Enterprise instance.
4. **API access** — confirm the instance is reachable and the GraphQL API is enabled.

## Colours not showing

If you see raw ANSI escape codes instead of colours, your terminal may not support them. Set `NO_COLOR=1` to disable colour output entirely:

```bash
NO_COLOR=1 gh-snitch
```

## Hyperlinks not working

OSC 8 hyperlinks require a supported terminal (e.g. iTerm2, Kitty, WezTerm). In unsupported terminals, operative names appear as plain text — this is expected behaviour.
