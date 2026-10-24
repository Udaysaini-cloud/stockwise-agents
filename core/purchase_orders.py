"""StockWise Purchase Order Structure and Utilities.

Defines PO generation, formatting, and summary helpers.
"""

import uuid
from decimal import Decimal
from typing import Dict, List
from core.schemas import DeferredItem, OrderLineItem, PurchaseOrder


def create_empty_purchase_order(budget: Decimal, order_id: str | None = None) -> PurchaseOrder:
    """Create an initialized, empty purchase order structure."""
    if order_id is None:
        order_id = f"PO-{uuid.uuid4().hex[:8].upper()}"

    return PurchaseOrder(
        order_id=order_id,
        items=[],
        supplier_delivery_charges={},
        subtotal=Decimal("0.0"),
        total_delivery_charges=Decimal("0.0"),
        total_cost=Decimal("0.0"),
        budget=budget,
        remaining_budget=budget,
        deferred_items=[],
    )


def format_purchase_order_summary(po: PurchaseOrder) -> str:
    """Generates a clean text summary of the purchase order."""
    lines = [
        f"============================================================",
        f"STOCKWISE PURCHASE ORDER: {po.order_id}",
        f"============================================================",
        f"Budget:             ₹{po.budget:,.2f}",
        f"Subtotal:           ₹{po.subtotal:,.2f}",
        f"Delivery Charges:   ₹{po.total_delivery_charges:,.2f}",
        f"Total Landed Cost:  ₹{po.total_cost:,.2f}",
        f"Remaining Budget:   ₹{po.remaining_budget:,.2f}",
        f"------------------------------------------------------------",
        f"ORDER LINE ITEMS ({len(po.items)} items):",
    ]

    if not po.items:
        lines.append("  (No items ordered)")
    else:
        for idx, item in enumerate(po.items, 1):
            lines.append(
                f"  {idx}. [{item.sku}] {item.product_name}\n"
                f"     Supplier: {item.supplier_name} ({item.supplier_id}) | Lead: {item.lead_time_days}d\n"
                f"     Qty: {item.ordered_quantity} units (Pack: {item.pack_size}, MOQ: {item.moq}) "
                f"@ ₹{item.unit_cost:,.2f}/unit = ₹{item.line_total:,.2f}"
            )

    if po.supplier_delivery_charges:
        lines.append(f"------------------------------------------------------------")
        lines.append("DELIVERY CHARGES BY SUPPLIER:")
        for sup_id, fee in po.supplier_delivery_charges.items():
            lines.append(f"  - {sup_id}: ₹{fee:,.2f}")

    if po.deferred_items:
        lines.append(f"------------------------------------------------------------")
        lines.append(f"DEFERRED ITEMS ({len(po.deferred_items)} items):")
        for idx, d in enumerate(po.deferred_items, 1):
            est = f" (Est. cost: ₹{d.estimated_cost:,.2f})" if d.estimated_cost else ""
            lines.append(f"  {idx}. [{d.sku}] {d.product_name} - Needed: {d.needed_quantity}{est}\n     Reason: {d.reason}")

    lines.append(f"============================================================")
    return "\n".join(lines)
