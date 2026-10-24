"""Integration tests for Milestone 4: Coordinator Chat to Procurement Engine."""

import re
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.coordinator import (
    extract_budget,
    extract_order_id,
    extract_supplier_id,
    generate_response,
    process_procurement_command,
)
from core.persistence import OrderStatus
from core.procurement_service import ProcurementService


@pytest.fixture
def isolated_service():
    """Provides a fresh isolated ProcurementService with a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_chat_procurement.db"
        svc = ProcurementService(
            db_path=db_path,
            inventory_path="data/inventory.json",
            suppliers_path="data/suppliers.json",
        )
        yield svc


# ------------------------------------------------------------------
# 1. Regex Entity Extractors
# ------------------------------------------------------------------
def test_extract_budget_variations():
    """Verify budget extraction from various natural language representations."""
    assert extract_budget("Plan restocking with budget ₹20,000") == Decimal("20000")
    assert extract_budget("budget of ₹15,500.50 please") == Decimal("15500.50")
    assert extract_budget("budget: 18000 inr") == Decimal("18000")
    assert extract_budget("We have 25000 rs available") == Decimal("25000")
    assert extract_budget("no budget mentioned here") is None
    assert extract_budget("budget of -500 rs") is None


def test_extract_order_and_supplier_ids():
    """Verify regex extraction of order IDs and supplier IDs."""
    assert extract_order_id("Please approve order PO-A1B2C3D4 immediately") == "PO-A1B2C3D4"
    assert extract_order_id("show details for po-12345678") == "PO-12345678"
    assert extract_order_id("No id here") is None

    assert extract_supplier_id("Supplier SUP-001 has broken down") == "SUP-001"
    assert extract_supplier_id("sup-004 is offline") == "SUP-004"
    assert extract_supplier_id("Generic supplier failed") is None


# ------------------------------------------------------------------
# 2. Natural Language Command Execution via Coordinator
# ------------------------------------------------------------------
def test_chat_inventory_analysis(isolated_service):
    """Test 1: Inventory analysis through the coordinator."""
    reply = generate_response("Check my inventory status and shortages", service=isolated_service)
    assert "STOCKWISE INVENTORY STATUS REPORT" in reply
    assert "Total SKUs Monitored: 15" in reply
    assert "Items Needing Restock" in reply
    assert "[CRITICAL]" in reply
    assert "Next Action" in reply


def test_chat_supplier_comparison(isolated_service):
    """Test 2: Supplier comparison through chat."""
    reply = generate_response("Compare suppliers for my urgent shortages", service=isolated_service)
    assert "STOCKWISE SUPPLIER COMPARISON REPORT" in reply
    assert "Rank 1" in reply
    assert "Unit Cost: ₹" in reply
    assert "Lead Time" in reply


def test_chat_procurement_plan_creation_and_persistence(isolated_service):
    """Test 3: Procurement plan creation and persistence."""
    reply = generate_response("Create a restocking plan with budget ₹18,000", service=isolated_service)
    assert "STOCKWISE PROCUREMENT PLAN" in reply
    assert "Authorized Budget:  ₹18,000.00" in reply
    assert "Status:             PENDING_APPROVAL" in reply
    assert "Order ID:           PO-" in reply
    assert "[NOTE: Synthetic Demo Data" in reply

    # Extract generated Order ID
    order_id = extract_order_id(reply)
    assert order_id is not None

    # Verify order was persisted in database
    po_db = isolated_service.db.get_purchase_order(order_id)
    assert po_db is not None
    assert po_db.status == OrderStatus.PENDING_APPROVAL
    assert po_db.total_cost <= Decimal("18000.00")


def test_chat_budget_enforcement(isolated_service):
    """Test 4: Strict budget enforcement via chat."""
    reply = generate_response("Plan replenishment with budget ₹5,000", service=isolated_service)
    order_id = extract_order_id(reply)
    assert order_id is not None

    po_db = isolated_service.db.get_purchase_order(order_id)
    assert po_db.total_cost <= Decimal("5000.00")
    assert po_db.remaining_budget >= Decimal("0.0")


def test_chat_invalid_budget_clarification(isolated_service):
    """Test 5: Missing or invalid budget input triggers clarification."""
    reply = generate_response("Plan restocking with budget abc", service=isolated_service)
    assert "I noticed you mentioned a budget, but couldn't read the amount" in reply


def test_chat_missing_order_id_clarification(isolated_service):
    """Test 6: Missing order ID in approval/rejection triggers clarification."""
    reply_app = generate_response("Please approve order", service=isolated_service)
    assert "Please specify the exact Order ID to approve" in reply_app

    reply_rej = generate_response("Reject the order", service=isolated_service)
    assert "Please specify the exact Order ID to reject" in reply_rej

    reply_sim = generate_response("Simulate placing order", service=isolated_service)
    assert "Please specify the exact Order ID to place" in reply_sim


def test_chat_order_approval_lifecycle(isolated_service):
    """Tests 7, 9, 10: Approval, attempted placement without approval, and simulated placement."""
    # 1. Create a plan
    plan_reply = generate_response("Create restocking plan with budget ₹20,000", service=isolated_service)
    order_id = extract_order_id(plan_reply)
    assert order_id is not None

    # 2. Attempt simulated placement BEFORE approval (Test 9: forbidden)
    pre_app_place = generate_response(f"Simulate placing order {order_id}", service=isolated_service)
    assert "[INVALID TRANSITION]" in pre_app_place
    assert "Order must be 'approved'" in pre_app_place

    # 3. Approve the order (Test 7: approval)
    app_reply = generate_response(f"Approve order {order_id}", service=isolated_service)
    assert "STOCKWISE ORDER APPROVAL CONFIRMATION" in app_reply
    assert "New Status:   APPROVED" in app_reply

    # 4. Now execute simulated placement (Test 10: placement)
    place_reply = generate_response(f"Simulate placing order {order_id}", service=isolated_service)
    assert "STOCKWISE SIMULATED DISPATCH SUCCESSFUL" in place_reply
    assert "SIMULATED_PLACED (Explicit Test / Demo Mode)" in place_reply
    assert "NO real funds were charged" in place_reply


def test_chat_order_rejection(isolated_service):
    """Test 8: Rejection of a pending order."""
    plan_reply = generate_response("Create restocking plan with budget ₹15,000", service=isolated_service)
    order_id = extract_order_id(plan_reply)
    assert order_id is not None

    rej_reply = generate_response(f"Reject order {order_id} because warehouse is at capacity", service=isolated_service)
    assert "STOCKWISE ORDER REJECTION" in rej_reply
    assert "New Status: REJECTED" in rej_reply
    assert "warehouse is at capacity" in rej_reply

    # Verify terminal status in DB
    po_db = isolated_service.db.get_purchase_order(order_id)
    assert po_db.status == OrderStatus.REJECTED


def test_chat_repeated_approval_and_placement_idempotency(isolated_service):
    """Test 11: Repeated approval and placement without duplicate actions or errors."""
    plan_reply = generate_response("Plan restocking with budget ₹20,000", service=isolated_service)
    order_id = extract_order_id(plan_reply)

    # First approval
    app1 = generate_response(f"Approve order {order_id}", service=isolated_service)
    assert "APPROVED" in app1
    audit_len_1 = len(isolated_service.db.get_order_audit_trail(order_id))

    # Second approval (idempotent repeat)
    app2 = generate_response(f"Approve order {order_id}", service=isolated_service)
    assert "APPROVED" in app2
    audit_len_2 = len(isolated_service.db.get_order_audit_trail(order_id))
    assert audit_len_1 == audit_len_2

    # First placement
    pl1 = generate_response(f"Simulate placing order {order_id}", service=isolated_service)
    assert "SIMULATED_PLACED" in pl1
    place_audit_1 = len(isolated_service.db.get_order_audit_trail(order_id))

    # Second placement (idempotent repeat)
    pl2 = generate_response(f"Simulate placing order {order_id}", service=isolated_service)
    assert "SIMULATED_PLACED" in pl2
    place_audit_2 = len(isolated_service.db.get_order_audit_trail(order_id))
    assert place_audit_1 == place_audit_2


def test_chat_supplier_failure_recovery(isolated_service):
    """Test 12: Supplier failure reporting and automated recalculation through chat."""
    reply = generate_response("Supplier SUP-001 failed. Recalculate my plan with budget ₹20,000", service=isolated_service)
    assert "SUPPLIER FAILURE NOTIFICATION & AUTOMATED REPLANNING" in reply
    assert "Supplier 'SUP-001' has been flagged as FAILED/OFFLINE" in reply
    assert "STOCKWISE PROCUREMENT PLAN" in reply

    order_id = extract_order_id(reply)
    po_db = isolated_service.db.get_purchase_order(order_id)
    # Ensure SUP-001 is completely excluded
    supplier_ids = {item.supplier_id for item in po_db.items}
    assert "SUP-001" not in supplier_ids


def test_chat_ai_fallback_on_unrecognized_query(isolated_service):
    """Test 13: Generic queries fall back gracefully without failing or crashing."""
    reply = generate_response("What is your favorite color?", service=isolated_service)
    assert "StockWise Coordinator" in reply
    assert "Available commands" in reply or "Check inventory" in reply


def test_chat_show_existing_order(isolated_service):
    """Verify 'Show order PO-XXXX' retrieves exact saved details."""
    plan_reply = generate_response("Create restocking plan with budget ₹20,000", service=isolated_service)
    order_id = extract_order_id(plan_reply)

    show_reply = generate_response(f"Show order {order_id}", service=isolated_service)
    assert "STOCKWISE PROCUREMENT PLAN" in show_reply
    assert order_id in show_reply
