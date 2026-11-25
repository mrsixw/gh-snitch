# Contribution Breakdown Stats

## Context

Previously, `gh-snitch` queried only `contributionsCollection.contributionCalendar.totalContributions`, displaying a single integer per operative per surveillance window. Handlers wanted visibility into *what* made up those numbers (commits, PRs, reviews, issues, repos created, and private contributions) with multiple terminal layouts and matching structured exports.

## GraphQL Field Mapping

All six breakdown counters live directly as scalar `Int!` fields on the existing `contributionsCollection(from: $from, to: $to)` node — requiring **zero extra HTTP requests** and no connection/pagination overhead:

| Category | Display Label | GraphQL Field |
|---|---|---|
| `commits` | Commits | `totalCommitContributions` |
| `prs` | PRs | `totalPullRequestContributions` |
| `reviews` | Reviews | `totalPullRequestReviewContributions` |
| `issues` | Issues | `totalIssueContributions` |
| `repos` | Repos | `totalRepositoryContributions` |
| `private` | Private | `restrictedContributionsCount` |

Per-repository connection fields (`commitContributionsByRepository`, etc.) were deliberately excluded because they multiply GraphQL query cost and risk `RESOURCE_LIMITS_EXCEEDED` when batching up to 10 operatives per query.

## Key Design Decisions

### 1. Authoritative Headline Total + `Other` Reconciliation
`contributionCalendar.totalContributions` does not always equal the exact sum of the six scalar fields (for example, due to private contribution visibility rules or calendar accounting quirks).

- **Decision:** Keep `totalContributions` authoritative for ranking, `--min-contributions`, ghost detection, snapshots, and YoY trend arrows. Compute `other = total - sum(6 categories)` and render an `Other` row/column **only** when at least one operative/period in the rendered scope has `other != 0`.
- **Consequence:** Leaderboard rankings never shift when enabling `--breakdown`, and displayed category counts always reconcile with the headline total.

### 2. Single `--breakdown <style>` Option
- **Decision:** Expose `--breakdown {subrows,nested,cards,columns}` on the CLI and `breakdown = "<style>"` under `[display]` in `config.toml`.
- **Alternatives considered:** Separate `--breakdown` flag + `--breakdown-style` option, or extra `--format` values. A single option avoids Click's optional-value ambiguity with subcommands (`completions`, `update`) while keeping `--format` orthogonal so `--breakdown` works across `table`, `json`, `csv`, `markdown`, and `xlsx`.

### 3. Four Terminal Layouts
- **`subrows`:** Tree-indented category sub-rows beneath each operative's headline row across the same period columns. Compact and scales well to multi-year/month/quarter sweeps.
- **`nested`:** Rich table-within-table embedding a compact inner breakdown table inside each period cell.
- **`cards`:** One Rich dossier table per operative (rows = categories, columns = periods).
- **`columns`:** One flat category-columns table per period, stacked newest-first (avoiding 24+ unreadably wide columns on multi-year sweeps).

### 4. Structured Exports & Flag Interactions
- **JSON:** Period keys map to `{"total", "commits", "prs", "reviews", "issues", "repos", "private"[, "other"]}`.
- **CSV:** Adds a `category` column (`total`, `commits`, …) keeping column count bounded across any number of periods.
- **Markdown:** Stacked GFM tables per period (`### <Period>`).
- **Excel (`xlsx`):** Inserts a `Category` column, writes category sub-rows at Excel outline level 1 (collapsible), and uses `SUMIF` for the totals footer so sub-rows are never double-counted.
- **`--percent`:** Headline totals retain their `(N%)` share of the cohort's period total; category cells show their `(N%)` share of *that operative's* period total.
- **Disallowed combinations:** `--breakdown` rejects `--delta`, `--format graph`, and `--format stack` with a clear `click.UsageError` (snapshots currently store scalar totals only).
