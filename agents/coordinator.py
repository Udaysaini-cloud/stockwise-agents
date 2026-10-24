import os
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, Tuple

import certifi
from dotenv import load_dotenv

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure SSL certificates are properly located on macOS / UNIX
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

load_dotenv()

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    MetadataContent,
    TextContent,
    chat_protocol_spec,
)

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
from core.procurement_service import ProcurementService

# Configuration from environment
COORDINATOR_NAME = os.getenv("COORDINATOR_NAME", "stockwise-coordinator")
COORDINATOR_SEED = os.getenv("COORDINATOR_SEED", "stockwise_coordinator_local_dev_seed_phrase_2026")
COORDINATOR_PORT = int(os.getenv("COORDINATOR_PORT", "8001"))
AGENT_MAILBOX_KEY = os.getenv("AGENT_MAILBOX_KEY", "").strip()
USE_MAILBOX = os.getenv("AGENT_MAILBOX_ENABLED", "false").lower() in ("true", "1", "yes") or bool(AGENT_MAILBOX_KEY)
ASI1_API_KEY = os.getenv("ASI1_API_KEY", "").strip()

# Procurement service instance
procurement_service = ProcurementService()

# Initialize the Agent
if USE_MAILBOX:
    coordinator = Agent(
        name=COORDINATOR_NAME,
        seed=COORDINATOR_SEED,
        port=COORDINATOR_PORT,
        mailbox=True,
        publish_agent_details=True,
    )
else:
    # Local HTTP endpoint configuration for local pair-testing
    coordinator = Agent(
        name=COORDINATOR_NAME,
        seed=COORDINATOR_SEED,
        port=COORDINATOR_PORT,
        endpoint=[f"http://127.0.0.1:{COORDINATOR_PORT}/submit"],
        publish_agent_details=True,
    )

# Protocol declaration using official chat_protocol_spec (AgentChatProtocol 0.3.0)
chat_protocol = Protocol(spec=chat_protocol_spec)


def strip_agent_mention(text: str) -> str:
    """Strips leading or embedded @agent1... address tags from incoming chat messages."""
    return re.sub(r"@agent1[a-z0-9]{50,70}\b", "", text, flags=re.IGNORECASE).strip()


def extract_budget(text: str) -> Optional[Decimal]:
    """Extracts a monetary budget amount in INR from text like '₹20,000', 'budget 20000', '25000 rs'."""
    # Match patterns like: ₹20,000, Rs. 20000, 20000 INR, budget of 20000
    cleaned = text.replace(",", "")
    patterns = [
        r"(?:₹|rs\.?|inr)\s*(-?[0-9]+(?:\.[0-9]+)?)",
        r"budget\s*(?:of|is|:)?\s*(?:₹|rs\.?|inr)?\s*(-?[0-9]+(?:\.[0-9]+)?)",
        r"(-?[0-9]+(?:\.[0-9]+)?)\s*(?:₹|rs\.?|inr|rupees)",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            try:
                val = Decimal(match.group(1))
                if val > Decimal("0.0"):
                    return val
            except InvalidOperation:
                pass
    return None


def extract_order_id(text: str) -> Optional[str]:
    """Extracts order identifier matching PO-XXXXXXXX format."""
    match = re.search(r"\b(PO-[A-Z0-9]{8})\b", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def extract_supplier_id(text: str) -> Optional[str]:
    """Extracts supplier identifier matching SUP-XXX format."""
    match = re.search(r"\b(SUP-[0-9]{3})\b", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def extract_item_request(text: str) -> Optional[Tuple[str, int, Optional[int]]]:
    """Extracts (sku, quantity, deadline_days) from requests like:
    - 'I want ELEC-SPK-008, 3 units, within 3 days'
    - 'Procure 5 of ELEC-USB-001 in 2d'
    - 'ELEC-AUD-003, 10 units'
    """
    cleaned = text.strip()

    # Match SKU (e.g. ELEC-SPK-008, ELEC-USB-001, ELEC-UNKNOWN-999)
    sku_match = re.search(r"\b([A-Z0-9]{2,10}-[A-Z0-9]{2,10}-[A-Z0-9]{2,10})\b", cleaned, re.IGNORECASE)
    if not sku_match:
        return None
    sku = sku_match.group(1).upper()

    # Match Quantity (e.g. 3 units, 3 pcs, 3 pieces, 3 qty, or '3' before/after SKU)
    qty = 1
    qty_match = re.search(r"(\d+)\s*(?:units?|pcs?|pieces?|items?|qty|packs?)", cleaned, re.IGNORECASE)
    if qty_match:
        qty = int(qty_match.group(1))
    else:
        # Check patterns like "want ELEC-SPK-008, 3" or "3 ELEC-SPK-008"
        qty_match2 = re.search(rf"(?:{re.escape(sku)}[,\s]+)(\d+)\b", cleaned, re.IGNORECASE)
        if qty_match2:
            qty = int(qty_match2.group(1))
        else:
            qty_match3 = re.search(rf"\b(\d+)\s+(?:of\s+)?{re.escape(sku)}\b", cleaned, re.IGNORECASE)
            if qty_match3:
                qty = int(qty_match3.group(1))

    # Match Deadline (e.g. within 3 days, in 3 days, within 48 hours, 3d)
    deadline_days: Optional[int] = None
    days_match = re.search(r"(?:within|in|by|deadline(?:\s*of)?)\s*(\d+)\s*(?:days?|d\b)", cleaned, re.IGNORECASE)
    if days_match:
        deadline_days = int(days_match.group(1))
    else:
        hours_match = re.search(r"(?:within|in|by|deadline(?:\s*of)?)\s*(\d+)\s*(?:hours?|hrs?|h\b)", cleaned, re.IGNORECASE)
        if hours_match:
            hrs = int(hours_match.group(1))
            deadline_days = max(1, (hrs + 23) // 24)

    return sku, max(1, qty), deadline_days


def extract_single_order_request(text: str) -> Optional[Tuple[str, int, str]]:
    """Extracts (sku, quantity, supplier_id) from confirmation requests like:
    - 'Create order for 4 units of ELEC-SPK-008 from SUP-002'
    - 'Order 4 ELEC-SPK-008 SUP-002'
    """
    cleaned = text.strip()
    sku_match = re.search(r"\b([A-Z0-9]{2,10}-[A-Z0-9]{2,10}-[A-Z0-9]{2,10})\b", cleaned, re.IGNORECASE)
    sup_match = re.search(r"\b(SUP-[0-9]{3})\b", cleaned, re.IGNORECASE)
    if not (sku_match and sup_match):
        return None

    sku = sku_match.group(1).upper()
    supplier_id = sup_match.group(1).upper()

    qty = 1
    qty_match = re.search(r"(\d+)\s*(?:units?|pcs?|pieces?|items?|qty|packs?)?", cleaned, re.IGNORECASE)
    # Avoid picking numbers from SKU or SUP
    clean_no_ids = re.sub(r"[A-Z]{3,4}-[A-Z0-9]{3,4}-[0-9]{3}", "", cleaned, flags=re.IGNORECASE)
    clean_no_ids = re.sub(r"SUP-[0-9]{3}", "", clean_no_ids, flags=re.IGNORECASE)
    num_match = re.search(r"\b(\d+)\b", clean_no_ids)
    if num_match:
        qty = int(num_match.group(1))

    return sku, max(1, qty), supplier_id


def process_procurement_command(user_text: str, service: Optional[ProcurementService] = None) -> Optional[str]:
    """Deterministic intent router mapping user messages to procurement service actions.

    Returns response string if a procurement action is identified; returns None for generic chat.
    """
    svc = service or procurement_service
    cleaned = user_text.strip()
    lowered = cleaned.lower()

    # 1. Greetings & System Capabilities
    if not lowered or lowered in ("hello", "hi", "hey", "help", "start"):
        return (
            "Hello! I am StockWise Coordinator, your autonomous inventory and procurement agent.\n\n"
            "Here is what I can do for you:\n"
            "• 'Check inventory' — View stock levels and urgent shortages\n"
            "• 'Compare suppliers' — Compare supplier prices, lead times, and MOQs\n"
            "• 'I want ELEC-SPK-008, 3 units, within 3 days' — Direct product evaluation with live supplier terms\n"
            "• 'Create restocking plan with budget ₹20,000' — Generate a budget-optimized purchase order\n"
            "• 'Show order PO-XXXX' — Review an existing purchase order\n"
            "• 'Approve order PO-XXXX' — Validate and approve a pending order\n"
            "• 'Reject order PO-XXXX' — Reject an order with an audit trail\n"
            "• 'Simulate placing order PO-XXXX' — Execute simulated vendor dispatch\n"
            "• 'Supplier SUP-001 failed' — Autonomous failure recovery and replanning"
        )

    # 2. Specific Single Item Order Confirmation (e.g. 'Create order for 4 units of ELEC-SPK-008 from SUP-002')
    single_order_req = extract_single_order_request(user_text)
    if single_order_req and any(k in lowered for k in ["create order", "place draft", "generate order", "make order", "buy", "order"]):
        sku, qty, sup_id = single_order_req
        try:
            _, plan_text = svc.create_single_item_order(sku=sku, quantity=qty, supplier_id=sup_id, user_query=user_text)
            return plan_text
        except Exception as e:
            return f"[ORDER CREATION FAILED] {e}"

    # 3. Dedicated Single SKU Inventory Lookup (e.g. "Check inventory for ELEC-SPK-008", "Stock of ELEC-USB-001")
    # Checked before item procurement evaluation if the intent is strictly to check stock/inventory
    sku_match = re.search(r"\b([A-Z0-9]{2,10}-[A-Z0-9]{2,10}-[A-Z0-9]{2,10})\b", cleaned, re.IGNORECASE)
    if sku_match and any(k in lowered for k in ["check inventory", "check stock", "stock level", "inventory for", "stock for", "how many", "quantity of", "inventory of"]):
        target_sku = sku_match.group(1).upper()
        return svc.check_inventory(filter_sku=target_sku)

    # 4. Specific Single Item Procurement/Inquiry Request (e.g. 'I want ELEC-SPK-008, 3 units, within 3 days')
    item_req = extract_item_request(user_text)
    if item_req:
        sku, qty, deadline_days = item_req
        return svc.evaluate_item_request(sku=sku, requested_quantity=qty, deadline_days=deadline_days)

    # 5. Supplier Comparison (checked before generic shortages check)
    if any(k in lowered for k in ["compare supplier", "supplier comparison", "vendor comparison", "compare vendor", "compare suppliers"]):
        return svc.compare_suppliers_for_shortages()

    # 6. Restock Prioritization (e.g. "What should I restock first?", "Restock priority")
    if any(k in lowered for k in ["restock first", "what should i restock", "which products to restock", "restock priority", "highest priority"]):
        return svc.check_inventory(mode="priority")

    # 7. Runout Projections (e.g. "Which products may run out within three days?", "run out in 3 days")
    if any(k in lowered for k in ["run out", "runout", "deplete", "exhaust stock"]):
        days_threshold = 3.0
        # Check if number of days is specified (digits or words)
        day_match = re.search(r"(\d+)\s*(?:days?|d\b)", cleaned, re.IGNORECASE)
        if day_match:
            days_threshold = float(day_match.group(1))
        elif "three" in lowered or "3" in lowered:
            days_threshold = 3.0
        elif "two" in lowered or "2" in lowered:
            days_threshold = 2.0
        elif "one" in lowered or "1" in lowered or "tomorrow" in lowered:
            days_threshold = 1.0
        elif "five" in lowered or "5" in lowered:
            days_threshold = 5.0
        elif "seven" in lowered or "7" in lowered or "week" in lowered:
            days_threshold = 7.0
        return svc.check_inventory(mode="runout", max_runout_days=days_threshold)

    # 8. All Products Stock Levels & General Inventory Status / Health Summary
    if any(k in lowered for k in [
        "check inventory",
        "check my inventory",
        "inventory health",
        "inventory summary",
        "summary of my store",
        "summary of store",
        "store's inventory",
        "inventory status",
        "stock level",
        "stock levels",
        "all products",
        "all inventory",
        "stock overview",
        "overview of stock",
        "which products need restock",
    ]):
        return svc.check_inventory(mode="summary")

    # 9. Running Low / Urgent Shortages List (e.g. "Which products are running low?", "Show me all urgent stock shortages")
    if any(k in lowered for k in ["running low", "low stock", "run low", "shortage", "shortages", "urgent stock", "critical stock", "low on stock"]):
        mode = "urgent_only" if any(k in lowered for k in ["urgent", "critical"]) else "running_low"
        return svc.check_inventory(mode=mode)

    # 4. Supplier Failure Notification & Replanning
    if "failed" in lowered or "offline" in lowered:
        sup_id = extract_supplier_id(user_text)
        if sup_id:
            budget = extract_budget(user_text) or Decimal("20000.00")
            _, response_text = svc.report_supplier_failure_and_replan(supplier_id=sup_id, budget=budget)
            return response_text
        else:
            return "Please specify the supplier ID that failed (e.g., 'Supplier SUP-001 failed')."

    # 5. Approve Order
    if "approve" in lowered:
        order_id = extract_order_id(user_text)
        if order_id:
            return svc.approve_order(order_id=order_id, actor="store_manager")
        else:
            return "Please specify the exact Order ID to approve (e.g., 'Approve order PO-ABCD1234')."

    # 6. Reject Order
    if "reject" in lowered:
        order_id = extract_order_id(user_text)
        if order_id:
            # Extract optional reason
            reason = "Rejected by user via chat"
            if "because" in lowered:
                reason = user_text.split("because", 1)[1].strip()
            return svc.reject_order(order_id=order_id, reason=reason, actor="store_manager")
        else:
            return "Please specify the exact Order ID to reject (e.g., 'Reject order PO-ABCD1234')."

    # 7. Simulate Placing Order
    if any(k in lowered for k in ["simulate place", "simulate placing", "place order", "dispatch order"]):
        order_id = extract_order_id(user_text)
        if order_id:
            return svc.simulate_placement(order_id=order_id, actor="procurement_agent")
        else:
            return "Please specify the exact Order ID to place (e.g., 'Simulate placing order PO-ABCD1234')."

    # 8. Show Order Details
    if any(k in lowered for k in ["show order", "view order", "get order", "details of order"]):
        order_id = extract_order_id(user_text)
        if order_id:
            return svc.show_order(order_id=order_id)
        else:
            return "Please specify the Order ID to view (e.g., 'Show order PO-ABCD1234')."

    # 9. Create Restocking Plan / Purchase Order
    if any(k in lowered for k in ["restock", "replenish", "plan", "procure", "purchase order", "create order"]):
        budget = extract_budget(user_text)
        if budget is None:
            # Check if user mentioned budget without valid number
            if "budget" in lowered:
                return "I noticed you mentioned a budget, but couldn't read the amount. Please specify a valid budget in INR (e.g. 'Create restocking plan with budget ₹20,000')."
            # Default to standard ₹20,000 budget
            budget = Decimal("20000.00")

        _, plan_text = svc.create_procurement_plan(budget=budget, user_query=user_text)
        return plan_text

    return None


def generate_response(user_text: str, service: Optional[ProcurementService] = None) -> str:
    """Generates coordinator response for incoming user text.

    Executes deterministic procurement engine commands first.
    If no procurement command matches and ASI1 is configured, delegates to ASI:One LLM.
    """
    # 1. Deterministic Procurement Engine Execution
    proc_reply = process_procurement_command(user_text, service=service)
    if proc_reply is not None:
        return proc_reply

    # 2. Optional ASI:One LLM reasoning for conversational queries
    if ASI1_API_KEY:
        try:
            from openai import OpenAI

            client = OpenAI(
                base_url="https://api.asi1.ai/v1",
                api_key=ASI1_API_KEY,
            )
            r = client.chat.completions.create(
                model="asi1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are StockWise Coordinator, an autonomous inventory and procurement agent for retail electronics. "
                            "Start your response identifying as 'StockWise Coordinator: '. "
                            "You analyze stock levels, compare suppliers in INR (₹), and guide users through purchase order approvals. "
                            "End your response reminding the user: 'Available commands: Check inventory, Compare suppliers, or Create restocking plan with budget ₹20,000'."
                        ),
                    },
                    {"role": "user", "content": user_text},
                ],
                max_tokens=512,
            )
            raw_reply = str(r.choices[0].message.content).strip()
            if "StockWise Coordinator" not in raw_reply:
                raw_reply = f"[StockWise Coordinator] {raw_reply}"
            if "Check inventory" not in raw_reply:
                raw_reply += "\n\nAvailable commands: 'Check inventory', 'Compare suppliers', 'Create restocking plan with budget ₹20,000'."
            return raw_reply
        except Exception as err:
            return (
                f"StockWise Coordinator received: '{user_text}'.\n\n"
                f"You can ask me to 'Check inventory', 'Compare suppliers', or 'Create a restocking plan with budget ₹20,000'."
            )

    return (
        f"StockWise Coordinator received: '{user_text}'.\n\n"
        f"Available commands:\n"
        f"• 'Check inventory'\n"
        f"• 'Compare suppliers'\n"
        f"• 'Create restocking plan with budget ₹20,000'\n"
        f"• 'Approve order PO-XXXX'\n"
        f"• 'Simulate placing order PO-XXXX'"
    )


def dispatch_chat_interaction(
    user_text: str,
    service: Optional[ProcurementService] = None,
) -> Tuple[str, Optional[MetadataContent], bool]:
    """Handles conversational text and structured card selections.

    Returns:
        (narration_text, optional_metadata_content, is_terminal)
    """
    svc = service or procurement_service
    cleaned = strip_agent_mention(user_text.strip())
    lowered = cleaned.lower()

    # 1. Parse Card Selections (direct JSON, embedded JSON, or action triggers)
    selection = parse_card_selection(cleaned)
    if selection:
        action = selection.get("action", "")

        # Action: Home / Main Menu
        if action == "home_menu":
            narration, meta = build_home_menu_card()
            return narration, meta, False

        # Action: Inventory Health Card
        if action == "inventory_health":
            narration, meta = build_inventory_health_card(svc)
            return narration, meta, False

        # Action: Compare Suppliers Carousel
        if action == "compare_suppliers":
            sku = selection.get("sku")
            narration, meta = build_supplier_comparison_carousel(svc, sku=sku)
            return narration, meta, False

        # Action: Restocking Plan Form
        if action == "build_restock_plan":
            default_budget = str(selection.get("budget", "20000"))
            default_sku = str(selection.get("sku", ""))
            narration, meta = build_restock_form_card(default_budget=default_budget, default_sku=default_sku)
            return narration, meta, False

        # Action: Submit Restocking Form -> Generates Plan and returns PO Review Card
        if action == "submit_restock_plan":
            raw_budget = selection.get("budget", 20000)
            try:
                budget_val = Decimal(str(raw_budget).replace(",", "").replace("₹", "").strip())
            except (InvalidOperation, TypeError):
                budget_val = Decimal("20000.00")

            req_sku = selection.get("sku")
            req_qty = selection.get("quantity")
            if req_sku and str(req_sku).strip():
                try:
                    q = max(1, int(req_qty or 1))
                    po, _ = svc.create_single_item_order(sku=str(req_sku).strip().upper(), quantity=q, supplier_id="SUP-001", user_query=cleaned)
                except Exception:
                    po, _ = svc.create_procurement_plan(budget=budget_val, user_query=cleaned)
            else:
                po, _ = svc.create_procurement_plan(budget=budget_val, user_query=cleaned)

            narration, meta = build_po_review_card(po)
            return narration, meta, False

        # Action: Review Purchase Orders
        if action == "review_orders":
            order_id = selection.get("order_id")
            orders = svc.list_orders()
            if order_id:
                po = svc.get_order(order_id)
            elif orders:
                po = orders[0]
            else:
                po = None

            if po:
                narration, meta = build_po_review_card(po)
                return narration, meta, False
            else:
                narration = "No purchase orders currently on file. Use 'Build Restocking Plan' to generate one."
                _, meta = build_home_menu_card()
                return narration, meta, False

        # Action: Approve Order
        if action == "approve_order":
            order_id = selection.get("order_id")
            if not order_id:
                return "Order approval requires a valid order_id.", None, False
            result_text = svc.approve_order(order_id=order_id, actor="store_manager")
            po = svc.get_order(order_id)
            if po and po.status.value == "approved":
                narration = (
                    f"Order {order_id} has been formally approved!\n\n"
                    f"{result_text}\n\n"
                    f"Ready to proceed with simulated placement?"
                )
                conf_payload = {
                    "title": f"Order {order_id} Approved",
                    "summary_rows": [
                        {"label": "Order ID", "value": order_id},
                        {"label": "Status", "value": "APPROVED"},
                        {"label": "Total Cost", "value": f"₹{po.total_cost:,.2f}"},
                    ],
                    "ctas": [
                        {
                            "label": "Execute Simulated Placement",
                            "primary": True,
                            "selection": {"action": "simulate_placement", "order_id": order_id},
                        },
                        {
                            "label": "Return to Home",
                            "primary": False,
                            "selection": {"action": "home_menu"},
                        },
                    ],
                }
                meta = build_card_metadata(card_kind="detail", card_payload=conf_payload)
                return narration, meta, False
            return result_text, None, False

        # Action: Simulate Placement
        if action == "simulate_placement":
            order_id = selection.get("order_id")
            if not order_id:
                return "Simulated placement requires a valid order_id.", None, False
            result_text = svc.simulate_placement(order_id=order_id, actor="procurement_agent")
            po = svc.get_order(order_id)
            if po:
                narration, meta = build_placement_confirmation_card(po, execution_result=result_text)
                return narration, meta, True
            return result_text, None, False

        # Action: Reject Order
        if action == "reject_order":
            order_id = selection.get("order_id")
            if not order_id:
                return "Order rejection requires a valid order_id.", None, False
            reason = selection.get("reason", "Rejected via interactive card")
            result_text = svc.reject_order(order_id=order_id, reason=reason, actor="store_manager")
            return result_text, None, False

    # 2. Check if user inquiry specifically requests Home or Menu Card
    if not cleaned or lowered in ("hello", "hi", "hey", "menu", "cards", "start", "help", "home"):
        narration, meta = build_home_menu_card()
        return narration, meta, False

    # 3. Check if user inquiry specifically matches Inventory Health query
    if any(k in lowered for k in [
        "inventory health",
        "check my inventory",
        "check inventory",
        "summary of my store",
        "store's inventory health",
        "inventory summary",
        "inventory status",
        "stock overview",
        "stock shortages",
        "shortages",
        "running low",
        "stock levels",
    ]):
        narration, meta = build_inventory_health_card(svc)
        return narration, meta, False

    # 4. Check if user inquiry specifically requests Supplier Comparison
    if any(k in lowered for k in ["compare suppliers", "compare supplier", "vendor comparison", "compare vendor"]):
        sku_match = re.search(r"\b([A-Z0-9]{2,10}-[A-Z0-9]{2,10}-[A-Z0-9]{2,10})\b", cleaned, re.IGNORECASE)
        sku = sku_match.group(1).upper() if sku_match else None
        narration, meta = build_supplier_comparison_carousel(svc, sku=sku)
        return narration, meta, False

    # 5. Check if user inquiry specifically requests Restocking Plan / Form
    if any(k in lowered for k in ["restock plan", "restocking plan", "build restocking", "replenish", "plan restock"]):
        narration, meta = build_restock_form_card()
        return narration, meta, False

    # 5. Standard deterministic procurement command or plain text response
    text_reply = generate_response(cleaned, service=svc)
    return text_reply, None, True


@chat_protocol.on_message(ChatMessage)
async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
    """Handle incoming ChatMessage, acknowledge immediately, and reply with TextContent and optional MetadataContent."""
    # 1. Acknowledge the message (mandatory per Agent Chat Protocol 0.3.0)
    await ctx.send(
        sender,
        ChatAcknowledgement(acknowledged_msg_id=msg.msg_id),
    )
    ctx.logger.info(f"Acknowledged message {msg.msg_id} from {sender}")

    # 2. Extract text content from payload blocks
    incoming_text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            incoming_text += item.text

    ctx.logger.info(f"Received query from {sender}: {incoming_text}")
    reply_text, card_metadata, is_terminal = dispatch_chat_interaction(incoming_text, service=procurement_service)

    # 3. Construct response contents
    response_blocks = [TextContent(type="text", text=reply_text)]
    if card_metadata is not None:
        response_blocks.append(card_metadata)

    # If terminal or plain text, close session block
    if is_terminal and card_metadata is None:
        response_blocks.append(EndSessionContent(type="end-session"))
    elif is_terminal and card_metadata is not None:
        # Terminal card with no further interaction needed
        pass

    # 4. Send response back to sender
    await ctx.send(
        sender,
        ChatMessage(content=response_blocks),
    )
    ctx.logger.info(f"Sent reply to {sender}: {reply_text[:60]}... (Card: {card_metadata is not None})")


@chat_protocol.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    """Handle acknowledgements from counterpart agents."""
    ctx.logger.info(
        f"Received acknowledgement from {sender} for message ID: {msg.acknowledged_msg_id}"
    )


# Include protocol in agent and publish manifest for Agentverse / ASI:One discovery
coordinator.include(chat_protocol, publish_manifest=True)


if __name__ == "__main__":
    print("=" * 60)
    print("StockWise Coordinator Agent")
    print(f"Address:  {coordinator.address}")
    print(f"Port:     {COORDINATOR_PORT}")
    print(f"Mailbox:  {'Enabled' if USE_MAILBOX else 'Disabled (Local HTTP endpoint)'}")
    print("=" * 60)
    coordinator.run()
