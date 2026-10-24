"""StockWise Budget-Constrained Purchase Order Optimizer.

Deterministic optimization algorithm that:
1. Filters products requiring restock (gross_reorder_qty > 0).
2. Prioritizes products by stockout urgency (days of stock left, safety stock).
3. Evaluates all suppliers for MOQ, pack size, landed cost, and availability.
4. Selects feasible supplier offers that fit strictly within the monetary budget (Decimal).
5. Defers items that exceed budget, violate MOQ constraints, or lack available suppliers.
6. Guarantees total_cost <= budget under all conditions.
"""

import uuid
from decimal import Decimal
from typing import Dict, List, Optional
from core.inventory import analyze_all_inventory
from core.schemas import (
    DeferredItem,
    OrderLineItem,
    Product,
    PurchaseOrder,
    StockRequirement,
    Supplier,
)
from core.supplier_scoring import rank_suppliers_for_requirement


def optimize_purchase_order(
    products: List[Product],
    suppliers: List[Supplier],
    budget: Decimal | float | int = Decimal("20000.0"),
    failed_supplier_ids: Optional[List[str]] = None,
    order_id: Optional[str] = None,
) -> PurchaseOrder:
    """Generates a deterministic, budget-compliant purchase order.

    Args:
        products: Current inventory products.
        suppliers: Available supplier profiles and catalogs.
        budget: Maximum spending limit in INR (enforced via Decimal).
        failed_supplier_ids: List of supplier IDs to ignore (for simulation/failure recovery).
        order_id: Optional custom order ID.

    Returns:
        PurchaseOrder: Complete PO with line items, delivery charges, remaining budget, and deferred items.
    """
    if not isinstance(budget, Decimal):
        budget = Decimal(str(budget))

    if budget < Decimal("0.0"):
        budget = Decimal("0.0")

    if order_id is None:
        order_id = f"PO-{uuid.uuid4().hex[:8].upper()}"

    if failed_supplier_ids is None:
        failed_supplier_ids = []

    # Map suppliers for easy lookup
    supplier_map: Dict[str, Supplier] = {s.id: s for s in suppliers}

    # 1. Analyze inventory and identify requirements
    all_requirements = analyze_all_inventory(products, suppliers)
    reorder_requirements = [r for r in all_requirements if r.gross_reorder_qty > 0]

    # Initialize order tracking
    allocated_items: List[OrderLineItem] = []
    supplier_delivery_charges: Dict[str, Decimal] = {}
    deferred_items: List[DeferredItem] = []

    current_subtotal = Decimal("0.0")
    current_delivery = Decimal("0.0")

    # 2. Iterate through sorted requirements
    for req in reorder_requirements:
        # Rank available suppliers for this requirement
        ranked_offers = rank_suppliers_for_requirement(
            req=req,
            suppliers=suppliers,
            failed_supplier_ids=failed_supplier_ids,
        )

        valid_offers = [o for o in ranked_offers if o.available and o.disqualification_reason is None]

        if not valid_offers:
            # Check why no valid offer
            reasons = [o.disqualification_reason for o in ranked_offers if o.disqualification_reason]
            reason_text = reasons[0] if reasons else "No suppliers catalog this product"
            deferred_items.append(
                DeferredItem(
                    sku=req.sku,
                    product_name=req.name,
                    needed_quantity=req.gross_reorder_qty,
                    reason=f"No available suppliers: {reason_text}",
                    estimated_cost=None,
                )
            )
            continue

        # Try to fit the best offer, or fallback to second best if best exceeds budget
        allocated = False
        best_cost_seen = valid_offers[0].item_total_cost

        for offer in valid_offers:
            sup = supplier_map.get(offer.supplier_id)
            if not sup:
                continue

            item_cost = offer.item_total_cost
            # Delivery fee is only charged once per supplier in this order
            additional_delivery = Decimal("0.0")
            if offer.supplier_id not in supplier_delivery_charges:
                additional_delivery = sup.delivery_charge

            total_cost_with_item = (
                current_subtotal + current_delivery + item_cost + additional_delivery
            )

            # Strict budget check: MUST NOT exceed budget
            if total_cost_with_item <= budget:
                # Accept item
                line_item = OrderLineItem(
                    sku=req.sku,
                    product_name=req.name,
                    supplier_id=offer.supplier_id,
                    supplier_name=offer.supplier_name,
                    ordered_quantity=offer.feasible_quantity,
                    unit_cost=offer.unit_cost,
                    line_total=item_cost,
                    lead_time_days=offer.lead_time_days,
                    pack_size=offer.pack_size,
                    moq=offer.moq,
                )
                allocated_items.append(line_item)
                current_subtotal += item_cost

                if additional_delivery > Decimal("0.0"):
                    supplier_delivery_charges[offer.supplier_id] = sup.delivery_charge
                    current_delivery += sup.delivery_charge

                allocated = True
                break

        if not allocated:
            # Could not fit any offer within remaining budget
            remaining = budget - (current_subtotal + current_delivery)
            deferred_items.append(
                DeferredItem(
                    sku=req.sku,
                    product_name=req.name,
                    needed_quantity=req.gross_reorder_qty,
                    reason=(
                        f"Insufficient budget: Lowest feasible offer ₹{best_cost_seen:,.2f} "
                        f"exceeds remaining budget ₹{remaining:,.2f}"
                    ),
                    estimated_cost=best_cost_seen,
                )
            )

    total_cost = current_subtotal + current_delivery
    remaining_budget = budget - total_cost

    return PurchaseOrder(
        order_id=order_id,
        items=allocated_items,
        supplier_delivery_charges=supplier_delivery_charges,
        subtotal=current_subtotal,
        total_delivery_charges=current_delivery,
        total_cost=total_cost,
        budget=budget,
        remaining_budget=remaining_budget,
        deferred_items=deferred_items,
    )
