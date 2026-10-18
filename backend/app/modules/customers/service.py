import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.documents import only_digits
from app.core.exceptions import ConflictError
from app.core.pagination import PageParams, apply_page, count_rows
from app.core.queries import commit_or_conflict, get_or_404, like_pattern
from app.modules.audit import service as audit
from app.modules.audit.service import snapshot
from app.modules.auth.context import AuthContext
from app.modules.customers.models import Customer
from app.modules.customers.schemas import CustomerCreate, CustomerUpdate

AUDIT_FIELDS = ("name", "document", "email", "phone", "is_active")
DUPLICATE_MESSAGE = "Já existe um cliente com este CPF/CNPJ"


def _document_exists(db: Session, tenant_id: uuid.UUID, document: str) -> bool:
    return (
        db.scalar(
            select(Customer.id).where(Customer.tenant_id == tenant_id, Customer.document == document)
        )
        is not None
    )


def list_customers(
    db: Session,
    ctx: AuthContext,
    params: PageParams,
    *,
    search: str | None = None,
    is_active: bool | None = None,
) -> tuple[list[Customer], int]:
    conditions = [Customer.tenant_id == ctx.tenant_id]
    if search:
        clauses = [Customer.name.ilike(like_pattern(search), escape="\\")]
        digits = only_digits(search)
        if digits:
            clauses.append(Customer.document.like(f"%{digits}%"))
        conditions.append(or_(*clauses))
    if is_active is not None:
        conditions.append(Customer.is_active == is_active)

    total = count_rows(db, select(Customer.id).where(*conditions))
    stmt = select(Customer).where(*conditions).order_by(Customer.name, Customer.id)
    return list(db.scalars(apply_page(stmt, params)).all()), total


def get_customer(db: Session, ctx: AuthContext, customer_id: uuid.UUID) -> Customer:
    return get_or_404(db, Customer, ctx.tenant_id, customer_id, "Cliente")


def create_customer(db: Session, ctx: AuthContext, data: CustomerCreate) -> Customer:
    if _document_exists(db, ctx.tenant_id, data.document):
        raise ConflictError(DUPLICATE_MESSAGE)
    customer = Customer(
        tenant_id=ctx.tenant_id,
        name=data.name,
        document=data.document,
        email=data.email,
        phone=data.phone,
    )
    db.add(customer)
    db.flush()
    audit.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.user_id,
        action="customer.created",
        entity_type="customer",
        entity_id=customer.id,
        after=snapshot(customer, AUDIT_FIELDS),
    )
    commit_or_conflict(db, DUPLICATE_MESSAGE)
    return customer


def update_customer(
    db: Session, ctx: AuthContext, customer_id: uuid.UUID, data: CustomerUpdate
) -> Customer:
    customer = get_or_404(db, Customer, ctx.tenant_id, customer_id, "Cliente")
    before = snapshot(customer, AUDIT_FIELDS)

    if data.document is not None and data.document != customer.document:
        if _document_exists(db, ctx.tenant_id, data.document):
            raise ConflictError(DUPLICATE_MESSAGE)
        customer.document = data.document
    if data.name is not None:
        customer.name = data.name
    if data.is_active is not None:
        customer.is_active = data.is_active
    # Campos opcionais aceitam null explícito para limpar o valor.
    if "email" in data.model_fields_set:
        customer.email = data.email
    if "phone" in data.model_fields_set:
        customer.phone = data.phone

    after = snapshot(customer, AUDIT_FIELDS)
    if after != before:
        audit.record(
            db,
            tenant_id=ctx.tenant_id,
            actor_id=ctx.user_id,
            action="customer.updated",
            entity_type="customer",
            entity_id=customer.id,
            before=before,
            after=after,
        )
    commit_or_conflict(db, DUPLICATE_MESSAGE)
    db.refresh(customer)
    return customer
