"""Unit tests for the budget-constrained purchase-order optimizer."""

from decimal import Decimal
import pytest
from core.inventory import load_inventory, load_suppliers
from core.optimizer import optimize_purchase_order
from core.purchase_orders import format_purchase_order_summary
from core.schemas import Product, Supplier, SupplierProductOffer
from core.supplier_scoring import compute_feasible_quantity, round_up_to_pack_size


def test_round_up_to_pack_size():
    """Verify pack size rounding logic."""
    assert round_up_to_pack_size(7, 5) == 10
    assert round_up_to_pack_size(10, 5) == 10
    assert round_up_to_pack_size(1, 10) == 10
    assert round_up_to_pack_size(12, 1) == 12


def test_compute_feasible_quantity():
    """Verify that feasible quantity satisfies both MOQ and pack size multiples."""
    # Needed 3, MOQ 10, Pack size 5 -> max(3, 10)=10, multiple of 5 -> 10
    assert compute_feasible_quantity(gross_needed=3, moq=10, pack_size=5) == 10
    # Needed 12, MOQ 10, Pack size 5 -> max(12, 10)=12, round to 5 -> 15
    assert compute_feasible_quantity(gross_needed=12, moq=10, pack_size=5) == 15
    # Needed 22, MOQ 50, Pack size 25 -> max(22, 50)=50, multiple of 25 -> 50
    assert compute_feasible_quantity(gross_needed=22, moq=50, pack_size=25) == 50


def test_budget_never_exceeded_default_budget():
    """Verify that optimizer generated order strictly stays within the ₹20,000 budget."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    budget = Decimal("20000.00")

    po = optimize_purchase_order(products, suppliers, budget=budget)

    assert isinstance(po.total_cost, Decimal)
    assert po.total_cost <= budget
    assert po.remaining_budget >= Decimal("0.0")
    assert po.remaining_budget == budget - po.total_cost
    assert len(po.items) > 0

    # Verify line totals
    sum_items = sum(item.line_total for item in po.items)
    assert sum_items == po.subtotal
    sum_delivery = sum(po.supplier_delivery_charges.values())
    assert sum_delivery == po.total_delivery_charges
    assert po.total_cost == po.subtotal + po.total_delivery_charges


def test_tight_budget_enforcement():
    """Under a tiny ₹1,000 budget, the engine must not exceed budget and must defer expensive items."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    tiny_budget = Decimal("1000.00")

    po = optimize_purchase_order(products, suppliers, budget=tiny_budget)

    assert po.total_cost <= tiny_budget
    assert po.remaining_budget >= Decimal("0.0")
    assert len(po.deferred_items) > 0
    # Check that deferred items contain explanations
    for d in po.deferred_items:
        assert len(d.reason) > 0


def test_zero_budget_impossible_order():
    """Under ₹0 budget, no items should be purchased and all should be deferred."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    zero_budget = Decimal("0.00")

    po = optimize_purchase_order(products, suppliers, budget=zero_budget)

    assert po.total_cost == Decimal("0.0")
    assert len(po.items) == 0
    assert po.remaining_budget == Decimal("0.0")
    assert len(po.deferred_items) > 0


def test_format_purchase_order_summary():
    """Verify summary formatter prints a human-readable table with INR values."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    po = optimize_purchase_order(products, suppliers, budget=Decimal("15000.00"))

    summary = format_purchase_order_summary(po)
    assert "STOCKWISE PURCHASE ORDER" in summary
    assert "₹15,000.00" in summary
    assert "ORDER LINE ITEMS" in summary
