"""Automated tests for direct single-item procurement requests.

Tests:
1. Exact user request: "I want ELEC-SPK-008, 3 units, within 3 days"
   - Evaluates stock, lead time limitation (SUP-002: 4 days > 3 days requested), MOQ constraint (4 units), and landed cost (₹2,780).
2. Unknown / missing SKU: "I want ELEC-UNKNOWN-999, 5 units"
   - Rejects with clear message without hallucinating suppliers or prices.
3. Feasible supplier meeting tight deadline: "I want ELEC-USB-001, 10 units, within 2 days"
   - Finds SUP-004 (1 day lead time) and SUP-001 (2 days lead time) and ranks lowest landed cost.
4. Item confirmation order creation and approval safeguard:
   - "Create order for 4 units of ELEC-SPK-008 from SUP-002" creates a draft order in PENDING_APPROVAL.
   - Does NOT approve or place order automatically.
   - Can be approved and simulated placed via state machine with full SQLite audit trail.
"""

import tempfile
from decimal import Decimal
from pathlib import Path
import pytest

from agents.coordinator import (
    extract_item_request,
    extract_single_order_request,
    generate_response,
    process_procurement_command,
)
from core.persistence import OrderStatus
from core.procurement_service import ProcurementService


@pytest.fixture
def isolated_service():
    """Provides an isolated ProcurementService instance using test SQLite database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_item_procurement.db"
        svc = ProcurementService(
            db_path=db_path,
            inventory_path="data/inventory.json",
            suppliers_path="data/suppliers.json",
        )
        yield svc


# ----------------------------------------------------------------------
# 1. Parsing tests
# ----------------------------------------------------------------------
def test_extract_item_request_exact_query():
    """Verify parsing of 'I want ELEC-SPK-008, 3 units, within 3 days'."""
    text = "I want ELEC-SPK-008, 3 units, within 3 days"
    res = extract_item_request(text)
    assert res is not None
    sku, qty, deadline_days = res
    assert sku == "ELEC-SPK-008"
    assert qty == 3
    assert deadline_days == 3


def test_extract_item_request_variations():
    """Verify variations of units, pcs, hours, and days."""
    r1 = extract_item_request("Need 10 pcs of ELEC-USB-001 in 2d")
    assert r1 == ("ELEC-USB-001", 10, 2)

    r2 = extract_item_request("Procure ELEC-AUD-003, 5 items, deadline 48 hours")
    assert r2 == ("ELEC-AUD-003", 5, 2)

    r3 = extract_item_request("I want ELEC-UNKNOWN-999, 5 units")
    assert r3 == ("ELEC-UNKNOWN-999", 5, None)


def test_extract_single_order_request():
    """Verify parsing confirmation to create order."""
    res = extract_single_order_request("Create order for 4 units of ELEC-SPK-008 from SUP-002")
    assert res == ("ELEC-SPK-008", 4, "SUP-002")


# ----------------------------------------------------------------------
# 2. Exact user query execution: ELEC-SPK-008, 3 units, within 3 days
# ----------------------------------------------------------------------
def test_exact_user_request_handling(isolated_service):
    """Verify handling of 'I want ELEC-SPK-008, 3 units, within 3 days' using real database.

    Requirements verified:
    - Current stock is looked up (6 pieces).
    - Supplier catalog is looked up (only SUP-002 offers it at 4 days lead time).
    - Reports 3-day deadline cannot be met (fastest is 4 days).
    - Computes feasible quantity as 4 units (due to MOQ 4 and pack size 2).
    - Calculates total landed cost = (4 * ₹650) + ₹180 delivery = ₹2,780.
    - Does NOT create or place an order automatically; asks for confirmation.
    """
    user_query = "I want ELEC-SPK-008, 3 units, within 3 days"
    response = process_procurement_command(user_query, service=isolated_service)

    assert response is not None
    assert "ELEC-SPK-008" in response
    assert "Compact IPX6 Bluetooth Speaker (5W)" in response
    assert "Current Stock:" in response
    assert "6 pieces" in response
    assert "Requested Quantity: 3 units" in response
    assert "Requested Deadline: Within 3 days" in response

    # Factual deadline notice
    assert "[DEADLINE NOTICE] No supplier can deliver within 3 days" in response
    assert "Fastest available delivery is 4 days from Zenith Electronics Supply Co (SUP-002)" in response

    # Supplier details & cost calculation
    assert "Unit Price: ₹650.00" in response
    assert "MOQ: 4" in response
    assert "Pack Size: 2" in response
    assert "Feasible Order Qty: 4 units" in response
    assert "Subtotal: ₹2,600.00" in response
    assert "Delivery: ₹180.00" in response
    assert "Total Landed: ₹2,780.00" in response

    # Safeguard verification
    assert "Safeguard: No purchase order has been approved or placed" in response
    assert "Create order for 4 units of ELEC-SPK-008 from SUP-002" in response

    # Verify no purchase orders were silently created
    assert len(isolated_service.list_orders()) == 0


# ----------------------------------------------------------------------
# 3. Missing / Unknown SKU Handling
# ----------------------------------------------------------------------
def test_unknown_sku_handling(isolated_service):
    """Verify that requesting an unknown SKU does not fabricate suppliers or prices."""
    user_query = "I want ELEC-UNKNOWN-999, 5 units, within 3 days"
    response = process_procurement_command(user_query, service=isolated_service)

    assert response is not None
    assert "[SKU UNKNOWN]" in response
    assert "ELEC-UNKNOWN-999" in response
    # Ensure no fabricated supplier names or charges
    assert "Zenith" not in response
    assert "Bharat" not in response
    assert "₹" not in response


# ----------------------------------------------------------------------
# 4. Valid feasible supplier meeting deadline
# ----------------------------------------------------------------------
def test_feasible_supplier_meeting_deadline(isolated_service):
    """Verify that when suppliers CAN meet deadline, best match is recommended."""
    user_query = "I want ELEC-USB-001, 10 units, within 2 days"
    response = process_procurement_command(user_query, service=isolated_service)

    assert response is not None
    assert "FEASIBLE SUPPLIER OFFERS IDENTIFIED" in response
    # SUP-004 has 1 day lead time (meets 2 day deadline)
    assert "RapidExpress Logistics & Wholesale (SUP-004) [BEST MATCH]" in response
    assert "Lead Time: 1 days (meets deadline)" in response
    assert "RECOMMENDED DRAFT ORDER:" in response
    assert "Total Cost:  ₹1,200.00" in response


# ----------------------------------------------------------------------
# 5. Order confirmation, approval safeguard, and persistence
# ----------------------------------------------------------------------
def test_order_confirmation_and_approval_safeguard(isolated_service):
    """Verify that order is only created when user confirms, and requires manual approval."""
    confirm_text = "Create order for 4 units of ELEC-SPK-008 from SUP-002"
    reply = process_procurement_command(confirm_text, service=isolated_service)

    assert reply is not None
    assert "STOCKWISE PROCUREMENT PLAN" in reply
    assert "ELEC-SPK-008" in reply
    assert "PENDING_APPROVAL" in reply
    assert "Total Landed Cost:  ₹2,780.00" in reply

    # Verify order was saved to database in PENDING_APPROVAL
    orders = isolated_service.list_orders()
    assert len(orders) == 1
    po = orders[0]
    assert po.status == OrderStatus.PENDING_APPROVAL
    assert po.total_cost == Decimal("2780.00")
    assert po.items[0].sku == "ELEC-SPK-008"
    assert po.items[0].ordered_quantity == 4

    # Verify audit event recorded
    audit = isolated_service.db.get_order_audit_trail(po.order_id)
    assert len(audit) >= 2
    assert audit[0].from_state == "none"
    assert audit[0].to_state == "draft"
    assert audit[1].from_state == "draft"
    assert audit[1].to_state == "pending_approval"

    # Verify order can be approved
    appr_reply = isolated_service.approve_order(po.order_id, actor="store_manager")
    assert "APPROVED" in appr_reply
    updated_po = isolated_service.get_order(po.order_id)
    assert updated_po.status == OrderStatus.APPROVED

    # Verify simulated placement
    place_reply = isolated_service.simulate_placement(po.order_id, actor="procurement_agent")
    assert "SIMULATED_PLACED" in place_reply
    final_po = isolated_service.get_order(po.order_id)
    assert final_po.status == OrderStatus.SIMULATED_PLACED
