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

### 1. Core vs Extended Breakdown + `Other` Reconciliation
`contributionCalendar.totalContributions` does not always equal the exact sum of the public counters (for example, due to private contribution visibility rules, repo creation, or calendar accounting quirks).

- **Decision:** Keep `totalContributions` authoritative for ranking, `--min-contributions`, ghost detection, snapshots, and YoY trend arrows. By default, `--breakdown` renders the four core categories (`Commits`, `PRs`, `Reviews`, `Issues`) to keep tables and charts compact. Adding `--breakdown-extended` (or `display.breakdown-extended = true`) appends `Repos`, `Private`, and `Other` (`total - sum(6 categories)`).
- **Consequence:** Leaderboard rankings never shift when enabling `--breakdown`, default layouts stay uncluttered, and extended mode reconciles every category against the headline total.

### 2. Separate `--breakdown`, `--breakdown-style`, and `--breakdown-extended` Options
- **Decision:** Expose boolean `--breakdown`, `--breakdown-style {subrows,nested,cards,columns}` (default `subrows`), and boolean `--breakdown-extended` on the CLI, with matching `[display]` config keys `breakdown`, `breakdown-style`, and `breakdown-extended`. Passing `--breakdown-style` or `--breakdown-extended` on the CLI implicitly enables `--breakdown`; in `config.toml`, `breakdown = true` is required.
- **Consequence:** Non-table formats (`json`, `csv`, `markdown`, `xlsx`, `graph`, `stack`) simply take `--breakdown` without needing a table layout name, while table users can pick their preferred layout cleanly.

### 3. Four Terminal Layouts
- **`subrows`:** Tree-indented category sub-rows beneath each operative's headline row across the same period columns. Compact and scales well to multi-year/month/quarter sweeps.
- **`nested`:** Rich table-within-table embedding a compact inner breakdown table inside each period cell.
- **`cards`:** One Rich dossier table per operative (rows = categories, columns = periods).
- **`columns`:** A single table where each period column displays its six breakdown subcolumns plus `Total` (and `Other` if non-zero) side-by-side under a grouped period header.

### 4. Structured Exports, Charts & Flag Interactions
- **JSON:** Period keys map to `{"total", "commits", "prs", "reviews", "issues", "repos", "private"[, "other"]}`.
- **CSV:** Adds a `category` column (`total`, `commits`, …) keeping column count bounded across any number of periods.
- **Markdown:** Stacked GFM tables per period (`### <Period>`).
- **Excel (`xlsx`):** Inserts a `Category` column, writes category sub-rows at Excel outline level 1 (collapsible), and uses `SUMIF` for the totals footer so sub-rows are never double-counted.
- **Graph (`graph`) & Stacked Bar (`stack`):** Aggregate category counts across the cohort for each period, plotting one trend line per category (`graph`) or stacking each period bar by category (`stack`).
- **`--percent`:** Headline totals retain their `(N%)` share of the cohort's period total; category cells show their `(N%)` share of *that operative's* period total.
- **Disallowed combinations:** `--breakdown` rejects `--delta` with a `click.UsageError` (snapshots currently store scalar totals only).
