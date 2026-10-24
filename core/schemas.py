"""StockWise Data Schemas.

Pydantic data models for inventory, suppliers, scoring, and purchase orders.
All monetary amounts use Decimal.
"""

from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class Product(BaseModel):
    """Product inventory record."""

    sku: str = Field(..., description="Unique product SKU identifier")
    name: str = Field(..., description="Product name")
    category: str = Field("General", description="Product category")
    current_stock: int = Field(..., ge=0, description="Current on-hand stock quantity")
    average_daily_sales: float = Field(..., ge=0.0, description="Average daily unit sales rate")
    outstanding_orders: int = Field(0, ge=0, description="Units already ordered and pending delivery")
    safety_stock: int = Field(..., ge=0, description="Minimum buffer stock units")
    target_stock_cover_days: int = Field(..., ge=0, description="Desired coverage horizon in days")
    unit: str = Field("piece", description="Inventory unit")


class SupplierProductOffer(BaseModel):
    """Supplier terms for a single product."""

    unit_cost: Decimal = Field(..., gt=Decimal("0.0"), description="Unit cost in INR")
    lead_time_days: int = Field(..., ge=0, description="Expected delivery lead time in days")
    moq: int = Field(..., ge=1, description="Minimum order quantity in units")
    pack_size: int = Field(1, ge=1, description="Multiple of units per pack")
    available: bool = Field(True, description="Whether the supplier currently has stock")

    @field_validator("unit_cost", mode="before")
    @classmethod
    def parse_cost(cls, v) -> Decimal:
        if isinstance(v, (int, float, str)):
            return Decimal(str(v))
        return v


class Supplier(BaseModel):
    """Supplier profile and catalog."""

    id: str = Field(..., description="Unique supplier identifier (e.g. SUP-001)")
    name: str = Field(..., description="Supplier company name")
    location: str = Field("", description="Warehouse or hub location")
    delivery_charge: Decimal = Field(Decimal("0.0"), ge=Decimal("0.0"), description="Flat delivery fee per order in INR")
    catalog: Dict[str, SupplierProductOffer] = Field(..., description="Mapping of SKU to supplier offer")

    @field_validator("delivery_charge", mode="before")
    @classmethod
    def parse_charge(cls, v) -> Decimal:
        if isinstance(v, (int, float, str)):
            return Decimal(str(v))
        return v


class StockRequirement(BaseModel):
    """Computed stock shortage and replenishment requirement for a product."""

    sku: str
    name: str
    current_stock: int
    outstanding_orders: int
    effective_stock: int
    average_daily_sales: float
    lead_time_days_used: int
    safety_stock: int
    target_stock_cover_days: int
    target_stock: int
    gross_reorder_qty: int
    days_of_stock_left: float
    urgency_score: float
    is_urgent: bool


class SupplierScore(BaseModel):
    """Scored evaluation of a supplier for a required item."""

    supplier_id: str
    supplier_name: str
    sku: str
    unit_cost: Decimal
    lead_time_days: int
    moq: int
    pack_size: int
    available: bool
    feasible_quantity: int
    item_total_cost: Decimal
    composite_score: float
    disqualification_reason: Optional[str] = None


class OrderLineItem(BaseModel):
    """Line item in a generated purchase order."""

    sku: str
    product_name: str
    supplier_id: str
    supplier_name: str
    ordered_quantity: int
    unit_cost: Decimal
    line_total: Decimal
    lead_time_days: int
    pack_size: int
    moq: int


class DeferredItem(BaseModel):
    """Product requirement deferred with specific justification."""

    sku: str
    product_name: str
    needed_quantity: int
    reason: str
    estimated_cost: Optional[Decimal] = None


class OrderStatus(str, Enum):
    """Explicit lifecycle states for a StockWise purchase order."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SIMULATED_PLACED = "simulated_placed"
    REJECTED = "rejected"
    FAILED = "failed"


class ProcurementRequest(BaseModel):
    """Incoming user procurement request record."""

    request_id: str
    user_query: str
    budget: Decimal
    created_at: str
    status: str = "processed"


class OrderAuditEvent(BaseModel):
    """Immutable audit trail log for purchase order state transitions."""

    event_id: str
    order_id: str
    from_state: str
    to_state: str
    reason: str
    timestamp: str
    actor: str = "system"


class PurchaseOrder(BaseModel):
    """Full purchase order containing line items, totals, budget analysis and lifecycle state."""

    order_id: str
    request_id: Optional[str] = None
    status: OrderStatus = OrderStatus.DRAFT
    items: List[OrderLineItem]
    supplier_delivery_charges: Dict[str, Decimal]
    subtotal: Decimal
    total_delivery_charges: Decimal
    total_cost: Decimal
    budget: Decimal
    remaining_budget: Decimal
    deferred_items: List[DeferredItem]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

