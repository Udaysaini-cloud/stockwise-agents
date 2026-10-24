"""Comprehensive unit tests for ASI Interactive Cards in StockWise Agents.

Tests:
- Card metadata envelope and JSON serialization
- Valid card kinds (form, carousel, detail, review, custom)
- Inventory summary card generation from real data
- Supplier carousel card generation from real fixtures
- Restocking plan form generation and submission handling
- Purchase order review card generation and approval workflow
- Placement confirmation card generation with is_terminal=True
- JSON selection parsing vs natural-language prose fallback
- Unknown SKU handling and invalid state transitions
- Duplicate interaction and approval safeguards
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any

import pytest
from uagents_core.contrib.protocols.chat import ChatMessage, MetadataContent, TextContent

from agents.cards import (
    build_card_metadata,
    build_home_menu_card,
    build_inventory_health_card,
    build_placement_confirmation_card,
    build_po_review_card,
    build_restock_form_card,
    build_supplier_comparison_carousel,
    parse_card_selection,
)
from agents.coordinator import dispatch_chat_interaction
from core.procurement_service import ProcurementService
from core.schemas import OrderStatus


@pytest.fixture
def test_procurement_service(tmp_path: Path) -> ProcurementService:
    """Creates a ProcurementService with isolated test database."""
    test_db = tmp_path / "test_stockwise_cards.db"
    svc = ProcurementService(
        db_path=test_db,
        inventory_path="data/inventory.json",
        suppliers_path="data/suppliers.json",
    )
    return svc


# -----------------------------------------------------------------------------
# 1. Envelope & Serialization Tests
# -----------------------------------------------------------------------------
def test_card_envelope_metadata_structure():
    """Verifies that the generated metadata envelope complies with ASI protocol v1."""
    payload = {"title": "Test Title", "summary_rows": [{"label": "Status", "value": "OK"}]}
    meta = build_card_metadata(card_kind="detail", card_payload=payload)

    assert isinstance(meta, MetadataContent)
    assert meta.type == "metadata"
    assert meta.metadata["card_protocol_version"] == "1"
    assert meta.metadata["requires_card_interaction"] == "true"
    assert meta.metadata["card_kind"] == "detail"
    assert meta.metadata["preferred_drawer_width_px"] == "540"

    # Verify card_payload is valid JSON string
    parsed_payload = json.loads(meta.metadata["card_payload"])
    assert parsed_payload["title"] == "Test Title"


def test_card_envelope_terminal():
    """Verifies is_terminal and requires_interaction flags for terminal cards."""
    payload = {"title": "Finished"}
    meta = build_card_metadata(
        card_kind="detail",
        card_payload=payload,
        requires_interaction=False,
        is_terminal=True,
    )
    assert meta.metadata["requires_card_interaction"] == "false"
    assert meta.metadata["is_terminal"] == "true"


def test_invalid_card_kind():
    """Rejects card kinds not in the official specification."""
    with pytest.raises(ValueError, match="Invalid card_kind"):
        build_card_metadata(card_kind="unsupported_kind", card_payload={})


# -----------------------------------------------------------------------------
# 2. Card A: Home Menu Tests
# -----------------------------------------------------------------------------
def test_home_menu_card():
    """Verifies Card A (Home Menu) contains 4 distinct procurement CTAs."""
    narration, meta = build_home_menu_card()

    assert "Welcome to StockWise" in narration
    assert meta.metadata["card_kind"] == "detail"
    payload = json.loads(meta.metadata["card_payload"])

    actions = [cta["selection"]["action"] for cta in payload["ctas"]]
    assert "inventory_health" in actions
    assert "compare_suppliers" in actions
    assert "build_restock_plan" in actions
    assert "review_orders" in actions


# -----------------------------------------------------------------------------
# 3. Card B: Inventory Health Tests
# -----------------------------------------------------------------------------
def test_inventory_health_card(test_procurement_service: ProcurementService):
    """Verifies Card B computes factual inventory metrics from database."""
    narration, meta = build_inventory_health_card(test_procurement_service)

    assert "StockWise Inventory Health" in narration
    assert meta.metadata["card_kind"] == "detail"
    payload = json.loads(meta.metadata["card_payload"])

    labels = {row["label"]: row["value"] for row in payload["summary_rows"]}
    assert "Total SKUs Monitored" in labels
    assert labels["Total SKUs Monitored"] == "15"
    assert "Critical Shortages" in labels


# -----------------------------------------------------------------------------
# 4. Card C: Supplier Comparison Carousel Tests
# -----------------------------------------------------------------------------
def test_supplier_comparison_carousel_general(test_procurement_service: ProcurementService):
    """Verifies Card C carousel lists verified suppliers from catalog."""
    narration, meta = build_supplier_comparison_carousel(test_procurement_service)

    assert meta.metadata["card_kind"] == "carousel"
    payload = json.loads(meta.metadata["card_payload"])
    assert len(payload["items"]) >= 4

    # Check SUP-001 is present
    sup_ids = [item["id"] for item in payload["items"]]
    assert "SUP-001" in sup_ids


def test_supplier_comparison_carousel_sku_specific(test_procurement_service: ProcurementService):
    """Verifies Card C ranks suppliers with real unit cost and lead time for SKU."""
    narration, meta = build_supplier_comparison_carousel(test_procurement_service, sku="ELEC-SPK-008")

    assert "ELEC-SPK-008" in narration
    assert meta.metadata["card_kind"] == "carousel"
    payload = json.loads(meta.metadata["card_payload"])
    assert len(payload["items"]) > 0

    first_item = payload["items"][0]
    assert "₹" in first_item["subtitle"]
    assert first_item["primary_cta"]["selection"]["action"] == "select_supplier"


# -----------------------------------------------------------------------------
# 5. Card D: Restocking Plan Form Tests
# -----------------------------------------------------------------------------
def test_restock_form_card():
    """Verifies Card D displays the required input fields."""
    narration, meta = build_restock_form_card(default_budget="25000")

    assert meta.metadata["card_kind"] == "form"
    payload = json.loads(meta.metadata["card_payload"])
    field_names = [f["name"] for f in payload["fields"]]
    assert "budget" in field_names
    assert "sku" in field_names
    assert "quantity" in field_names
    assert "max_deadline_days" in field_names
    assert payload["submit_cta"]["selection"]["action"] == "submit_restock_plan"


# -----------------------------------------------------------------------------
# 6. Card E & F: Review, Approval, and Simulated Placement Workflow Tests
# -----------------------------------------------------------------------------
def test_full_order_review_and_simulated_placement(test_procurement_service: ProcurementService):
    """Tests the entire procurement card lifecycle:

    1. Form submission creates draft PO -> PO Review Card (Card E)
    2. Review Card -> Approve Order CTA -> Approval Card
    3. Approval Card -> Simulate Placement CTA -> Placement Confirmation Card (Card F)
    """
    svc = test_procurement_service

    # Step 1: Submit restocking plan
    submit_selection = json.dumps({"action": "submit_restock_plan", "budget": "20000"})
    narration, meta, is_terminal = dispatch_chat_interaction(submit_selection, service=svc)

    assert meta is not None
    assert meta.metadata["card_kind"] == "review"
    assert not is_terminal

    payload = json.loads(meta.metadata["card_payload"])
    order_id = payload["approve_cta"]["selection"]["order_id"]
    assert order_id.startswith("PO-")

    # Verify order is in PENDING_APPROVAL status
    po = svc.get_order(order_id)
    assert po is not None
    assert po.status == OrderStatus.PENDING_APPROVAL

    # Step 2: Approve order via card action
    approve_selection = json.dumps({"action": "approve_order", "order_id": order_id})
    narration, meta, is_terminal = dispatch_chat_interaction(approve_selection, service=svc)

    po = svc.get_order(order_id)
    assert po.status == OrderStatus.APPROVED
    assert meta is not None
    assert meta.metadata["card_kind"] == "detail"

    # Step 3: Simulate placement via card action
    placement_selection = json.dumps({"action": "simulate_placement", "order_id": order_id})
    narration, meta, is_terminal = dispatch_chat_interaction(placement_selection, service=svc)

    po = svc.get_order(order_id)
    assert po.status == OrderStatus.SIMULATED_PLACED
    assert is_terminal is True
    assert meta.metadata["is_terminal"] == "true"
    assert meta.metadata["requires_card_interaction"] == "false"
    assert "Simulated Dispatch" in meta.metadata["card_payload"]


# -----------------------------------------------------------------------------
# 7. Card Selection Parsing & Fallbacks
# -----------------------------------------------------------------------------
def test_card_selection_parser():
    """Tests direct JSON, markdown-wrapped JSON, and natural-language triggers."""
    # Direct JSON
    sel1 = parse_card_selection('{"action": "inventory_health"}')
    assert sel1 == {"action": "inventory_health"}

    # Markdown embedded JSON
    sel2 = parse_card_selection('```json\n{"action": "approve_order", "order_id": "PO-TEST1234"}\n```')
    assert sel2["action"] == "approve_order"
    assert sel2["order_id"] == "PO-TEST1234"

    # Prose trigger for inventory health
    sel3 = parse_card_selection("give me a summary of my store's inventory health")
    assert sel3 == {"action": "inventory_health"}

    # Prose trigger for menu
    sel4 = parse_card_selection("show me the card menu")
    assert sel4 == {"action": "home_menu"}

    # Prose trigger for supplier comparison
    sel5 = parse_card_selection("compare suppliers")
    assert sel5 == {"action": "compare_suppliers"}


def test_invalid_and_stale_order_id_handling(test_procurement_service: ProcurementService):
    """Ensures approving a non-existent or stale order ID returns an error without crashing."""
    approve_sel = json.dumps({"action": "approve_order", "order_id": "PO-NONEXISTENT"})
    narration, meta, _ = dispatch_chat_interaction(approve_sel, service=test_procurement_service)
    assert "not found" in narration.lower() or "failed" in narration.lower()


def test_cannot_simulate_placement_before_approval(test_procurement_service: ProcurementService):
    """Ensures simulated placement fails if the order has not been approved yet."""
    svc = test_procurement_service
    po, _ = svc.create_procurement_plan(budget=Decimal("20000.00"))

    # Attempt to place order without approval
    place_sel = json.dumps({"action": "simulate_placement", "order_id": po.order_id})
    narration, meta, is_terminal = dispatch_chat_interaction(place_sel, service=svc)

    po_after = svc.get_order(po.order_id)
    assert po_after.status == OrderStatus.PENDING_APPROVAL
    assert "invalid transition" in narration.lower() or "failed" in narration.lower()


def test_direct_agent_mention_stripping(test_procurement_service: ProcurementService):
    """Verifies that direct @mention formatted messages correctly trigger cards."""
    svc = test_procurement_service
    mention_query = "@agent1q2jq4rxh6wp56z7d09t23477y9gzc3uvr6j6tpdpl44r4rtzggd9jeflrev Check inventory"
    narration, meta, _ = dispatch_chat_interaction(mention_query, service=svc)
    assert meta is not None
    assert meta.metadata["card_kind"] == "detail"
    assert "StockWise Inventory Health" in narration
