"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-07
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORDER_STATUSES = "'draft', 'confirmed', 'picking', 'shipped', 'delivered', 'cancelled'"
APPEND_ONLY_TABLES = ("stock_movements", "order_status_history", "audit_logs")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_order_number", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("slug", name=op.f("uq_tenants_slug")),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_users_tenant_id_tenants")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_users_tenant_id_id")),
        sa.CheckConstraint(
            "role IN ('admin', 'manager', 'operator', 'viewer')", name=op.f("ck_users_role_valid")
        ),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])

    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("document", sa.String(14), nullable=False),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_customers_tenant_id_tenants")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_customers_tenant_id_id")),
        sa.UniqueConstraint("tenant_id", "document", name=op.f("uq_customers_tenant_id_document")),
    )
    op.create_index("ix_customers_tenant_id_name", "customers", ["tenant_id", "name"])

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(10), server_default="UN", nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("min_stock", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_products_tenant_id_tenants")),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_products_tenant_id_id")),
        sa.UniqueConstraint("tenant_id", "sku", name=op.f("uq_products_tenant_id_sku")),
        sa.CheckConstraint("unit_price >= 0", name=op.f("ck_products_unit_price_non_negative")),
        sa.CheckConstraint("min_stock >= 0", name=op.f("ck_products_min_stock_non_negative")),
    )
    op.create_index("ix_products_tenant_id_name", "products", ["tenant_id", "name"])

    op.create_table(
        "stock_balances",
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("on_hand", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reserved", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "product_id", name=op.f("pk_stock_balances")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_stock_balances_tenant_id_tenants")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name=op.f("fk_stock_balances_product_id_products"),
        ),
        sa.CheckConstraint("on_hand >= 0", name=op.f("ck_stock_balances_on_hand_non_negative")),
        sa.CheckConstraint("reserved >= 0", name=op.f("ck_stock_balances_reserved_non_negative")),
        sa.CheckConstraint("reserved <= on_hand", name=op.f("ck_stock_balances_reserved_within_on_hand")),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_orders_tenant_id_tenants")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "customer_id"],
            ["customers.tenant_id", "customers.id"],
            name=op.f("fk_orders_customer_id_customers"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_id"],
            ["users.tenant_id", "users.id"],
            name=op.f("fk_orders_created_by_id_users"),
        ),
        sa.UniqueConstraint("tenant_id", "id", name=op.f("uq_orders_tenant_id_id")),
        sa.UniqueConstraint("tenant_id", "number", name=op.f("uq_orders_tenant_id_number")),
        sa.CheckConstraint(f"status IN ({ORDER_STATUSES})", name=op.f("ck_orders_status_valid")),
    )
    op.create_index(
        "ix_orders_tenant_id_status_created_at", "orders", ["tenant_id", "status", "created_at"]
    )
    op.create_index("ix_orders_tenant_id_customer_id", "orders", ["tenant_id", "customer_id"])

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movements")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_stock_movements_tenant_id_tenants")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name=op.f("fk_stock_movements_product_id_products"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            name=op.f("fk_stock_movements_order_id_orders"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_id"],
            ["users.tenant_id", "users.id"],
            name=op.f("fk_stock_movements_created_by_id_users"),
        ),
        sa.CheckConstraint(
            "movement_type IN ('inbound', 'outbound', 'adjustment')",
            name=op.f("ck_stock_movements_movement_type_valid"),
        ),
        sa.CheckConstraint(
            "(movement_type = 'inbound' AND quantity > 0)"
            " OR (movement_type = 'outbound' AND quantity < 0)"
            " OR (movement_type = 'adjustment' AND quantity <> 0)",
            name=op.f("ck_stock_movements_quantity_matches_type"),
        ),
        sa.CheckConstraint("balance_after >= 0", name=op.f("ck_stock_movements_balance_after_non_negative")),
    )
    op.create_index(
        "ix_stock_movements_tenant_id_product_id_created_at",
        "stock_movements",
        ["tenant_id", "product_id", "created_at"],
    )

    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_order_items_tenant_id_tenants")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            name=op.f("fk_order_items_order_id_orders"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name=op.f("fk_order_items_product_id_products"),
        ),
        sa.UniqueConstraint("order_id", "product_id", name=op.f("uq_order_items_order_id_product_id")),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_order_items_quantity_positive")),
        sa.CheckConstraint("unit_price >= 0", name=op.f("ck_order_items_unit_price_non_negative")),
    )
    op.create_index("ix_order_items_tenant_id_product_id", "order_items", ["tenant_id", "product_id"])

    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_by_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_status_history")),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_order_status_history_tenant_id_tenants")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            name=op.f("fk_order_status_history_order_id_orders"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "changed_by_id"],
            ["users.tenant_id", "users.id"],
            name=op.f("fk_order_status_history_changed_by_id_users"),
        ),
        sa.CheckConstraint(
            f"from_status IN ({ORDER_STATUSES})", name=op.f("ck_order_status_history_from_status_valid")
        ),
        sa.CheckConstraint(
            f"to_status IN ({ORDER_STATUSES})", name=op.f("ck_order_status_history_to_status_valid")
        ),
    )
    op.create_index(
        "ix_order_status_history_tenant_id_order_id", "order_status_history", ["tenant_id", "order_id"]
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_audit_logs_tenant_id_tenants")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_id"],
            ["users.tenant_id", "users.id"],
            name=op.f("fk_audit_logs_actor_id_users"),
        ),
    )
    op.create_index("ix_audit_logs_tenant_id_created_at", "audit_logs", ["tenant_id", "created_at"])
    op.create_index(
        "ix_audit_logs_tenant_id_entity_type_entity_id",
        "audit_logs",
        ["tenant_id", "entity_type", "entity_id"],
    )

    # Tabelas append-only: o banco recusa UPDATE/DELETE, independentemente da aplicação.
    op.execute(
        """
        CREATE FUNCTION prevent_row_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION USING MESSAGE = 'append-only table: ' || TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION prevent_row_mutation()"
        )


def downgrade() -> None:
    for table in APPEND_ONLY_TABLES:
        op.execute(f"DROP TRIGGER trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION prevent_row_mutation()")

    for table in (
        "audit_logs",
        "order_status_history",
        "order_items",
        "stock_movements",
        "orders",
        "stock_balances",
        "products",
        "customers",
        "refresh_tokens",
        "users",
        "tenants",
    ):
        op.drop_table(table)
