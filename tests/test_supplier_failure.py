"""Unit tests for supplier failure, unavailable suppliers, and recovery."""

from decimal import Decimal
import pytest
from core.inventory import load_inventory, load_suppliers
from core.optimizer import optimize_purchase_order
from core.schemas import Product, Supplier, SupplierProductOffer
from core.supplier_scoring import rank_suppliers_for_requirement
from core.inventory import calculate_stock_requirement


def test_unavailable_supplier_disqualification():
    """Verify that an unavailable supplier offer (available=False) is never selected."""
    # In suppliers.json, SUP-001 has ELEC-AUD-003 available=False
    suppliers = load_suppliers("data/suppliers.json")
    sup1 = next(s for s in suppliers if s.id == "SUP-001")
    assert sup1.catalog["ELEC-AUD-003"].available is False

    prod_earbuds = Product(
        sku="ELEC-AUD-003",
        name="Wireless TWS Earbuds",
        current_stock=1,
        average_daily_sales=2.0,
        outstanding_orders=0,
        safety_stock=5,
        target_stock_cover_days=7,
    )
    req = calculate_stock_requirement(prod_earbuds, lead_time_days=3)

    # Rank suppliers
    ranked = rank_suppliers_for_requirement(req, suppliers)
    best_offer = ranked[0]

    # Best offer must NOT be SUP-001 because SUP-001 is unavailable
    assert best_offer.available is True
    assert best_offer.supplier_id != "SUP-001"
    # SUP-001 must be marked unavailable
    sup1_rank = next(r for r in ranked if r.supplier_id == "SUP-001")
    assert sup1_rank.available is False
    assert sup1_rank.disqualification_reason is not None


def test_supplier_failure_recovery_fallback():
    """Demonstrate supplier failure recovery:

    When primary supplier SUP-001 is failed/rejected, the optimizer automatically
    falls back to next-best supplier without failing the entire order.
    """
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    budget = Decimal("20000.00")

    # Baseline order: all suppliers healthy
    normal_po = optimize_purchase_order(products, suppliers, budget=budget)
    normal_supplier_ids = {item.supplier_id for item in normal_po.items}
    assert "SUP-001" in normal_supplier_ids

    # Simulate catastrophic failure of SUP-001
    recovery_po = optimize_purchase_order(
        products,
        suppliers,
        budget=budget,
        failed_supplier_ids=["SUP-001"],
    )

    recovery_supplier_ids = {item.supplier_id for item in recovery_po.items}
    # Failed supplier must NOT appear in any item
    assert "SUP-001" not in recovery_supplier_ids
    # Recovery order must still succeed with items from other suppliers
    assert len(recovery_po.items) > 0
    assert recovery_po.total_cost <= budget


def test_all_suppliers_failed_or_unavailable():
    """When all suppliers for an item are failed or unavailable, item is gracefully deferred."""
    products = [
        Product(
            sku="ELEC-SOLO",
            name="Exclusive Proprietary Part",
            current_stock=0,
            average_daily_sales=1.0,
            outstanding_orders=0,
            safety_stock=5,
            target_stock_cover_days=7,
        )
    ]
    # Single supplier offering this SKU
    suppliers = [
        Supplier(
            id="SUP-EXCL",
            name="Exclusive Vendor",
            location="Pune",
            delivery_charge=Decimal("100.0"),
            catalog={
                "ELEC-SOLO": SupplierProductOffer(
                    unit_cost=Decimal("500.0"),
                    lead_time_days=2,
                    moq=5,
                    pack_size=1,
                    available=True,
                )
            },
        )
    ]

    # Baseline: works with adequate budget (14 units * 500 = 7000 + 100 delivery = 7100)
    po_ok = optimize_purchase_order(products, suppliers, budget=Decimal("10000.0"))
    assert len(po_ok.items) == 1

    # Now fail SUP-EXCL
    po_failed = optimize_purchase_order(
        products,
        suppliers,
        budget=Decimal("10000.0"),
        failed_supplier_ids=["SUP-EXCL"],
    )
    assert len(po_failed.items) == 0
    assert len(po_failed.deferred_items) == 1
    assert "failed" in po_failed.deferred_items[0].reason.lower()
