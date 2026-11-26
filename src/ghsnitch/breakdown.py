"""Data model and helpers for GitHub contribution category breakdowns."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

__all__ = [
    "BREAKDOWN_CATEGORIES",
    "CORE_BREAKDOWN_CATEGORIES",
    "ContributionBreakdown",
    "EXTENDED_BREAKDOWN_CATEGORIES",
    "VALID_BREAKDOWN_STYLES",
    "has_other_contributions",
    "sum_breakdowns",
]

VALID_BREAKDOWN_STYLES = ("subrows", "nested", "cards", "columns")

CORE_BREAKDOWN_CATEGORIES = (
    ("commits", "Commits"),
    ("prs", "PRs"),
    ("reviews", "Reviews"),
    ("issues", "Issues"),
)

EXTENDED_BREAKDOWN_CATEGORIES = (
    ("repos", "Repos"),
    ("private", "Private"),
)

BREAKDOWN_CATEGORIES = CORE_BREAKDOWN_CATEGORIES + EXTENDED_BREAKDOWN_CATEGORIES


@dataclass(frozen=True)
class ContributionBreakdown:
    """Category breakdown of a user's GitHub contributions for one time window.

    ``total`` comes from GitHub's ``contributionCalendar.totalContributions``
    and remains the authoritative headline figure. Default breakdowns display
    the four core categories (``Commits``, ``PRs``, ``Reviews``, ``Issues``);
    extended mode also includes ``Repos``, ``Private``, and ``Other`` (any
    discrepancy between ``total`` and the six explicit counters).
    """

    total: int = 0
    commits: int = 0
    prs: int = 0
    reviews: int = 0
    issues: int = 0
    repos: int = 0
    private: int = 0

    @property
    def category_sum(self) -> int:
        """Return the sum of the six explicit GitHub breakdown categories."""
        return (
            self.commits
            + self.prs
            + self.reviews
            + self.issues
            + self.repos
            + self.private
        )

    @property
    def other(self) -> int:
        """Return any discrepancy between ``total`` and the six categories."""
        return self.total - self.category_sum

    def categories(
        self,
        *,
        extended: bool = False,
        include_other: bool | None = None,
    ) -> list[tuple[str, str, int]]:
        """Return ``(key, label, value)`` tuples for the selected categories.

        When ``extended`` is False (default), returns the four core categories.
        When ``extended`` is True, returns the six GitHub categories plus
        ``Other`` (unless ``include_other=False`` is explicitly passed).
        """
        cat_defs = BREAKDOWN_CATEGORIES if extended else CORE_BREAKDOWN_CATEGORIES
        items = [(key, label, getattr(self, key)) for key, label in cat_defs]
        show_other = extended if include_other is None else include_other
        if show_other:
            items.append(("other", "Other", self.other))
        return items

    def to_dict(
        self,
        *,
        extended: bool = False,
        include_other: bool | None = None,
    ) -> dict[str, int]:
        """Return a JSON-ready dictionary of ``total`` and category counts."""
        payload = {"total": self.total}
        for key, _label, value in self.categories(
            extended=extended, include_other=include_other
        ):
            payload[key] = value
        return payload


def sum_breakdowns(
    breakdowns: Iterable[ContributionBreakdown],
) -> ContributionBreakdown:
    """Return the element-wise sum of multiple contribution breakdowns."""
    total = commits = prs = reviews = issues = repos = private = 0
    for item in breakdowns:
        total += item.total
        commits += item.commits
        prs += item.prs
        reviews += item.reviews
        issues += item.issues
        repos += item.repos
        private += item.private
    return ContributionBreakdown(
        total=total,
        commits=commits,
        prs=prs,
        reviews=reviews,
        issues=issues,
        repos=repos,
        private=private,
    )


def has_other_contributions(
    breakdowns: Mapping[str, Mapping[str, ContributionBreakdown]] | None,
    users: Iterable[str] | None = None,
    period_labels: Iterable[str] | None = None,
) -> bool:
    """Return whether any breakdown in scope has a non-zero ``other`` remainder."""
    if not breakdowns:
        return False
    selected_users = list(users) if users is not None else list(breakdowns.keys())
    selected_labels = list(period_labels) if period_labels is not None else None
    for username in selected_users:
        user_periods = breakdowns.get(username, {})
        labels = selected_labels if selected_labels is not None else user_periods.keys()
        for label in labels:
            item = user_periods.get(label)
            if item is not None and item.other != 0:
                return True
    return False
