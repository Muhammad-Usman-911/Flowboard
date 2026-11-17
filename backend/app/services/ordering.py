"""Position helpers for ordered lists (columns on a board, tasks in a column).

Strategy: positions are always 0, 1, 2, ... with no gaps. To move an item we take the
list in its current order, pull the item out, insert it at the new index, and write
0..n-1 back. Only rows whose position actually changed are updated.

This is simple and always correct, at the cost of touching up to n rows per move, which
is fine for Kanban columns (tens or hundreds of cards). LEARNING_GUIDE.md compares it with
"fractional" positions (e.g. 1.5 between 1 and 2) used by apps with huge lists.
"""

from typing import Protocol, TypeVar


class Positioned(Protocol):
    position: int


T = TypeVar("T", bound=Positioned)


def move_item[T: Positioned](items: list[T], item: T, index: int) -> list[T]:
    """Return a new list with `item` placed at `index` (clamped to the valid range).
    `item` may or may not already be in `items` (same column vs. other column)."""
    rest = [i for i in items if i is not item]
    index = max(0, min(index, len(rest)))
    rest.insert(index, item)
    return rest


def renumber[T: Positioned](items: list[T]) -> None:
    """Write positions 0..n-1 in list order (only touching rows that changed)."""
    for position, item in enumerate(items):
        if item.position != position:
            item.position = position
