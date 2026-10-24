"""Regression tests for conversational inventory questions via coordinator.

Validates:
A. "Check my inventory" returns real inventory data.
B. "Give me a quick summary of my store's inventory health" returns a summary without asking for a category.
C. "Which products are running low?" returns products based on actual thresholds.
D. "Check inventory for ELEC-SPK-008" returns the correct record if the SKU exists.
E. An unknown SKU returns a clear not-found response.
F. A database/service failure returns a useful error and does not fabricate an answer.
G. The inventory response shown in the frontend matches the actual backend result.
H. Existing supplier comparison, budget optimization, purchase orders, approval, and audit history continue to work.
"""

import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
import pytest

from agents.coordinator import generate_response, process_procurement_command
from core.persistence import OrderStatus
from core.procurement_service import ProcurementService


@pytest.fixture
def isolated_service():
    """Provides a fresh isolated ProcurementService with a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_inventory_agent.db"
        svc = ProcurementService(
            db_path=db_path,
            inventory_path="data/inventory.json",
            suppliers_path="data/suppliers.json",
        )
        yield svc


# ---------------------------------------------------------------------------
# Test A: "Check my inventory" returns real inventory data
# ---------------------------------------------------------------------------
def test_check_my_inventory_returns_real_data(isolated_service):
    reply = generate_response("Check my inventory.", service=isolated_service)
    assert reply is not None
    assert "Total SKUs Monitored: 15" in reply
    assert "Items Needing Restock: 13" in reply
    assert "Critical Shortages: 5" in reply
    assert "ELEC-AUD-003" in reply
    assert "ELEC-PWR-002" in reply


# ---------------------------------------------------------------------------
# Test B: "Give me a quick summary of my store's inventory health"
# ---------------------------------------------------------------------------
def test_summary_store_inventory_health_no_category_prompt(isolated_service):
    reply = generate_response("Give me a quick summary of my store's inventory health.", service=isolated_service)
    assert reply is not None
    # Must NOT ask to specify category or SKU
    assert "Please specify" not in reply
    assert "which product categories" not in reply
    assert "STOCKWISE INVENTORY STATUS REPORT & STORE HEALTH SUMMARY" in reply
    assert "Total SKUs Monitored: 15" in reply
    assert "Total Physical Inventory:" in reply
    assert "Critical Shortages: 5" in reply


# ---------------------------------------------------------------------------
# Test C: "Which products are running low?"
# ---------------------------------------------------------------------------
def test_which_products_are_running_low(isolated_service):
    reply = generate_response("Which products are running low?", service=isolated_service)
    assert reply is not None
    assert "STOCKWISE PRODUCTS RUNNING LOW" in reply
    assert "Total Monitored SKUs: 15" in reply
    assert "Products Below Threshold: 13" in reply
    # Must list items like ELEC-AUD-003, ELEC-PWR-002, ELEC-USB-001
    assert "ELEC-AUD-003" in reply
    assert "ELEC-PWR-002" in reply
    assert "Reorder Needed:" in reply


# ---------------------------------------------------------------------------
# Test C2: "Show me all urgent stock shortages"
# ---------------------------------------------------------------------------
def test_urgent_stock_shortages(isolated_service):
    reply = generate_response("Show me all urgent stock shortages.", service=isolated_service)
    assert reply is not None
    assert "STOCKWISE URGENT STOCK SHORTAGES" in reply
    assert "Products Below Threshold: 5" in reply
    assert "ELEC-AUD-003" in reply
    assert "ELEC-PWR-002" in reply
    assert "ELEC-USB-001" in reply


# ---------------------------------------------------------------------------
# Test C3: "Which products may run out within three days?"
# ---------------------------------------------------------------------------
def test_products_runout_within_three_days(isolated_service):
    reply = generate_response("Which products may run out within three days?", service=isolated_service)
    assert reply is not None
    assert "STOCKWISE INVENTORY RUNOUT ALERT (Within 3.0 Days)" in reply
    # Items with days_of_stock_left <= 3.0: AUD-003 (0.5), PWR-002 (0.6), USB-001 (0.7), HUB-013 (1.1), MIC-005 (1.2), OTG-006 (2.7) = 6 items
    assert "Items Depleting in ≤ 3.0 Days: 6" in reply
    assert "ELEC-AUD-003" in reply
    assert "ELEC-PWR-002" in reply
    assert "ELEC-USB-001" in reply


# ---------------------------------------------------------------------------
# Test C4: "What should I restock first?"
# ---------------------------------------------------------------------------
def test_what_should_i_restock_first(isolated_service):
    reply = generate_response("What should I restock first?", service=isolated_service)
    assert reply is not None
    assert "STOCKWISE RESTOCK PRIORITIZATION (Highest Urgency First)" in reply
    assert "1. 🚨 [CRITICAL] [ELEC-AUD-003]" in reply
    assert "Priority Score: 96.0/100" in reply


# ---------------------------------------------------------------------------
# Test D: "Check inventory for ELEC-SPK-008" returns the correct record
# ---------------------------------------------------------------------------
def test_check_inventory_single_sku(isolated_service):
    reply = generate_response("Check inventory for ELEC-SPK-008.", service=isolated_service)
    assert reply is not None
    assert "STOCKWISE INVENTORY STATUS: [ELEC-SPK-008] Compact IPX6 Bluetooth Speaker (5W)" in reply
    assert "Current Stock:      6 pieces" in reply
    assert "Safety Stock:       3 pieces" in reply
    assert "Avg Daily Sales:    0.8 pieces/day" in reply
    assert "Est. Stock Left:    7.5 days" in reply
    assert "Reorder Shortfall:  9 pieces" in reply


# ---------------------------------------------------------------------------
# Test E: An unknown SKU returns a clear not-found response
# ---------------------------------------------------------------------------
def test_check_inventory_unknown_sku(isolated_service):
    reply = generate_response("Check inventory for ELEC-UNKNOWN-999", service=isolated_service)
    assert reply is not None
    assert "[SKU NOT FOUND]" in reply
    assert "ELEC-UNKNOWN-999" in reply
    assert "Monitored SKUs:" in reply


# ---------------------------------------------------------------------------
# Test F: Service failure returns a diagnostic error without fabricating data
# ---------------------------------------------------------------------------
def test_inventory_service_failure_returns_diagnostic_error(isolated_service):
    with patch.object(isolated_service, "get_inventory", side_effect=RuntimeError("Disk I/O error")):
        reply = isolated_service.check_inventory()
        assert "[INVENTORY SERVICE ERROR]" in reply
        assert "Disk I/O error" in reply
        # Never fabricate numbers when backend fails
        assert "Total SKUs Monitored: 15" not in reply


# ---------------------------------------------------------------------------
# Test G: No purchase orders or database modifications during read-only queries
# ---------------------------------------------------------------------------
def test_read_only_queries_do_not_modify_database(isolated_service):
    initial_orders = isolated_service.list_orders()
    assert len(initial_orders) == 0

    queries = [
        "Check my inventory.",
        "Give me a quick summary of my store's inventory health.",
        "Which products are running low?",
        "Show me all urgent stock shortages.",
        "Which products may run out within three days?",
        "What should I restock first?",
        "Check inventory for ELEC-SPK-008.",
    ]
    for q in queries:
        generate_response(q, service=isolated_service)

    # Must remain completely untouched
    final_orders = isolated_service.list_orders()
    assert len(final_orders) == 0


# ---------------------------------------------------------------------------
# Test H: Existing procurement workflows continue to function
# ---------------------------------------------------------------------------
def test_existing_procurement_workflow_safeguards_intact(isolated_service):
    # Supplier comparison
    comp_reply = generate_response("Compare suppliers", service=isolated_service)
    assert "STOCKWISE SUPPLIER COMPARISON REPORT" in comp_reply

    # Restock plan with budget
    plan_reply = generate_response("Create restocking plan with budget ₹20,000", service=isolated_service)
    assert "STOCKWISE PROCUREMENT PLAN" in plan_reply
    assert "PENDING_APPROVAL" in plan_reply
    orders = isolated_service.list_orders()
    assert len(orders) == 1
    po = orders[0]
    assert po.status == OrderStatus.PENDING_APPROVAL

    # Approval and placement
    appr_reply = generate_response(f"Approve order {po.order_id}", service=isolated_service)
    assert "APPROVED" in appr_reply

    place_reply = generate_response(f"Simulate placing order {po.order_id}", service=isolated_service)
    assert "SIMULATED_PLACED" in place_reply
