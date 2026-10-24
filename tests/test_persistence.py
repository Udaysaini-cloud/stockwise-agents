"""Unit tests for Milestone 3: SQLite persistence, state transitions, and safe approval."""

import tempfile
from decimal import Decimal
from pathlib import Path
import pytest

from core.inventory import load_inventory, load_suppliers
from core.optimizer import optimize_purchase_order
from core.persistence import (
    InvalidStateTransitionError,
    OrderApprovalService,
    OrderValidationError,
    ProcurementDatabase,
)
from core.schemas import (
    OrderLineItem,
    OrderStatus,
    ProcurementRequest,
    PurchaseOrder,
    Supplier,
    SupplierProductOffer,
)


@pytest.fixture
def temp_db():
    """Provides a fresh temporary SQLite database for test isolation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_stockwise.db"
        db = ProcurementDatabase(db_file)
        yield db


def test_procurement_request_persistence(temp_db):
    """Verify saving and retrieving procurement requests."""
    req = ProcurementRequest(
        request_id="REQ-TEST-001",
        user_query="Restock fast-charging cables under ₹5000",
        budget=Decimal("5000.00"),
        created_at="2026-10-23T12:00:00Z",
        status="processed",
    )
    temp_db.save_procurement_request(req)

    loaded = temp_db.get_procurement_request("REQ-TEST-001")
    assert loaded is not None
    assert loaded.request_id == "REQ-TEST-001"
    assert loaded.budget == Decimal("5000.00")
    assert loaded.user_query == req.user_query


def test_purchase_order_full_persistence_across_connections(temp_db):
    """Verify purchase order, lines, deferred items, and delivery fees persist across fresh connections."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    # Save associated request first to satisfy FK constraint
    req = ProcurementRequest(
        request_id="REQ-TEST-PO",
        user_query="Auto replenishment",
        budget=Decimal("15000.00"),
        created_at="2026-10-23T12:00:00Z",
    )
    temp_db.save_procurement_request(req)
    po = optimize_purchase_order(products, suppliers, budget=Decimal("15000.00"))
    po.request_id = "REQ-TEST-PO"
    assert po.status == OrderStatus.DRAFT

    # Save order
    temp_db.save_purchase_order(po, actor="system")

    # Open fresh DB connection to same file to verify on-disk persistence
    new_db = ProcurementDatabase(temp_db.db_path)
    loaded_po = new_db.get_purchase_order(po.order_id)

    assert loaded_po is not None
    assert loaded_po.order_id == po.order_id
    assert loaded_po.request_id == "REQ-TEST-PO"
    assert loaded_po.status == OrderStatus.DRAFT
    assert loaded_po.total_cost == po.total_cost
    assert loaded_po.remaining_budget == po.remaining_budget
    assert len(loaded_po.items) == len(po.items)
    assert len(loaded_po.deferred_items) == len(po.deferred_items)
    assert loaded_po.supplier_delivery_charges == po.supplier_delivery_charges

    # Verify audit event logged for creation
    audit_trail = new_db.get_order_audit_trail(po.order_id)
    assert len(audit_trail) >= 1
    assert audit_trail[0].to_state == "draft"


def test_valid_state_transition_flow(temp_db):
    """Verify full linear lifecycle: draft -> pending_approval -> approved -> simulated_placed."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    po = optimize_purchase_order(products, suppliers, budget=Decimal("20000.00"))
    temp_db.save_purchase_order(po)

    approval_service = OrderApprovalService(temp_db)

    # 1. Draft -> Pending Approval
    po1 = approval_service.submit_for_approval(po.order_id, actor="store_associate")
    assert po1.status == OrderStatus.PENDING_APPROVAL

    # 2. Pending Approval -> Approved
    po2 = approval_service.approve_order(po.order_id, suppliers=suppliers, actor="store_manager")
    assert po2.status == OrderStatus.APPROVED

    # 3. Approved -> Simulated Placed
    po3 = approval_service.place_simulated_order(po.order_id, suppliers=suppliers, actor="procurement_agent")
    assert po3.status == OrderStatus.SIMULATED_PLACED

    # Verify audit history logged every state transition
    audit_trail = temp_db.get_order_audit_trail(po.order_id)
    states = [a.to_state for a in audit_trail]
    assert "draft" in states
    assert "pending_approval" in states
    assert "approved" in states
    assert "simulated_placed" in states


def test_idempotent_approval_and_placement(temp_db):
    """Verify that repeating approval or simulated placement does not error or duplicate events."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    po = optimize_purchase_order(products, suppliers, budget=Decimal("20000.00"))
    temp_db.save_purchase_order(po)

    approval_service = OrderApprovalService(temp_db)
    approval_service.submit_for_approval(po.order_id)

    # First approval
    po_app1 = approval_service.approve_order(po.order_id, suppliers=suppliers)
    assert po_app1.status == OrderStatus.APPROVED
    audit_len_1 = len(temp_db.get_order_audit_trail(po.order_id))

    # Repeated approval (idempotent call)
    po_app2 = approval_service.approve_order(po.order_id, suppliers=suppliers)
    assert po_app2.status == OrderStatus.APPROVED
    audit_len_2 = len(temp_db.get_order_audit_trail(po.order_id))
    # Must NOT record duplicate audit transitions when repeated
    assert audit_len_1 == audit_len_2

    # First simulated placement
    po_place1 = approval_service.place_simulated_order(po.order_id, suppliers=suppliers)
    assert po_place1.status == OrderStatus.SIMULATED_PLACED
    place_len_1 = len(temp_db.get_order_audit_trail(po.order_id))

    # Repeated simulated placement (idempotent call)
    po_place2 = approval_service.place_simulated_order(po.order_id, suppliers=suppliers)
    assert po_place2.status == OrderStatus.SIMULATED_PLACED
    place_len_2 = len(temp_db.get_order_audit_trail(po.order_id))
    assert place_len_1 == place_len_2


def test_forbidden_state_transitions(temp_db):
    """Verify that illegal transitions raise InvalidStateTransitionError."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    po = optimize_purchase_order(products, suppliers, budget=Decimal("20000.00"))
    temp_db.save_purchase_order(po)

    approval_service = OrderApprovalService(temp_db)

    # Draft cannot jump directly to Approved (must go through pending_approval)
    with pytest.raises(InvalidStateTransitionError):
        approval_service.approve_order(po.order_id, suppliers=suppliers)

    # Draft cannot jump directly to Simulated Placed
    with pytest.raises(InvalidStateTransitionError):
        approval_service.place_simulated_order(po.order_id, suppliers=suppliers)

    # Submit to pending approval
    approval_service.submit_for_approval(po.order_id)

    # Pending cannot jump directly to Simulated Placed (must be approved first)
    with pytest.raises(InvalidStateTransitionError):
        approval_service.place_simulated_order(po.order_id, suppliers=suppliers)

    # Reject order
    approval_service.reject_order(po.order_id, reason="Budget freeze")

    # Terminal state: Rejected cannot transition to Approved or Simulated Placed
    with pytest.raises(InvalidStateTransitionError):
        approval_service.approve_order(po.order_id, suppliers=suppliers)

    with pytest.raises(InvalidStateTransitionError):
        approval_service.submit_for_approval(po.order_id)


def test_pre_approval_budget_violation_failure(temp_db):
    """If budget is reduced before approval, approval must fail with OrderValidationError."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    po = optimize_purchase_order(products, suppliers, budget=Decimal("20000.00"))
    temp_db.save_purchase_order(po)

    approval_service = OrderApprovalService(temp_db)
    approval_service.submit_for_approval(po.order_id)

    # Attempt approval with an authorized cap smaller than the order's cost
    tight_cap = po.total_cost - Decimal("100.00")
    with pytest.raises(OrderValidationError) as exc_info:
        approval_service.approve_order(po.order_id, suppliers=suppliers, max_budget=tight_cap)

    assert "Budget violation" in str(exc_info.value)

    # Verify status transitioned to FAILED
    updated = temp_db.get_purchase_order(po.order_id)
    assert updated.status == OrderStatus.FAILED


def test_pre_approval_supplier_stockout_failure(temp_db):
    """If a supplier goes out of stock prior to approval, revalidation catches it and marks order FAILED."""
    products = load_inventory("data/inventory.json")
    suppliers = load_suppliers("data/suppliers.json")
    po = optimize_purchase_order(products, suppliers, budget=Decimal("20000.00"))
    temp_db.save_purchase_order(po)

    approval_service = OrderApprovalService(temp_db)
    approval_service.submit_for_approval(po.order_id)

    first_item = po.items[0]

    # Simulate that the supplier for first_item just went out of stock
    modified_suppliers = []
    for s in suppliers:
        if s.id == first_item.supplier_id:
            updated_cat = dict(s.catalog)
            orig_offer = updated_cat[first_item.sku]
            updated_cat[first_item.sku] = orig_offer.model_copy(update={"available": False})
            modified_suppliers.append(s.model_copy(update={"catalog": updated_cat}))
        else:
            modified_suppliers.append(s)

    # Approval must be rejected by revalidation
    with pytest.raises(OrderValidationError) as exc_info:
        approval_service.approve_order(po.order_id, suppliers=modified_suppliers)

    assert "out of stock" in str(exc_info.value)
    updated = temp_db.get_purchase_order(po.order_id)
    assert updated.status == OrderStatus.FAILED
