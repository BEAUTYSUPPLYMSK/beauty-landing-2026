import pytest

from bot.core import states


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (states.DRAFT, states.PUBLISHED),
        (states.DRAFT, states.SCHEDULED),
        (states.DRAFT, states.DELETED),
        (states.SCHEDULED, states.PUBLISHED),
        (states.SCHEDULED, states.SCHEDULED),
        (states.SCHEDULED, states.DRAFT),
        (states.SCHEDULED, states.DELETED),
        (states.PUBLISHED, states.DELETED),
    ],
)
def test_allowed_transitions(current, target):
    assert states.transition(current, target) == target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (states.PUBLISHED, states.DRAFT),
        (states.PUBLISHED, states.SCHEDULED),
        (states.DELETED, states.PUBLISHED),
        (states.DELETED, states.DRAFT),
        (states.DRAFT, states.DRAFT),
    ],
)
def test_illegal_transitions_raise(current, target):
    with pytest.raises(ValueError):
        states.transition(current, target)


def test_unknown_state_raises():
    with pytest.raises(ValueError):
        states.transition("nonsense", states.PUBLISHED)
    with pytest.raises(ValueError):
        states.transition(states.DRAFT, "nonsense")
