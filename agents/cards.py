"""ASI Interactive Cards Envelope & Builders for StockWise Agents.

Implements the official AgentChatProtocol Interactive Cards specification:
- MetadataContent envelope with card_protocol_version="1", requires_card_interaction="true"
- Card kinds: form, carousel, detail, review, custom
- Server-side data grounding: real inventory, verified supplier offers, and deterministic purchase orders
- Card selection parser for both direct JSON and natural-language / planner text
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from uagents_core.contrib.protocols.chat import MetadataContent

from core.procurement_service import ProcurementService
from core.schemas import PurchaseOrder


# -----------------------------------------------------------------------------
# 1. Envelope Builder
# -----------------------------------------------------------------------------
def build_card_metadata(
    card_kind: str,
    card_payload: Dict[str, Any],
    requires_interaction: bool = True,
    is_terminal: bool = False,
    drawer_width_px: str = "540",
) -> MetadataContent:
    """Builds the official MetadataContent for ASI Interactive Cards.

    Validates:
    - card_protocol_version is '1'
    - card_kind in {'form', 'carousel', 'detail', 'review', 'custom'}
    - card_payload serialized as JSON string (max 64KB)
    - stringified dictionary values required by the protocol
    """
    valid_kinds = {"form", "carousel", "detail", "review", "custom"}
    if card_kind not in valid_kinds:
        raise ValueError(f"Invalid card_kind '{card_kind}'. Must be one of {valid_kinds}")

    payload_str = json.dumps(card_payload, separators=(",", ":"))
    if len(payload_str.encode("utf-8")) > 64 * 1024:
        raise ValueError("Card payload exceeds 64KB size limit")

    metadata: Dict[str, str] = {
        "card_protocol_version": "1",
        "card_kind": card_kind,
        "card_payload": payload_str,
    }

    if requires_interaction:
        metadata["requires_card_interaction"] = "true"
    else:
        metadata["requires_card_interaction"] = "false"

    if is_terminal:
        metadata["is_terminal"] = "true"

    if drawer_width_px:
        metadata["preferred_drawer_width_px"] = str(drawer_width_px)

    return MetadataContent(type="metadata", metadata=metadata)


# -----------------------------------------------------------------------------
# 2. Card A: StockWise Home / Action Menu (Detail Card)
# -----------------------------------------------------------------------------
def build_home_menu_card() -> Tuple[str, MetadataContent]:
    """Card A — StockWise Home / Action Menu.

    Presents a clear introductory overview and 4 structured actions:
    1. Inventory Health
    2. Compare Suppliers
    3. Build Restocking Plan
    4. Review Purchase Orders
    """
    narration = (
        "Welcome to StockWise Agents! I am your autonomous inventory and procurement coordinator.\n\n"
        "Select an action below or ask me any question about your stock, suppliers, or purchase orders."
    )

    payload = {
        "title": "StockWise Procurement Suite",
        "summary_rows": [
            {"label": "Agent Status", "value": "Autonomous Active"},
            {"label": "Optimization Engine", "value": "Deterministic Multi-Supplier"},
            {"label": "Currency", "value": "INR (₹)"},
            {"label": "Safety Policy", "value": "Explicit Human Approval Required"},
        ],
        "ctas": [
            {
                "label": "📊 Inventory Health",
                "primary": True,
                "selection": {"action": "inventory_health"},
            },
            {
                "label": "🏢 Compare Suppliers",
                "primary": False,
                "selection": {"action": "compare_suppliers"},
            },
            {
                "label": "📦 Build Restocking Plan",
                "primary": False,
                "selection": {"action": "build_restock_plan"},
            },
            {
                "label": "📋 Review Purchase Orders",
                "primary": False,
                "selection": {"action": "review_orders"},
            },
        ],
    }

    metadata = build_card_metadata(card_kind="detail", card_payload=payload)
    return narration, metadata


# -----------------------------------------------------------------------------
# 3. Card B: Inventory Health (Detail Card)
# -----------------------------------------------------------------------------
def build_inventory_health_card(service: ProcurementService) -> Tuple[str, MetadataContent]:
    """Card B — Inventory Health.

    Shows real inventory metrics:
    - Total monitored SKUs
    - Total physical stock units
    - Shortage products
    - Urgent/critical shortages
    - Healthy products
    """
    try:
        products = service.get_inventory()
        suppliers = service.get_suppliers()
        from core.inventory import analyze_all_inventory
        requirements = analyze_all_inventory(products, suppliers)
    except Exception as e:
        error_narration = f"[INVENTORY SERVICE ERROR] Unable to retrieve inventory: {e}"
        err_payload = {
            "title": "Inventory Health Error",
            "summary_rows": [{"label": "Status", "value": "Unavailable"}, {"label": "Details", "value": str(e)}],
            "ctas": [{"label": "Retry", "primary": True, "selection": {"action": "inventory_health"}}],
        }
        return error_narration, build_card_metadata(card_kind="detail", card_payload=err_payload)

    total_skus = len(products)
    total_units = sum(p.current_stock for p in products)
    shortages = [r for r in requirements if r.gross_reorder_qty > 0]
    critical = [r for r in shortages if r.is_urgent]
    healthy = [r for r in requirements if r.gross_reorder_qty == 0]

    top_urgents = ", ".join([r.sku for r in critical[:3]]) if critical else "None"

    narration = (
        f"StockWise Inventory Health:\n"
        f"• Monitored SKUs: {total_skus}\n"
        f"• Total Physical Stock: {total_units} units\n"
        f"• Products Below Threshold: {len(shortages)} ({len(critical)} critical)\n"
        f"• Healthy SKUs: {len(healthy)}\n\n"
        "Explore options below to inspect individual shortages or generate a restocking plan."
    )

    payload = {
        "title": "Store Inventory Health Summary",
        "summary_rows": [
            {"label": "Total SKUs Monitored", "value": str(total_skus)},
            {"label": "Total Physical Inventory", "value": f"{total_units} units"},
            {"label": "Items Below Threshold", "value": str(len(shortages))},
            {"label": "Critical Shortages", "value": f"{len(critical)} ({top_urgents})"},
            {"label": "Adequately Stocked", "value": str(len(healthy))},
        ],
        "ctas": [
            {
                "label": "🚀 Build Restocking Plan",
                "primary": True,
                "selection": {"action": "build_restock_plan", "budget": "20000"},
            },
            {
                "label": "🔍 Compare Suppliers",
                "primary": False,
                "selection": {"action": "compare_suppliers"},
            },
            {
                "label": "🔄 Refresh Health",
                "primary": False,
                "selection": {"action": "inventory_health"},
            },
        ],
    }

    metadata = build_card_metadata(card_kind="detail", card_payload=payload)
    return narration, metadata


# -----------------------------------------------------------------------------
# 4. Card C: Supplier Comparison (Carousel Card)
# -----------------------------------------------------------------------------
def build_supplier_comparison_carousel(
    service: ProcurementService,
    sku: Optional[str] = None,
) -> Tuple[str, MetadataContent]:
    """Card C — Supplier Comparison Carousel.

    Presents real supplier catalog terms, prices, lead times, MOQs, and delivery charges.
    If SKU is provided, ranks suppliers for that specific SKU.
    Otherwise, displays the registered verified suppliers and their catalogs.
    """
    suppliers = service.get_suppliers()
    products = service.get_inventory()

    items: List[Dict[str, Any]] = []

    if sku:
        target_sku = sku.strip().upper()
        prod = next((p for p in products if p.sku.upper() == target_sku), None)
        prod_name = prod.name if prod else target_sku

        # Collect verified offers
        offers_found = []
        for s in suppliers:
            if target_sku in s.catalog and s.catalog[target_sku].available:
                offers_found.append((s, s.catalog[target_sku]))

        if not offers_found:
            narration = f"No verified suppliers found offering available stock for SKU '{target_sku}'."
            fallback_payload = {
                "title": f"Supplier Comparison — {target_sku}",
                "summary_rows": [
                    {"label": "Target SKU", "value": target_sku},
                    {"label": "Available Suppliers", "value": "0"},
                ],
                "ctas": [
                    {"label": "View All Suppliers", "primary": True, "selection": {"action": "compare_suppliers"}},
                    {"label": "Back to Home", "primary": False, "selection": {"action": "home_menu"}},
                ],
            }
            return narration, build_card_metadata(card_kind="detail", card_payload=fallback_payload)

        # Sort by unit cost
        offers_found.sort(key=lambda x: x[1].unit_cost)

        for rank, (sup, off) in enumerate(offers_found, 1):
            badge_text = "Lowest Unit Price" if rank == 1 else f"Rank #{rank}"
            items.append({
                "id": sup.id,
                "title": f"{sup.name} ({sup.id})",
                "subtitle": f"₹{off.unit_cost:,.2f} / unit • Lead time: {off.lead_time_days}d",
                "secondary_text": f"MOQ: {off.moq} | Pack Size: {off.pack_size} | Flat Delivery: ₹{sup.delivery_charge:,.2f}",
                "badges": [{"label": badge_text, "variant": "success" if rank == 1 else "info"}],
                "primary_cta": {
                    "label": f"Select {sup.id}",
                    "selection": {
                        "action": "select_supplier",
                        "sku": target_sku,
                        "supplier_id": sup.id,
                        "quantity": off.moq,
                    },
                },
            })

        narration = f"Comparing {len(offers_found)} verified suppliers for {prod_name} [{target_sku}]:"
        payload = {
            "title": f"Suppliers for {target_sku}",
            "subtitle": f"{prod_name} verified catalog terms",
            "items": items,
        }
    else:
        # General supplier directory
        for sup in suppliers:
            active_skus = len([o for o in sup.catalog.values() if o.available])
            loc_str = f" • Location: {sup.location}" if sup.location else ""
            items.append({
                "id": sup.id,
                "title": f"{sup.name} ({sup.id})",
                "subtitle": f"Flat Delivery: ₹{sup.delivery_charge:,.2f}{loc_str}",
                "secondary_text": f"Catalog: {active_skus} verified SKUs | Status: Active Contract",
                "badges": [{"label": "Verified Supplier", "variant": "info"}],
                "primary_cta": {
                    "label": f"Inspect {sup.id}",
                    "selection": {
                        "action": "view_supplier_catalog",
                        "supplier_id": sup.id,
                    },
                },
            })

        narration = f"StockWise manages {len(suppliers)} verified suppliers with live catalog contracts:"
        payload = {
            "title": "Verified Supplier Directory",
            "subtitle": "Active vendor contracts and terms",
            "items": items,
        }

    metadata = build_card_metadata(card_kind="carousel", card_payload=payload)
    return narration, metadata


# -----------------------------------------------------------------------------
# 5. Card D: Restocking Plan Form (Form Card)
# -----------------------------------------------------------------------------
def build_restock_form_card(
    default_budget: str = "20000",
    default_sku: str = "",
) -> Tuple[str, MetadataContent]:
    """Card D — Restocking Plan Form.

    Captures:
    - Target SKU or all shortages
    - Authorized budget (INR)
    - Maximum delivery deadline (days)
    - Preferred supplier (optional)
    """
    narration = (
        "Configure your restocking parameters below.\n"
        "StockWise will calculate an optimal multi-supplier procurement plan using actual stock levels, "
        "live catalog prices, and delivery charges."
    )

    payload = {
        "title": "Configure Restocking Optimization Plan",
        "fields": [
            {
                "name": "budget",
                "kind": "number",
                "label": "Authorized Budget (₹ INR)",
                "required": True,
                "default": default_budget,
            },
            {
                "name": "sku",
                "kind": "text",
                "label": "Target SKU (leave blank for all shortages)",
                "required": False,
                "default": default_sku,
            },
            {
                "name": "quantity",
                "kind": "number",
                "label": "Requested Quantity (optional for single SKU)",
                "required": False,
                "default": "1",
            },
            {
                "name": "max_deadline_days",
                "kind": "number",
                "label": "Max Lead Time / Deadline (Days, optional)",
                "required": False,
                "default": "7",
            },
        ],
        "submit_cta": {
            "label": "Generate Optimized Plan",
            "selection": {
                "action": "submit_restock_plan",
            },
        },
    }

    metadata = build_card_metadata(card_kind="form", card_payload=payload)
    return narration, metadata


# -----------------------------------------------------------------------------
# 6. Card E: Purchase-Order Review (Review Card)
# -----------------------------------------------------------------------------
def build_po_review_card(
    order: PurchaseOrder,
) -> Tuple[str, MetadataContent]:
    """Card E — Purchase-Order Review.

    Presents a formal review card for an order in PENDING_APPROVAL status:
    - Order ID
    - Items and quantities
    - Suppliers and lead times
    - Subtotal, delivery charges, total landed cost
    - Explicit approve and reject CTAs
    """
    supplier_names = sorted(list(set(item.supplier_name for item in order.items)))
    items_summary = ", ".join([f"{item.ordered_quantity}x {item.sku}" for item in order.items[:3]])
    if len(order.items) > 3:
        items_summary += f" +{len(order.items) - 3} more"

    narration = (
        f"Draft Purchase Order {order.order_id} is ready for review:\n"
        f"• Status: {order.status.value.upper()}\n"
        f"• Total Landed Cost: ₹{order.total_cost:,.2f} (Subtotal: ₹{order.subtotal:,.2f} + Delivery: ₹{order.total_delivery_charges:,.2f})\n"
        f"• Suppliers: {', '.join(supplier_names) if supplier_names else 'None'}\n"
        f"• Items: {len(order.items)} line items allocated\n\n"
        "Please review the details below. Explicit approval is required before simulated placement."
    )

    payload = {
        "title": f"Review Purchase Order — {order.order_id}",
        "summary_rows": [
            {"label": "Order ID", "value": order.order_id},
            {"label": "Current Status", "value": order.status.value.upper()},
            {"label": "Authorized Budget", "value": f"₹{order.budget:,.2f}"},
            {"label": "Subtotal", "value": f"₹{order.subtotal:,.2f}"},
            {"label": "Delivery Fees", "value": f"₹{order.total_delivery_charges:,.2f}"},
            {"label": "Total Landed Cost", "value": f"₹{order.total_cost:,.2f}"},
            {"label": "Remaining Budget", "value": f"₹{order.remaining_budget:,.2f}"},
            {"label": "Items", "value": items_summary or "None"},
            {"label": "Suppliers", "value": ", ".join(supplier_names) or "None"},
        ],
        "approve_cta": {
            "label": "Approve Purchase Order",
            "primary": True,
            "selection": {
                "action": "approve_order",
                "order_id": order.order_id,
            },
        },
        "reject_cta": {
            "label": "Reject Order",
            "selection": {
                "action": "reject_order",
                "order_id": order.order_id,
            },
        },
    }

    metadata = build_card_metadata(card_kind="review", card_payload=payload)
    return narration, metadata


# -----------------------------------------------------------------------------
# 7. Card F: Placement Confirmation (Detail Card / Terminal)
# -----------------------------------------------------------------------------
def build_placement_confirmation_card(
    order: PurchaseOrder,
    execution_result: str,
) -> Tuple[str, MetadataContent]:
    """Card F — Placement Confirmation.

    Shown after simulated placement has been executed on an approved order.
    Marks is_terminal=True since the procurement workflow is complete.
    """
    supplier_names = sorted(list(set(item.supplier_name for item in order.items)))

    narration = (
        f"Simulated Placement Result for Order {order.order_id}:\n"
        f"• Status: {order.status.value.upper()}\n"
        f"• Total Cost: ₹{order.total_cost:,.2f}\n"
        f"• Result: {execution_result}\n\n"
        "[Safeguard Notice: This execution is a synthetic simulation. No real money was charged or goods dispatched.]"
    )

    payload = {
        "title": f"Simulated Dispatch — {order.order_id}",
        "summary_rows": [
            {"label": "Order ID", "value": order.order_id},
            {"label": "Final Status", "value": order.status.value.upper()},
            {"label": "Execution", "value": "Simulation Confirmed"},
            {"label": "Total Cost", "value": f"₹{order.total_cost:,.2f}"},
            {"label": "Vendors Notified", "value": ", ".join(supplier_names) or "None"},
            {"label": "Notice", "value": "Demo simulation; no actual funds transferred"},
        ],
        "ctas": [
            {
                "label": "Return to StockWise Home",
                "primary": True,
                "selection": {"action": "home_menu"},
            },
            {
                "label": "Check Inventory Health",
                "primary": False,
                "selection": {"action": "inventory_health"},
            },
        ],
    }

    # Since it's a finished confirmation, mark is_terminal=True
    metadata = build_card_metadata(
        card_kind="detail",
        card_payload=payload,
        requires_interaction=False,
        is_terminal=True,
    )
    return narration, metadata


# -----------------------------------------------------------------------------
# 8. Card Selection Parser
# -----------------------------------------------------------------------------
def parse_card_selection(text: str) -> Optional[Dict[str, Any]]:
    """Robustly parses user input as either a card selection payload or natural language intent.

    Handles:
    - Direct JSON string: {"action": "inventory_health", ...}
    - Markdown enclosed JSON: ```json {"action": ...} ```
    - Substring JSON objects: "User selected: {"action": "approve_order", "order_id": "PO-12345678"}"
    - Prose fallback for common card actions
    """
    cleaned = text.strip()
    # Strip any direct @mention prefixes like "@agent1q2jq4rxh... "
    cleaned = re.sub(r"@agent1[a-z0-9]{50,70}\b", "", cleaned, flags=re.IGNORECASE).strip()

    # 1. Try direct JSON parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "action" in data:
            return data
    except Exception:
        pass

    # 2. Try markdown or embedded JSON parse
    json_match = re.search(r"\{[^{}]*\"action\"[^{}]*\}", cleaned)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            if isinstance(data, dict) and "action" in data:
                return data
        except Exception:
            pass

    # 3. Natural language / prose mapping for card actions
    lowered = cleaned.lower()

    if any(k in lowered for k in ["home menu", "main menu", "start menu", "show menu", "card menu"]):
        return {"action": "home_menu"}

    if any(k in lowered for k in ["inventory health", "check inventory", "store's inventory health", "inventory summary"]):
        return {"action": "inventory_health"}

    if any(k in lowered for k in ["compare supplier", "compare suppliers", "vendor comparison"]):
        return {"action": "compare_suppliers"}

    if any(k in lowered for k in ["build restocking plan", "restocking plan", "build restock plan"]):
        return {"action": "build_restock_plan"}

    if any(k in lowered for k in ["review purchase orders", "review orders", "review order", "show order"]):
        po_match = re.search(r"\b(PO-[A-Z0-9]{8})\b", cleaned, re.IGNORECASE)
        order_id = po_match.group(1).upper() if po_match else None
        return {"action": "review_orders", "order_id": order_id}

    if "approve order" in lowered or "approve po" in lowered:
        po_match = re.search(r"\b(PO-[A-Z0-9]{8})\b", cleaned, re.IGNORECASE)
        order_id = po_match.group(1).upper() if po_match else None
        return {"action": "approve_order", "order_id": order_id}

    if any(k in lowered for k in ["simulate place", "simulate placing", "place order", "dispatch order"]):
        po_match = re.search(r"\b(PO-[A-Z0-9]{8})\b", cleaned, re.IGNORECASE)
        order_id = po_match.group(1).upper() if po_match else None
        return {"action": "simulate_placement", "order_id": order_id}

    if "reject order" in lowered or "reject po" in lowered:
        po_match = re.search(r"\b(PO-[A-Z0-9]{8})\b", cleaned, re.IGNORECASE)
        order_id = po_match.group(1).upper() if po_match else None
        return {"action": "reject_order", "order_id": order_id}

    return None
