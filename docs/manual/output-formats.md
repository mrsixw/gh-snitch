# Output Formats

## Table Output

gh-snitch renders a plain-text table using `tabulate` with `simple` format:

```
  #  Operative      2026    2025    2024
---  -----------  ------  ------  ------
  1  alice           312     890     754
  2  bob             205     430     611
  3  carol            42     180     290
```

### Columns

- **#** — leaderboard rank, based on the current year's contribution count. Ties share the same rank; the next rank skips accordingly (competition ranking: 1, 2, 2, 4, …).
- **Operative** — GitHub username, hyperlinked to the user's profile (in TTY mode)
- **Year columns** — total contribution count for that calendar year

The current (partial) year appears first. Prior complete years follow in descending order.

### Colour Grading

Counts are colour-graded per column based on quartile position among non-zero values:

| Colour | Meaning |
|---|---|
| Dim grey | Zero contributions |
| Red | Bottom quartile (>0) |
| Yellow | Second quartile |
| Green | Third quartile |
| Bright green | Top quartile |

Grading is independent per column — a count that ranks high in one year may rank differently in another.

### Hyperlinks

In TTY mode (with a supporting terminal), operative names and contribution counts are rendered as OSC 8 hyperlinks pointing to `https://github.com/{username}`.

Set `NO_COLOR=1` to disable all ANSI output and hyperlinks.

## Status Messages

gh-snitch prints status messages to stdout during a run:

```
🔍 Initiating surveillance sweep...
📡 Intercepting field reports for 3 operatives...
[table]
🗂️  Dossier compiled. Handler review recommended.
```

If a newer version is available:
```
📬 New intelligence package available: v1.2.0. Update at: https://github.com/mrsixw/gh-snitch/releases/latest
```
