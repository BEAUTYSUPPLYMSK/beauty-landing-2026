"""Post lifecycle state machine (pure logic, no framework imports)."""

from __future__ import annotations

DRAFT = "draft"
SCHEDULED = "scheduled"
PUBLISHED = "published"
DELETED = "deleted"

ALL_STATES = frozenset({DRAFT, SCHEDULED, PUBLISHED, DELETED})

_ALLOWED: frozenset[tuple[str, str]] = frozenset(
    {
        (DRAFT, SCHEDULED),      # schedule a draft
        (DRAFT, PUBLISHED),      # publish a draft immediately
        (DRAFT, DELETED),        # discard a draft
        (SCHEDULED, DRAFT),      # cancel a scheduled post back to draft
        (SCHEDULED, SCHEDULED),  # reschedule
        (SCHEDULED, PUBLISHED),  # scheduler fires (or "publish now")
        (SCHEDULED, DELETED),    # drop a scheduled post entirely
        (PUBLISHED, DELETED),    # delete from the channel
    }
)


def can_transition(current: str, target: str) -> bool:
    return (current, target) in _ALLOWED


def transition(current: str, target: str) -> str:
    """Validate and return the new state, raising ValueError when illegal."""
    if current not in ALL_STATES:
        raise ValueError(f"Unknown post state: {current!r}")
    if target not in ALL_STATES:
        raise ValueError(f"Unknown post state: {target!r}")
    if not can_transition(current, target):
        raise ValueError(f"Illegal post state transition: {current} -> {target}")
    return target
