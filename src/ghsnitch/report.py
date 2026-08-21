"""Build isolated contribution reports from a shared surveillance sweep."""

import hashlib
from dataclasses import dataclass

from .snapshot import compute_scope, load_snapshot, save_snapshot


@dataclass
class ContributionReport:
    """Contribution data and display metadata for one independent cohort."""

    name: str | None
    users: list[str]
    rows: list[dict]
    period_labels: list[str]
    rank_deltas: dict[str, int | None] | None
    ghost_usernames: set[str]
    delta_column: str | None
    suppressed_count: int
    missing_delta_snapshot: bool


def _compute_rank_metadata(rows, current_period_label):
    """Return competition ranks for a leaderboard.

    Args:
        rows: Contribution rows containing a ``username`` key.
        current_period_label: Period used to rank the leaderboard.

    Returns:
        tuple[dict[str, int], dict[str, int]]: Display ranks and persisted
        movement positions keyed by username.
    """
    sorted_rows = sorted(
        rows, key=lambda row: (-row.get(current_period_label, 0), row["username"])
    )
    ranks = {}
    positions = {}
    index = 0
    while index < len(sorted_rows):
        current_count = sorted_rows[index].get(current_period_label, 0)
        group_end = index + 1
        while (
            group_end < len(sorted_rows)
            and sorted_rows[group_end].get(current_period_label, 0) == current_count
        ):
            group_end += 1

        competition_rank = index + 1
        for row in sorted_rows[index:group_end]:
            username = row["username"]
            ranks[username] = competition_rank
            positions[username] = competition_rank

        index = group_end
    return ranks, positions


def _get_snapshot_ranks(snapshot, current_period_label):
    """Return comparable ranks from a current or legacy snapshot.

    Args:
        snapshot: Previously persisted snapshot payload.
        current_period_label: Period used to rank the current report.

    Returns:
        dict[str, int]: Persisted or reconstructed ranks keyed by username.
    """
    stored_ranks = snapshot.get("ranks", {})
    if stored_ranks:
        return stored_ranks

    snapshot_contributions = snapshot.get("contributions", {})
    if any(
        current_period_label in period_data
        for period_data in snapshot_contributions.values()
    ):
        snapshot_rows = []
        for username, period_data in snapshot_contributions.items():
            row = {"username": username}
            row.update(period_data)
            snapshot_rows.append(row)
        ranks, _ = _compute_rank_metadata(snapshot_rows, current_period_label)
        return ranks

    return snapshot.get("positions", {})


def _snapshot_context_id(name, users):
    """Return the existing team or ad-hoc snapshot context identifier.

    Args:
        name: Optional configured team name.
        users: Users in the report cohort.

    Returns:
        str | None: Stable context identifier for snapshot partitioning.
    """
    if name is not None:
        return f"team-{name}"
    if not users:
        return None
    user_key = ",".join(sorted(users))
    user_hash = hashlib.sha256(user_key.encode()).hexdigest()[:12]
    return f"u-{user_hash}"


def build_contribution_report(  # noqa: PLR0913
    name,
    users,
    contributions,
    period_labels,
    github_url,
    *,
    delta=False,
    min_contributions=0,
):
    """Build one independently ranked and snapshotted contribution report.

    Args:
        name: Optional configured team name.
        users: Ordered usernames belonging to this report.
        contributions: Shared sweep results keyed by username and period.
        period_labels: Ordered display labels, newest first.
        github_url: GitHub base URL used to scope snapshots.
        delta: Whether to replace the newest period with snapshot differences.
        min_contributions: Minimum newest-period count to keep a row.

    Returns:
        ContributionReport: Prepared rows and renderer metadata for the cohort.
    """
    labels = list(period_labels)
    rows = []
    for username in users:
        row = {"username": username}
        row.update(contributions.get(username, {}))
        rows.append(row)

    if not rows:
        empty_period_labels = ["Δ Today"] if delta else labels
        return ContributionReport(
            name=name,
            users=list(users),
            rows=[],
            period_labels=empty_period_labels,
            rank_deltas=None,
            ghost_usernames=set(),
            delta_column="Δ Today" if delta else None,
            suppressed_count=0,
            missing_delta_snapshot=False,
        )

    current_period_label = labels[0]
    snapshot_scope = compute_scope(users, github_url)
    context_id = _snapshot_context_id(name, users)
    previous_snapshot = load_snapshot(scope=snapshot_scope, context_id=context_id)
    current_ranks, current_positions = _compute_rank_metadata(
        rows, current_period_label
    )

    if not delta:
        save_snapshot(
            {
                row["username"]: {label: row.get(label, 0) for label in period_labels}
                for row in rows
            },
            ranks=current_ranks,
            positions=current_positions,
            scope=snapshot_scope,
            context_id=context_id,
        )

    rank_deltas = None
    if previous_snapshot is not None:
        previous_ranks = _get_snapshot_ranks(previous_snapshot, current_period_label)
        if previous_ranks:
            rank_deltas = {}
            for username, current_position in current_positions.items():
                if username not in previous_ranks:
                    rank_deltas[username] = None
                else:
                    rank_deltas[username] = previous_ranks[username] - current_position

    suppressed_count = 0
    if min_contributions > 0:
        filtered_rows = []
        for row in rows:
            if row.get(current_period_label, 0) >= min_contributions:
                filtered_rows.append(row)
            else:
                suppressed_count += 1
        rows = filtered_rows

    ghost_usernames = {
        row["username"]
        for row in rows
        if all(row.get(label, 0) == 0 for label in labels)
    }

    delta_column = None
    missing_delta_snapshot = delta and previous_snapshot is None
    if delta and previous_snapshot is not None:
        previous_data = previous_snapshot.get("contributions", {})
        for row in rows:
            username = row["username"]
            previous_count = previous_data.get(username, {}).get(
                current_period_label, 0
            )
            row["Δ Today"] = row.get(current_period_label, 0) - previous_count
            row.pop(current_period_label, None)
        labels = ["Δ Today"]
        delta_column = "Δ Today"
        rank_deltas = None

    return ContributionReport(
        name=name,
        users=list(users),
        rows=rows,
        period_labels=labels,
        rank_deltas=rank_deltas,
        ghost_usernames=ghost_usernames,
        delta_column=delta_column,
        suppressed_count=suppressed_count,
        missing_delta_snapshot=missing_delta_snapshot,
    )
