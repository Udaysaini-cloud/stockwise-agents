"""StockWise Supplier Scoring.

Compares supplier offers for each SKU based on:
- Availability
- Total landed unit cost
- Lead time and stockout urgency
- Minimum Order Quantity (MOQ)
- Pack size alignment
"""

import math
from decimal import Decimal
from typing import Dict, List, Optional
from core.schemas import StockRequirement, Supplier, SupplierScore


def round_up_to_pack_size(qty: int, pack_size: int) -> int:
    """Rounds quantity up to the next integer multiple of pack_size."""
    if pack_size <= 1:
        return qty
    remainder = qty % pack_size
    if remainder == 0:
        return qty
    return qty + (pack_size - remainder)


def compute_feasible_quantity(gross_needed: int, moq: int, pack_size: int) -> int:
    """Computes the exact purchasable quantity adhering to MOQ and pack size."""
    # First ensure at least MOQ
    base_qty = max(gross_needed, moq)
    # Then round up to multiple of pack size
    return round_up_to_pack_size(base_qty, pack_size)


def evaluate_supplier_for_sku(
    supplier: Supplier,
    sku: str,
    needed_qty: int,
    days_of_stock_left: float,
    failed_supplier_ids: Optional[List[str]] = None,
) -> SupplierScore:
    """Evaluates and scores a single supplier's offer for an SKU."""
    if failed_supplier_ids is None:
        failed_supplier_ids = []

    if supplier.id in failed_supplier_ids:
        return SupplierScore(
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            sku=sku,
            unit_cost=Decimal("0.0"),
            lead_time_days=0,
            moq=1,
            pack_size=1,
            available=False,
            feasible_quantity=0,
            item_total_cost=Decimal("0.0"),
            composite_score=-999.0,
            disqualification_reason=f"Supplier {supplier.id} flagged as failed/unresponsive",
        )

    if sku not in supplier.catalog:
        return SupplierScore(
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            sku=sku,
            unit_cost=Decimal("0.0"),
            lead_time_days=0,
            moq=1,
            pack_size=1,
            available=False,
            feasible_quantity=0,
            item_total_cost=Decimal("0.0"),
            composite_score=-999.0,
            disqualification_reason="SKU not offered in catalog",
        )

    offer = supplier.catalog[sku]

    if not offer.available:
        return SupplierScore(
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            sku=sku,
            unit_cost=offer.unit_cost,
            lead_time_days=offer.lead_time_days,
            moq=offer.moq,
            pack_size=offer.pack_size,
            available=False,
            feasible_quantity=0,
            item_total_cost=Decimal("0.0"),
            composite_score=-999.0,
            disqualification_reason="Temporarily out of stock with supplier",
        )

    # Compute feasible quantity
    feasible_qty = compute_feasible_quantity(needed_qty, offer.moq, offer.pack_size)
    item_total_cost = offer.unit_cost * Decimal(feasible_qty)

    # Composite scoring: higher score is better
    # Factors:
    # 1. Price factor (lower price -> higher score)
    # 2. Lead time factor (lower lead time -> higher score, especially if urgent)
    # 3. Overshoot penalty (if MOQ causes huge over-purchase relative to need)
    overshoot_ratio = (feasible_qty / needed_qty) if needed_qty > 0 else 1.0

    # Base score
    # Lead time penalty: -10 points per lead day. If stock left <= lead time, double the penalty.
    lead_time_penalty = offer.lead_time_days * 10.0
    if days_of_stock_left <= offer.lead_time_days:
        lead_time_penalty += 30.0  # High risk of stockout during transit

    # Overshoot penalty: penalty if forced to buy > 2x needed
    overshoot_penalty = max(0.0, (overshoot_ratio - 1.0) * 20.0)

    # Price factor: normalize relative to 1000 base
    cost_float = float(offer.unit_cost)
    price_score = max(0.0, 200.0 - (cost_float / 5.0))

    composite_score = round(price_score - lead_time_penalty - overshoot_penalty, 2)

    return SupplierScore(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        sku=sku,
        unit_cost=offer.unit_cost,
        lead_time_days=offer.lead_time_days,
        moq=offer.moq,
        pack_size=offer.pack_size,
        available=True,
        feasible_quantity=feasible_qty,
        item_total_cost=item_total_cost,
        composite_score=composite_score,
        disqualification_reason=None,
    )


def rank_suppliers_for_requirement(
    req: StockRequirement,
    suppliers: List[Supplier],
    failed_supplier_ids: Optional[List[str]] = None,
) -> List[SupplierScore]:
    """Scores and ranks all feasible suppliers for a specific stock requirement."""
    scores: List[SupplierScore] = []
    for s in suppliers:
        eval_score = evaluate_supplier_for_sku(
            supplier=s,
            sku=req.sku,
            needed_qty=req.gross_reorder_qty,
            days_of_stock_left=req.days_of_stock_left,
            failed_supplier_ids=failed_supplier_ids,
        )
        scores.append(eval_score)

    # Separate available and unavailable
    available_scores = [sc for sc in scores if sc.available and sc.disqualification_reason is None]
    unavailable_scores = [sc for sc in scores if not sc.available or sc.disqualification_reason is not None]

    # Rank available by highest composite score (or lowest total cost on tie)
    available_scores.sort(key=lambda s: (s.composite_score, -float(s.item_total_cost)), reverse=True)

    return available_scores + unavailable_scores
