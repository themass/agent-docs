"""Declarative, allow-listed `ORDER BY` for the admin list endpoints.

Why this exists rather than each store taking a `sort_by` string
----------------------------------------------------------------
Every admin list hard-coded one order (`updated_at DESC`, `created_at DESC`,
`last_message_at DESC`), so an operator looking for the slowest call or the
oldest open feedback had to page through everything. Adding `sort_by` to four
stores independently would repeat three decisions that are easy to get wrong in
different ways in each one:

1. **An unknown column must never reach SQL.** The sort key arrives from a query
   string. Mapping it through an explicit allow-list of ORM columns — rather
   than `getattr(Model, name)` — is what makes that structurally impossible
   instead of merely unlikely.
2. **An unknown key must fail loudly.** Silently falling back to the default
   renders a column header as sorted when the rows are not, which is worse than
   an error: the operator draws conclusions from an order that is not there.
3. **Every sort needs a unique tiebreaker.** `ORDER BY status` over offset
   pagination is non-deterministic across pages in MySQL — rows with equal
   `status` may be returned in a different order for page 2 than page 1, so a
   row can appear twice or not at all. Appending the primary key makes the
   total order strict, which is what offset pagination assumes.

A `SortSpec` is declared next to the store that owns the table, so the set of
sortable columns is visible in one place and the API layer only passes through
two strings.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import asc, desc
from sqlalchemy.sql.elements import UnaryExpression

from jc.exceptions import AppError

#: Direction tokens accepted from the API. Compared case-insensitively.
_DIRECTIONS = frozenset({"asc", "desc"})


@dataclass(frozen=True, slots=True)
class SortSpec:
    """The sortable surface of one list query.

    `fields` maps the *API's* field name (the same name the response model and
    therefore the table header uses) to the ORM column. Keeping those names
    identical is deliberate: a header can be made clickable by its own key with
    no translation table on either side, and a renamed response field fails fast
    here instead of silently losing its sort.

    `tiebreaker` is appended to every order, in the same direction, to keep the
    total order strict under offset pagination. It must be unique — in practice
    the primary key.
    """

    fields: Mapping[str, object]
    default: str
    tiebreaker: object
    default_direction: str = "desc"

    def __post_init__(self) -> None:
        # Declaration-time checks: a mis-declared spec is a programming error and
        # should surface on import, not on the first request that happens to use it.
        if self.default not in self.fields:
            raise ValueError(f"default sort {self.default!r} is not in fields")
        if self.default_direction not in _DIRECTIONS:
            raise ValueError(f"default direction {self.default_direction!r} is invalid")

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(self.fields)

    def resolve(self, sort_by: str | None, sort_dir: str | None) -> tuple[str, str]:
        """Normalise the requested sort, or raise `AppError` (HTTP 400).

        Returned as the resolved `(field, direction)` so a response can echo
        what it actually sorted by — the table header needs to render its arrow
        from the server's answer, not from what the client asked for.
        """
        field = (sort_by or self.default).strip()
        if field not in self.fields:
            raise AppError(
                f"不支持按 {field!r} 排序，可用字段：{', '.join(self.keys)}。",
                code="invalid_sort_field",
            )
        direction = (sort_dir or self.default_direction).strip().lower()
        if direction not in _DIRECTIONS:
            raise AppError(
                f"排序方向只能是 asc 或 desc，收到 {direction!r}。",
                code="invalid_sort_direction",
            )
        return field, direction

    def order_by(
        self, sort_by: str | None, sort_dir: str | None
    ) -> tuple[Sequence[UnaryExpression], str, str]:
        """`(order_by clauses, resolved field, resolved direction)`."""
        field, direction = self.resolve(sort_by, sort_dir)
        wrap = asc if direction == "asc" else desc
        column = self.fields[field]
        clauses: list[UnaryExpression] = [wrap(column)]
        if column is not self.tiebreaker:
            clauses.append(wrap(self.tiebreaker))
        return clauses, field, direction
