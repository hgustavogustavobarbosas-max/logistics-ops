import pytest

from app.core.exceptions import InvalidStatusTransitionError
from app.modules.auth.permissions import Permission
from app.modules.orders.models import OrderStatus
from app.modules.orders.state import (
    ALLOWED_TRANSITIONS,
    TARGET_PERMISSION,
    ensure_transition_allowed,
)

S = OrderStatus
VALID = [
    (S.DRAFT, S.CONFIRMED),
    (S.DRAFT, S.CANCELLED),
    (S.CONFIRMED, S.PICKING),
    (S.CONFIRMED, S.CANCELLED),
    (S.PICKING, S.SHIPPED),
    (S.PICKING, S.CANCELLED),
    (S.SHIPPED, S.DELIVERED),
]


@pytest.mark.parametrize(("current", "target"), VALID)
def test_valid_transitions_are_allowed(current: OrderStatus, target: OrderStatus) -> None:
    ensure_transition_allowed(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [(c, t) for c in S for t in S if (c, t) not in VALID],
)
def test_every_other_transition_is_rejected(current: OrderStatus, target: OrderStatus) -> None:
    with pytest.raises(InvalidStatusTransitionError):
        ensure_transition_allowed(current, target)


def test_final_states_have_no_exit() -> None:
    assert ALLOWED_TRANSITIONS[S.DELIVERED] == frozenset()
    assert ALLOWED_TRANSITIONS[S.CANCELLED] == frozenset()


def test_shipped_orders_cannot_be_cancelled() -> None:
    assert S.CANCELLED not in ALLOWED_TRANSITIONS[S.SHIPPED]


def test_every_reachable_status_requires_a_permission() -> None:
    reachable = {target for targets in ALLOWED_TRANSITIONS.values() for target in targets}
    assert reachable == set(TARGET_PERMISSION)
    assert TARGET_PERMISSION[S.CONFIRMED] == Permission.ORDERS_CONFIRM
    assert TARGET_PERMISSION[S.CANCELLED] == Permission.ORDERS_CANCEL
