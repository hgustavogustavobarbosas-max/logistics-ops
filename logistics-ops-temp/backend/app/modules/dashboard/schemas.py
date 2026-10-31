import uuid
from datetime import date

from pydantic import BaseModel


class LowStockItem(BaseModel):
    product_id: uuid.UUID
    sku: str
    name: str
    unit: str
    on_hand: int
    reserved: int
    available: int
    min_stock: int


class DailyCount(BaseModel):
    date: date
    count: int


class DashboardSummary(BaseModel):
    orders_by_status: dict[str, int]
    open_orders: int
    units_on_hand: int
    units_reserved: int
    low_stock_count: int
    low_stock_items: list[LowStockItem]
    orders_last_7_days: list[DailyCount]
    delivered_last_30_days: int
    avg_fulfillment_hours: float | None
