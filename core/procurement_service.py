"""StockWise Procurement Service Layer.

Orchestrates inventory checks, supplier comparisons, plan generation,
persistence, approval workflows, and simulated vendor placement.
Provides a clean, unified API for coordinator and CLI interfaces.
"""

import re
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.inventory import analyze_all_inventory, load_inventory, load_suppliers
from core.optimizer import optimize_purchase_order
from core.persistence import (
    InvalidStateTransitionError,
    OrderApprovalService,
    OrderValidationError,
    ProcurementDatabase,
    utc_now_iso,
)
from core.purchase_orders import format_purchase_order_summary
from core.schemas import (
    DeferredItem,
    OrderLineItem,
    OrderStatus,
    ProcurementRequest,
    Product,
    PurchaseOrder,
    StockRequirement,
    Supplier,
)
from core.supplier_scoring import rank_suppliers_for_requirement

DEFAULT_INVENTORY_PATH = Path("data/inventory.json")
DEFAULT_SUPPLIERS_PATH = Path("data/suppliers.json")
DEFAULT_DB_PATH = Path("data/stockwise.db")


class ProcurementService:
    """Service layer coordinating business logic, persistence, and state transitions."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        inventory_path: str | Path = DEFAULT_INVENTORY_PATH,
        suppliers_path: str | Path = DEFAULT_SUPPLIERS_PATH,
    ):
        self.inventory_path = Path(inventory_path)
        self.suppliers_path = Path(suppliers_path)
        self.db = ProcurementDatabase(db_path)
        self.approval_service = OrderApprovalService(self.db)
        self.failed_supplier_ids: List[str] = []

    def get_inventory(self) -> List[Product]:
        """Loads and returns current inventory products."""
        return load_inventory(self.inventory_path)

    def get_suppliers(self) -> List[Supplier]:
        """Loads and returns supplier catalog list."""
        return load_suppliers(self.suppliers_path)

    # ------------------------------------------------------------------
    # 1. Inventory Analysis & Health Reporting
    # ------------------------------------------------------------------
    def check_inventory(
        self,
        mode: str = "summary",
        filter_sku: Optional[str] = None,
        max_runout_days: Optional[float] = None,
    ) -> str:
        """Analyzes stock levels and returns a structured, factual inventory report.

        Modes:
        - 'summary': Complete overview including totals, healthy, moderate, and critical shortages.
        - 'running_low': Focuses strictly on products below reorder/safety stock thresholds.
        - 'urgent_only': Focuses only on urgent/critical shortages (stock <= safety or <= lead time).
        - 'runout': Filters products that may run out within max_runout_days.
        - 'priority': Prioritized list of what to restock first based on urgency score.
        - 'single': Dedicated status for a single SKU.
        """
        try:
            products = self.get_inventory()
            suppliers = self.get_suppliers()
            requirements = analyze_all_inventory(products, suppliers)
        except Exception as e:
            return f"[INVENTORY SERVICE ERROR] Unable to retrieve inventory data from database: {e}"

        # Single SKU lookup if requested
        if filter_sku:
            target_sku = filter_sku.strip().upper()
            req = next((r for r in requirements if r.sku.upper() == target_sku), None)
            if not req:
                return (
                    f"[SKU NOT FOUND] SKU '{target_sku}' does not exist in the inventory database.\n"
                    f"Monitored SKUs: {', '.join(sorted([p.sku for p in products]))}"
                )
            prod = next((p for p in products if p.sku.upper() == target_sku), None)
            base_unit = prod.unit if prod else "unit"
            unit_label = f"{base_unit}s" if (base_unit != "piece" or not base_unit.endswith("s")) else "pieces"
            if base_unit == "piece":
                unit_label = "pieces"
            urgency_str = "CRITICAL (Urgent Reorder Required)" if req.is_urgent else ("REORDER NEEDED" if req.gross_reorder_qty > 0 else "HEALTHY")
            return (
                f"STOCKWISE INVENTORY STATUS: [{req.sku}] {req.name}\n"
                f"============================================================\n"
                f"Stock Health:       {urgency_str}\n"
                f"Current Stock:      {req.current_stock} {unit_label}\n"
                f"Safety Stock:       {req.safety_stock} {unit_label}\n"
                f"Target Stock Cover: {req.target_stock_cover_days} days (Target: {req.target_stock} {unit_label})\n"
                f"Avg Daily Sales:    {req.average_daily_sales} {unit_label}/day\n"
                f"Outstanding Orders: {req.outstanding_orders} {unit_label}\n"
                f"Est. Stock Left:    {req.days_of_stock_left} days\n"
                f"Reorder Shortfall:  {req.gross_reorder_qty} {unit_label}\n"
                f"Lead Time (Days):   {req.lead_time_days_used} days\n"
                f"Urgency Score:      {req.urgency_score}/100.0\n"
                f"============================================================\n"
                f"Next Action: To evaluate supplier offers for this item, say 'I want {req.sku}, {max(req.gross_reorder_qty, 1)} units'."
            )

        shortages = [r for r in requirements if r.gross_reorder_qty > 0]
        critical = [r for r in shortages if r.is_urgent]
        healthy = [r for r in requirements if r.gross_reorder_qty == 0]

        # Mode: runout filter
        if mode == "runout" or max_runout_days is not None:
            threshold_days = max_runout_days if max_runout_days is not None else 3.0
            runout_items = [r for r in requirements if r.days_of_stock_left <= threshold_days]
            lines = [
                f"STOCKWISE INVENTORY RUNOUT ALERT (Within {threshold_days} Days)",
                "============================================================",
                f"Total SKUs Evaluated: {len(products)}",
                f"Items Depleting in ≤ {threshold_days} Days: {len(runout_items)}",
                "------------------------------------------------------------",
            ]
            if not runout_items:
                lines.append(f"  Good news! No monitored products are projected to run out within {threshold_days} days.")
            else:
                for idx, r in enumerate(runout_items, 1):
                    lines.append(
                        f"  {idx}. [{r.sku}] {r.name}\n"
                        f"     Current Stock: {r.current_stock} units | Sales Rate: {r.average_daily_sales}/day\n"
                        f"     Estimated Runout: {r.days_of_stock_left} days left (Safety Stock: {r.safety_stock})\n"
                        f"     Reorder Needed: {r.gross_reorder_qty} units"
                    )
            lines.extend([
                "============================================================",
                "Next Action: Say 'Create restocking plan with budget ₹20,000' to replenish depleting stock."
            ])
            return "\n".join(lines)

        # Mode: what to restock first / priority
        if mode == "priority":
            lines = [
                "STOCKWISE RESTOCK PRIORITIZATION (Highest Urgency First)",
                "============================================================",
                f"Total Reorder Shortages: {len(shortages)} of {len(products)} SKUs",
                "------------------------------------------------------------",
            ]
            if not shortages:
                lines.append("  No items currently require restocking.")
            else:
                for idx, r in enumerate(shortages[:6], 1):
                    tag = "🚨 [CRITICAL]" if r.is_urgent else "⚠️ [REORDER]"
                    lines.append(
                        f"  {idx}. {tag} [{r.sku}] {r.name}\n"
                        f"     Priority Score: {r.urgency_score}/100 | Days Left: {r.days_of_stock_left}d\n"
                        f"     Current: {r.current_stock} units (Safety: {r.safety_stock}, Target: {r.target_stock})\n"
                        f"     Reorder Shortfall: {r.gross_reorder_qty} units"
                    )
            lines.extend([
                "============================================================",
                "Next Action: Say 'Create restocking plan with budget ₹20,000' to optimize allocation."
            ])
            return "\n".join(lines)

        # Mode: running_low / urgent_only
        if mode in ("running_low", "urgent_only"):
            items_to_show = critical if mode == "urgent_only" else shortages
            title = "URGENT STOCK SHORTAGES" if mode == "urgent_only" else "PRODUCTS RUNNING LOW"
            lines = [
                f"STOCKWISE {title}",
                "============================================================",
                f"Total Monitored SKUs: {len(products)}",
                f"Products Below Threshold: {len(items_to_show)}",
                "------------------------------------------------------------",
            ]
            if not items_to_show:
                lines.append("  No products are currently running below their designated stock thresholds.")
            else:
                for idx, r in enumerate(items_to_show, 1):
                    urgency_tag = "[CRITICAL]" if r.is_urgent else "[NORMAL]"
                    lines.append(
                        f"  {idx}. {urgency_tag} [{r.sku}] {r.name}\n"
                        f"     Current Stock: {r.current_stock} (Safety: {r.safety_stock}, Target: {r.target_stock})\n"
                        f"     Est. Stock Left: {r.days_of_stock_left} days | Reorder Needed: {r.gross_reorder_qty} units"
                    )
            lines.extend([
                "============================================================",
                "Next Action: Say 'Compare suppliers' to inspect vendors or 'Create restocking plan with budget ₹20,000'."
            ])
            return "\n".join(lines)

        # Default Mode: Comprehensive Store Health Summary
        lines = [
            "STOCKWISE INVENTORY STATUS REPORT & STORE HEALTH SUMMARY",
            "============================================================",
            f"Total SKUs Monitored: {len(products)}",
            f"Total Physical Inventory: {sum(p.current_stock for p in products)} units across {len(products)} products",
            f"Items Needing Restock: {len(shortages)} (Total shortages below target cover)",
            f"Critical Shortages: {len(critical)} products below safety threshold",
            f"Items Adequately Stocked: {len(healthy)} products",
            "------------------------------------------------------------",
            "TOP REORDER SHORTAGES (Ranked by Urgency):",
        ]

        if not shortages:
            lines.append("  All products are currently stocked above reorder thresholds.")
        else:
            for idx, r in enumerate(shortages[:8], 1):
                urgency_tag = "[CRITICAL]" if r.is_urgent else "[REORDER]"
                lines.append(
                    f"  {idx}. {urgency_tag} [{r.sku}] {r.name}\n"
                    f"     Current: {r.current_stock} (Safety: {r.safety_stock}, Target: {r.target_stock}) | Stock Left: {r.days_of_stock_left}d\n"
                    f"     Reorder Shortfall: {r.gross_reorder_qty} units"
                )

        if len(shortages) > 8:
            lines.append(f"  ... and {len(shortages) - 8} more shortage items.")

        lines.extend(
            [
                "============================================================",
                "Next Action: Say 'Which products are running low?' or 'Create restocking plan with budget ₹20,000'.",
            ]
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 2. Supplier Comparison
    # ------------------------------------------------------------------
    def compare_suppliers_for_shortages(self) -> str:
        """Compares ranked supplier offers across all urgent shortage items."""
        products = self.get_inventory()
        suppliers = self.get_suppliers()
        requirements = analyze_all_inventory(products, suppliers)
        shortages = [r for r in requirements if r.gross_reorder_qty > 0]

        if not shortages:
            return "No products currently need restocking. All stock levels are sufficient."

        lines = [
            "STOCKWISE SUPPLIER COMPARISON REPORT",
            "============================================================",
        ]

        for r in shortages[:4]:  # Top 4 most urgent shortages
            ranked = rank_suppliers_for_requirement(
                r, suppliers, failed_supplier_ids=self.failed_supplier_ids
            )
            lines.append(f"Product: [{r.sku}] {r.name} (Gross Reorder Needed: {r.gross_reorder_qty})")
            for idx, offer in enumerate(ranked, 1):
                if offer.available and offer.disqualification_reason is None:
                    lines.append(
                        f"  {idx}. [Rank {idx}] {offer.supplier_name} ({offer.supplier_id})\n"
                        f"     Unit Cost: ₹{offer.unit_cost:,.2f} | Lead Time: {offer.lead_time_days} days\n"
                        f"     Feasible Qty: {offer.feasible_quantity} (MOQ: {offer.moq}, Pack: {offer.pack_size}) | Total: ₹{offer.item_total_cost:,.2f}"
                    )
                else:
                    lines.append(
                        f"  {idx}. [Unavailable] {offer.supplier_name} ({offer.supplier_id}) - {offer.disqualification_reason}"
                    )
            lines.append("------------------------------------------------------------")

        lines.append("Next Action: Request an optimized order with your budget (e.g. 'Plan restock with budget ₹20,000').")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 2. Single Item Request Evaluation & Procurement
    # ------------------------------------------------------------------
    def evaluate_item_request(
        self,
        sku: str,
        requested_quantity: int,
        deadline_days: Optional[int] = None,
    ) -> str:
        """Evaluates a single product procurement request against live inventory and supplier catalogs.

        Validates SKU existence, current inventory, supplier offers, lead time constraints,
        pack sizes, minimum order quantities (MOQ), and landed costs.
        """
        sku_clean = sku.strip().upper()
        products = self.get_inventory()
        product = next((p for p in products if p.sku.upper() == sku_clean), None)

        if not product:
            return (
                f"[SKU UNKNOWN] SKU '{sku_clean}' was not found in the inventory database or supplier catalog.\n"
                f"Please verify the SKU identifier (e.g., 'ELEC-SPK-008', 'ELEC-USB-001') and try again."
            )

        suppliers = self.get_suppliers()
        active_offers: List[Tuple[Supplier, Any, int, Decimal, Decimal]] = []
        unavailable_offers: List[Tuple[Supplier, str]] = []

        for sup in suppliers:
            if sup.id in self.failed_supplier_ids:
                unavailable_offers.append((sup, f"Supplier {sup.id} is flagged as failed/unresponsive"))
                continue
            if sku_clean in sup.catalog:
                offer = sup.catalog[sku_clean]
                if not offer.available:
                    unavailable_offers.append((sup, "Product currently marked unavailable"))
                    continue

                # Feasible quantity adhering to MOQ and pack size
                base_qty = max(requested_quantity, offer.moq)
                rem = base_qty % offer.pack_size
                feasible_qty = base_qty if rem == 0 else base_qty + (offer.pack_size - rem)
                item_cost = Decimal(str(feasible_qty)) * offer.unit_cost
                total_landed = item_cost + sup.delivery_charge

                active_offers.append((sup, offer, feasible_qty, item_cost, total_landed))

        if not active_offers:
            lines = [
                f"STOCKWISE PROCUREMENT EVALUATION: {sku_clean}",
                "============================================================",
                f"Product:            {product.name}",
                f"Current Stock:      {product.current_stock} {product.unit}s (Safety stock: {product.safety_stock})",
                "------------------------------------------------------------",
                "NO ACTIVE SUPPLIER OFFERS FOUND",
                f"No suppliers currently offer available stock for SKU '{sku_clean}'.",
            ]
            if unavailable_offers:
                lines.append("Unavailable vendors:")
                for sup, reason in unavailable_offers:
                    lines.append(f"  • {sup.name} ({sup.id}): {reason}")
            lines.append("============================================================")
            return "\n".join(lines)

        # Sort offers by total landed cost
        active_offers.sort(key=lambda x: x[4])

        # Filter by deadline if specified
        deadline_met_offers = [o for o in active_offers if deadline_days is None or o[1].lead_time_days <= deadline_days]

        lines = [
            f"STOCKWISE PROCUREMENT EVALUATION: {sku_clean}",
            "============================================================",
            f"Product:            {product.name}",
            f"Current Stock:      {product.current_stock} {product.unit}s (Safety Stock: {product.safety_stock}, Daily Sales: {product.average_daily_sales})",
            f"Requested Quantity: {requested_quantity} units",
        ]
        if deadline_days is not None:
            lines.append(f"Requested Deadline: Within {deadline_days} days")
        lines.append("------------------------------------------------------------")

        if deadline_days is not None and not deadline_met_offers:
            # Deadline cannot be met! Report factual constraint
            fastest_offer = min(active_offers, key=lambda x: x[1].lead_time_days)
            f_sup, f_offer, f_qty, f_item_cost, f_landed = fastest_offer
            lines.extend([
                f"[DEADLINE NOTICE] No supplier can deliver within {deadline_days} days.",
                f"Fastest available delivery is {f_offer.lead_time_days} days from {f_sup.name} ({f_sup.id}).",
                "------------------------------------------------------------",
                "AVAILABLE SUPPLIER OFFERS (From Catalog):",
            ])
            for s, o, f_q, i_cost, t_cost in active_offers:
                lines.append(
                    f"• {s.name} ({s.id}):\n"
                    f"  - Lead Time: {o.lead_time_days} days (exceeds {deadline_days}-day request)\n"
                    f"  - Unit Price: ₹{o.unit_cost:,.2f} | MOQ: {o.moq} | Pack Size: {o.pack_size}\n"
                    f"  - Feasible Order Qty: {f_q} units\n"
                    f"  - Subtotal: ₹{i_cost:,.2f} + Delivery: ₹{s.delivery_charge:,.2f} = Total Landed: ₹{t_cost:,.2f}"
                )
            lines.extend([
                "============================================================",
                f"Recommendation: If a {f_offer.lead_time_days}-day lead time is acceptable, I can prepare a draft purchase order",
                f"for {f_qty} units with {f_sup.name} at ₹{f_landed:,.2f} total landed cost.",
                f"Next Action: Say 'Create order for {f_qty} units of {sku_clean} from {f_sup.id}' to generate a draft order for approval.",
                "[Safeguard: No purchase order has been approved or placed.]"
            ])
            return "\n".join(lines)

        # Offers meeting deadline (or no deadline specified)
        best_sup, best_offer, best_qty, best_item_cost, best_landed = (
            deadline_met_offers[0] if deadline_met_offers else active_offers[0]
        )

        lines.extend([
            "FEASIBLE SUPPLIER OFFERS IDENTIFIED:",
        ])
        for idx, (s, o, f_q, i_cost, t_cost) in enumerate(deadline_met_offers or active_offers, 1):
            lines.append(
                f"{idx}. {s.name} ({s.id}) {'[BEST MATCH]' if idx == 1 else ''}\n"
                f"   - Lead Time: {o.lead_time_days} days (meets deadline)\n"
                f"   - Unit Price: ₹{o.unit_cost:,.2f} | MOQ: {o.moq} | Pack Size: {o.pack_size}\n"
                f"   - Feasible Order Qty: {f_q} units (adjusted for MOQ/pack size)\n"
                f"   - Cost Breakdown: ₹{o.unit_cost:,.2f} × {f_q} = ₹{i_cost:,.2f} + Delivery ₹{s.delivery_charge:,.2f} = Total ₹{t_cost:,.2f}"
            )

        lines.extend([
            "------------------------------------------------------------",
            f"RECOMMENDED DRAFT ORDER:",
            f"• Supplier:    {best_sup.name} ({best_sup.id})",
            f"• Quantity:    {best_qty} units (MOQ: {best_offer.moq}, Pack: {best_offer.pack_size})",
            f"• Lead Time:   {best_offer.lead_time_days} days",
            f"• Total Cost:  ₹{best_landed:,.2f} (including ₹{best_sup.delivery_charge:,.2f} delivery)",
            "============================================================",
            f"Would you like me to create this draft purchase order?",
            f"Next Action: Say 'Create order for {best_qty} units of {sku_clean} from {best_sup.id}' to prepare the order for approval.",
            "[Safeguard: No order is approved or placed automatically.]"
        ])
        return "\n".join(lines)

    def create_single_item_order(
        self,
        sku: str,
        quantity: int,
        supplier_id: str,
        user_query: str = "Direct item procurement request",
    ) -> Tuple[PurchaseOrder, str]:
        """Creates and persists a single-item draft purchase order in PENDING_APPROVAL status.

        Validates real supplier catalog terms, delivery fee, MOQ, and pack size before persisting.
        """
        sku_clean = sku.strip().upper()
        sup_id_clean = supplier_id.strip().upper()

        products = self.get_inventory()
        product = next((p for p in products if p.sku.upper() == sku_clean), None)
        if not product:
            raise ValueError(f"SKU '{sku_clean}' not found in inventory catalog.")

        suppliers = self.get_suppliers()
        supplier = next((s for s in suppliers if s.id.upper() == sup_id_clean), None)
        if not supplier:
            raise ValueError(f"Supplier '{sup_id_clean}' not found in registered suppliers.")

        if sku_clean not in supplier.catalog:
            raise ValueError(f"Supplier '{supplier.name}' does not offer SKU '{sku_clean}'.")

        offer = supplier.catalog[sku_clean]
        if not offer.available:
            raise ValueError(f"SKU '{sku_clean}' is currently marked unavailable from {supplier.name}.")

        base_qty = max(quantity, offer.moq)
        rem = base_qty % offer.pack_size
        feasible_qty = base_qty if rem == 0 else base_qty + (offer.pack_size - rem)

        subtotal = Decimal(str(feasible_qty)) * offer.unit_cost
        delivery_charges = {supplier.id: supplier.delivery_charge}
        total_delivery = supplier.delivery_charge
        total_cost = subtotal + total_delivery

        request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        req_record = ProcurementRequest(
            request_id=request_id,
            user_query=user_query,
            budget=total_cost,
            created_at=utc_now_iso(),
            status="draft_created",
        )
        self.db.save_procurement_request(req_record)

        order_id = f"PO-{uuid.uuid4().hex[:8].upper()}"
        item = OrderLineItem(
            sku=sku_clean,
            product_name=product.name,
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            ordered_quantity=feasible_qty,
            unit_cost=offer.unit_cost,
            line_total=subtotal,
            lead_time_days=offer.lead_time_days,
            pack_size=offer.pack_size,
            moq=offer.moq,
        )

        po = PurchaseOrder(
            order_id=order_id,
            request_id=request_id,
            status=OrderStatus.DRAFT,
            budget=total_cost,
            subtotal=subtotal,
            total_delivery_charges=total_delivery,
            total_cost=total_cost,
            remaining_budget=Decimal("0.00"),
            items=[item],
            supplier_delivery_charges=delivery_charges,
            deferred_items=[],
        )

        # Persist draft order
        self.db.save_purchase_order(po, actor="system")
        # Submit for approval
        po = self.approval_service.submit_for_approval(po.order_id, actor="stockwise_system")

        formatted = self._format_plan_chat_response(po)
        return po, formatted

    # ------------------------------------------------------------------
    # 3. Budget-Constrained Procurement Planning & Persistence
    # ------------------------------------------------------------------
    def create_procurement_plan(
        self,
        budget: Decimal,
        user_query: str = "Restock procurement request",
    ) -> Tuple[PurchaseOrder, str]:
        """Calculates budget-constrained purchase order, persists as DRAFT, and formats summary."""
        products = self.get_inventory()
        suppliers = self.get_suppliers()

        request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        req_record = ProcurementRequest(
            request_id=request_id,
            user_query=user_query,
            budget=budget,
            created_at=utc_now_iso(),
            status="draft_created",
        )
        self.db.save_procurement_request(req_record)

        po = optimize_purchase_order(
            products=products,
            suppliers=suppliers,
            budget=budget,
            failed_supplier_ids=self.failed_supplier_ids,
        )
        po.request_id = request_id
        po.status = OrderStatus.DRAFT

        # Persist draft order
        self.db.save_purchase_order(po, actor="system")

        # Automatically transition to PENDING_APPROVAL so manager can approve it directly
        po = self.approval_service.submit_for_approval(po.order_id, actor="stockwise_system")

        formatted = self._format_plan_chat_response(po)
        return po, formatted

    def _format_plan_chat_response(self, po: PurchaseOrder) -> str:
        """Formats plan response per Milestone 4 Step 5 guidelines."""
        supplier_ids = sorted(list({item.supplier_id for item in po.items}))
        lines = [
            "STOCKWISE PROCUREMENT PLAN",
            "============================================================",
            f"Request ID:         {po.request_id}",
            f"Order ID:           {po.order_id}",
            f"Status:             {po.status.value.upper()}",
            f"Authorized Budget:  ₹{po.budget:,.2f}",
            f"Selected Suppliers: {', '.join(supplier_ids) if supplier_ids else 'None'}",
            f"Subtotal:           ₹{po.subtotal:,.2f}",
            f"Delivery Charges:   ₹{po.total_delivery_charges:,.2f}",
            f"Total Landed Cost:  ₹{po.total_cost:,.2f}",
            f"Remaining Budget:   ₹{po.remaining_budget:,.2f}",
            "------------------------------------------------------------",
            f"ALLOCATED PRODUCTS ({len(po.items)} items):",
        ]

        if not po.items:
            lines.append("  (No products allocated within authorized budget)")
        else:
            for idx, item in enumerate(po.items, 1):
                lines.append(
                    f"  {idx}. [{item.sku}] {item.product_name}\n"
                    f"     Supplier: {item.supplier_name} ({item.supplier_id}) | Lead: {item.lead_time_days}d\n"
                    f"     Qty: {item.ordered_quantity} @ ₹{item.unit_cost:,.2f}/unit = ₹{item.line_total:,.2f}"
                )

        if po.deferred_items:
            lines.append("------------------------------------------------------------")
            lines.append(f"DEFERRED PRODUCTS ({len(po.deferred_items)} items):")
            for idx, d in enumerate(po.deferred_items, 1):
                lines.append(f"  {idx}. [{d.sku}] {d.product_name} (Need: {d.needed_quantity})\n     Reason: {d.reason}")

        lines.extend(
            [
                "============================================================",
                "[NOTE: Synthetic Demo Data - No real order or money transferred]",
                f"Next Action: To approve this purchase, say: 'Approve order {po.order_id}'",
                f"             To reject, say: 'Reject order {po.order_id}'",
            ]
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 4. Order Inquiries & Lifecycle Management
    # ------------------------------------------------------------------
    def show_order(self, order_id: str) -> str:
        """Retrieves and formats stored order details."""
        po = self.db.get_purchase_order(order_id)
        if not po:
            return f"Order '{order_id}' not found. Please verify the order ID."
        return self._format_plan_chat_response(po)

    def get_order(self, order_id: str) -> Optional[PurchaseOrder]:
        """Loads and returns the PurchaseOrder domain object."""
        return self.db.get_purchase_order(order_id)

    def list_orders(self) -> List[PurchaseOrder]:
        """Loads and returns all purchase orders."""
        return self.db.list_all_purchase_orders()

    def approve_order(self, order_id: str, actor: str = "store_manager") -> str:
        """Approves a pending order with strict pre-approval revalidation."""
        suppliers = self.get_suppliers()
        try:
            po = self.approval_service.approve_order(
                order_id=order_id,
                suppliers=suppliers,
                actor=actor,
            )
            return (
                f"STOCKWISE ORDER APPROVAL CONFIRMATION\n"
                f"============================================================\n"
                f"Order ID:     {po.order_id}\n"
                f"New Status:   {po.status.value.upper()}\n"
                f"Total Amount: ₹{po.total_cost:,.2f}\n"
                f"Decision:     Approved by {actor}\n"
                f"Verification: Budget, live supplier catalogs, and MOQs revalidated successfully.\n"
                f"============================================================\n"
                f"Next Action: Say 'Simulate placing order {po.order_id}' to execute simulated dispatch."
            )
        except OrderValidationError as e:
            return f"[APPROVAL REJECTED BY SAFETY AUDIT] Order {order_id} failed revalidation: {e}"
        except InvalidStateTransitionError as e:
            return f"[INVALID TRANSITION] {e}"
        except ValueError as e:
            return str(e)

    def reject_order(self, order_id: str, reason: str = "Rejected by user", actor: str = "store_manager") -> str:
        """Rejects a purchase order."""
        try:
            po = self.approval_service.reject_order(
                order_id=order_id,
                reason=reason,
                actor=actor,
            )
            return (
                f"STOCKWISE ORDER REJECTION\n"
                f"============================================================\n"
                f"Order ID:   {po.order_id}\n"
                f"New Status: {po.status.value.upper()}\n"
                f"Reason:     {reason}\n"
                f"Actor:      {actor}\n"
                f"============================================================"
            )
        except InvalidStateTransitionError as e:
            return f"[INVALID TRANSITION] {e}"
        except ValueError as e:
            return str(e)

    def simulate_placement(self, order_id: str, actor: str = "procurement_agent") -> str:
        """Simulates placing an approved order with vendors."""
        suppliers = self.get_suppliers()
        try:
            po = self.approval_service.place_simulated_order(
                order_id=order_id,
                suppliers=suppliers,
                actor=actor,
            )
            return (
                f"STOCKWISE SIMULATED DISPATCH SUCCESSFUL\n"
                f"============================================================\n"
                f"Order ID:    {po.order_id}\n"
                f"Status:      {po.status.value.upper()} (Explicit Test / Demo Mode)\n"
                f"Total Cost:  ₹{po.total_cost:,.2f}\n"
                f"Suppliers:   {', '.join(po.supplier_delivery_charges.keys())}\n"
                f"Audit Event: Simulated vendor dispatch completed successfully.\n"
                f"Notice:      [NO real funds were charged; NO physical goods dispatched]\n"
                f"============================================================"
            )
        except OrderValidationError as e:
            return f"[PLACEMENT BLOCKED] Order {order_id} failed final revalidation: {e}"
        except InvalidStateTransitionError as e:
            return f"[INVALID TRANSITION] {e}"
        except ValueError as e:
            return str(e)

    # ------------------------------------------------------------------
    # 5. Supplier Failure & Recalculation
    # ------------------------------------------------------------------
    def report_supplier_failure_and_replan(
        self,
        supplier_id: str,
        budget: Decimal = Decimal("20000.00"),
    ) -> Tuple[PurchaseOrder, str]:
        """Flags supplier as failed, excludes them from scoring, and replans procurement."""
        sup_id_clean = supplier_id.strip().upper()
        if sup_id_clean not in self.failed_supplier_ids:
            self.failed_supplier_ids.append(sup_id_clean)

        po, plan_text = self.create_procurement_plan(
            budget=budget,
            user_query=f"Replanning after supplier {sup_id_clean} failure",
        )

        recovery_header = (
            f"SUPPLIER FAILURE NOTIFICATION & AUTOMATED REPLANNING\n"
            f"============================================================\n"
            f"Supplier '{sup_id_clean}' has been flagged as FAILED/OFFLINE.\n"
            f"Autonomous optimizer recalculated replenishment using next-best suppliers.\n"
            f"------------------------------------------------------------\n"
        )
        return po, recovery_header + plan_text
