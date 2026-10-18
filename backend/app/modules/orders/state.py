from app.core.exceptions import InvalidStatusTransitionError
from app.modules.auth.permissions import Permission
from app.modules.orders.models import OrderStatus

# Fluxo operacional: rascunho -> confirmado (reserva) -> separação -> enviado (baixa) -> entregue.
# O cancelamento só é possível antes do envio.
ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.DRAFT: frozenset({OrderStatus.CONFIRMED, OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.PICKING, OrderStatus.CANCELLED}),
    OrderStatus.PICKING: frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED}),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}

# Permissão exigida para ENTRAR em cada status.
TARGET_PERMISSION: dict[OrderStatus, Permission] = {
    OrderStatus.CONFIRMED: Permission.ORDERS_CONFIRM,
    OrderStatus.PICKING: Permission.ORDERS_FULFILL,
    OrderStatus.SHIPPED: Permission.ORDERS_FULFILL,
    OrderStatus.DELIVERED: Permission.ORDERS_FULFILL,
    OrderStatus.CANCELLED: Permission.ORDERS_CANCEL,
}

STATUS_LABELS: dict[OrderStatus, str] = {
    OrderStatus.DRAFT: "Rascunho",
    OrderStatus.CONFIRMED: "Confirmado",
    OrderStatus.PICKING: "Em separação",
    OrderStatus.SHIPPED: "Enviado",
    OrderStatus.DELIVERED: "Entregue",
    OrderStatus.CANCELLED: "Cancelado",
}


def ensure_transition_allowed(current: OrderStatus, target: OrderStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidStatusTransitionError(
            f"Não é possível mover o pedido de '{STATUS_LABELS[current]}' "
            f"para '{STATUS_LABELS[target]}'"
        )
