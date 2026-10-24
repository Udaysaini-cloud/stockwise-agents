"""Unit tests for core inventory calculations (MASTER_PLAN Phase 3)."""

import pytest
from core.inventory import (
    calculate_stock_requirement,
    load_inventory,
    load_suppliers,
    analyze_all_inventory,
)
from core.schemas import Product


def test_load_synthetic_inventory_and_suppliers():
    """Verify that inventory.json (15 items) and suppliers.json (4 suppliers) load accurately."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")

    assert len(products) == 15
    assert len(suppliers) == 4

    # Verify SKU uniqueness
    skus = [p.sku for p in products]
    assert len(skus) == len(set(skus))

    # Verify supplier IDs
    supplier_ids = [s.id for s in suppliers]
    assert "SUP-001" in supplier_ids
    assert "SUP-004" in supplier_ids


def test_target_stock_and_reorder_calculation():
    """Verify MASTER_PLAN formula:

    Target Stock = Average Daily Sales * (Lead Time + Target Stock Cover) + Safety Stock
    Reorder Quantity = max(0, Target Stock - Available Stock - Outstanding Orders)
    """
    prod = Product(
        sku="TEST-SKU-1",
        name="Test Wireless Mouse",
        current_stock=10,
        average_daily_sales=5.0,
        outstanding_orders=5,
        safety_stock=15,
        target_stock_cover_days=10,
    )
    # Lead time = 4 days
    # Target Stock = 5.0 * (4 + 10) + 15 = 5.0 * 14 + 15 = 70 + 15 = 85
    # Available Stock = 10, Outstanding = 5 -> Effective = 15
    # Reorder = 85 - 15 = 70
    req = calculate_stock_requirement(prod, lead_time_days=4)

    assert req.target_stock == 85
    assert req.effective_stock == 15
    assert req.gross_reorder_qty == 70
    assert req.days_of_stock_left == 2.0  # 10 / 5.0


def test_outstanding_orders_prevent_duplicate_reorders():
    """Ensure that outstanding purchase orders reduce the gross reorder quantity."""
    prod_without_po = Product(
        sku="TEST-SKU-2",
        name="Keyboard",
        current_stock=5,
        average_daily_sales=2.0,
        outstanding_orders=0,
        safety_stock=10,
        target_stock_cover_days=5,
    )
    # Lead time 2 -> Target = 2.0 * (2 + 5) + 10 = 24. Reorder = 24 - 5 = 19
    req_without = calculate_stock_requirement(prod_without_po, lead_time_days=2)
    assert req_without.gross_reorder_qty == 19

    # Now with 15 outstanding orders already placed
    prod_with_po = prod_without_po.model_copy(update={"outstanding_orders": 15})
    # Target = 24. Effective = 5 + 15 = 20. Reorder = 24 - 20 = 4
    req_with = calculate_stock_requirement(prod_with_po, lead_time_days=2)
    assert req_with.gross_reorder_qty == 4


def test_zero_reorder_when_stock_exceeds_target():
    """Reorder quantity must be 0 when available + outstanding exceeds target stock."""
    prod_surplus = Product(
        sku="TEST-SKU-3",
        name="Surplus Item",
        current_stock=100,
        average_daily_sales=2.0,
        outstanding_orders=0,
        safety_stock=10,
        target_stock_cover_days=5,
    )
    # Target = 2.0 * (2 + 5) + 10 = 24. Current = 100 -> Reorder = 0
    req = calculate_stock_requirement(prod_surplus, lead_time_days=2)
    assert req.gross_reorder_qty == 0
    assert req.is_urgent is False


def test_urgent_stockout_detection():
    """Items with stock <= safety stock or days of stock <= lead time are marked urgent."""
    urgent_prod = Product(
        sku="TEST-SKU-4",
        name="Low Stock Item",
        current_stock=2,
        average_daily_sales=4.0,
        outstanding_orders=0,
        safety_stock=10,
        target_stock_cover_days=7,
    )
    req = calculate_stock_requirement(urgent_prod, lead_time_days=3)
    assert req.is_urgent is True
    assert req.days_of_stock_left == 0.5  # 2 / 4.0 = 0.5 days left <= 3 days lead time


def test_analyze_all_inventory_sorts_by_urgency():
    """Verify that inventory analysis ranks urgent shortages at the top."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    analysis = analyze_all_inventory(products, suppliers)

    assert len(analysis) == 15
    # Top item must require reorder
    assert analysis[0].gross_reorder_qty > 0
    assert analysis[0].is_urgent is True
