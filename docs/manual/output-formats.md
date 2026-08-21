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
- **Period columns** — contribution count for each requested year, month, quarter, week, or custom window

The newest period appears first. For `--last-quarters`, that means the current quarter-to-date followed by complete prior quarters.

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

## Multiple Teams

Repeating `--team` preserves team boundaries rather than combining everyone into one leaderboard:

```bash
gh-snitch --team platform --team backend
```

Table, Markdown, graph, and stack output render one labelled section per team in command-line order. JSON returns a top-level `teams` array:

```json
{
  "teams": [
    {
      "team": "platform",
      "operatives": [
        {"rank": 1, "operative": "alice", "Q3 2026": 312}
      ]
    }
  ]
}
```

CSV remains a single stream and adds team identity to every row:

```csv
team,rank,operative,Q3 2026
platform,1,alice,312
backend,1,bob,205
```

Rankings, filtering, totals, ghost detection, and snapshots are calculated independently for each team. An operative shared by two teams appears in both reports.

Direct-user and single-team runs retain the original JSON array and CSV columns for compatibility.

## Excel Workbooks

Excel output uses XlsxWriter and requires a destination path:

```bash
gh-snitch --team platform --team backend --last-quarters 4 \
  --format xlsx --output quarterly-teams.xlsx
```

Each selected team becomes one worksheet, in command-line order, with all requested periods as columns. A direct `--users` report uses a single worksheet named `Dossier`. Worksheet names are made Excel-safe and disambiguated when team names would otherwise collide.

The workbook uses typed contribution counts, frozen headings and identity columns, filters, GitHub profile links, and a restrained contribution colour scale. `--redact` replaces operative names and removes those links. `--totals` adds formula-driven row and column totals. An empty team in a multi-team report still receives a labelled zero-state worksheet.

gh-snitch creates missing parent directories but refuses to overwrite an existing workbook. `--output` is rejected for every non-Excel format.

## Status Messages

gh-snitch prints status messages to stderr during a run, keeping stdout clean for text data formats:

```
🔍 Initiating surveillance sweep...
📡 Intercepting field reports for 3 operatives...
[report data or workbook status]
🗂️  Dossier compiled. Handler review recommended.
```

If a newer version is available:
```
📬 New intelligence package available: v1.2.0. Update at: https://github.com/mrsixw/gh-snitch/releases/latest
```
