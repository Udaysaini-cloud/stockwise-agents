"""StockWise SQLite Persistence and Order Approval State Machine.

Implements transactional SQLite storage for:
- Procurement requests
- Purchase orders (PO)
- Order line items
- Deferred line items
- Immutable audit event trail

Implements the explicit state machine:
draft -> pending_approval -> approved -> simulated_placed
                             \\-> rejected
                             \\-> failed

Enforces:
- Unique order IDs and request IDs
- Pre-approval revalidation of budget, supplier availability, and line contents
- Idempotent approval and placement (repeated calls never create duplicate purchases)
- Transaction safety with rollback on failure
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.schemas import (
    DeferredItem,
    OrderAuditEvent,
    OrderLineItem,
    OrderStatus,
    ProcurementRequest,
    PurchaseOrder,
    Supplier,
)


class InvalidStateTransitionError(Exception):
    """Raised when an illegal order state transition is attempted."""

    pass


class OrderValidationError(Exception):
    """Raised when an order fails revalidation prior to approval or placement."""

    pass


# Permitted state transition map
PERMITTED_TRANSITIONS: Dict[OrderStatus, List[OrderStatus]] = {
    OrderStatus.DRAFT: [OrderStatus.PENDING_APPROVAL, OrderStatus.REJECTED],
    OrderStatus.PENDING_APPROVAL: [OrderStatus.APPROVED, OrderStatus.REJECTED, OrderStatus.FAILED],
    OrderStatus.APPROVED: [OrderStatus.SIMULATED_PLACED, OrderStatus.FAILED, OrderStatus.REJECTED],
    OrderStatus.SIMULATED_PLACED: [],  # Terminal state
    OrderStatus.REJECTED: [],          # Terminal state
    OrderStatus.FAILED: [OrderStatus.PENDING_APPROVAL, OrderStatus.REJECTED], # Can retry to pending or reject
}


def utc_now_iso() -> str:
    """Returns current UTC ISO timestamp string."""
    return datetime.now(timezone.utc).isoformat()


class ProcurementDatabase:
    """SQLite Database manager for StockWise procurement engine."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        """Creates tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS procurement_requests (
                    request_id TEXT PRIMARY KEY,
                    user_query TEXT NOT NULL,
                    budget TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS purchase_orders (
                    order_id TEXT PRIMARY KEY,
                    request_id TEXT,
                    status TEXT NOT NULL,
                    budget TEXT NOT NULL,
                    subtotal TEXT NOT NULL,
                    total_delivery_charges TEXT NOT NULL,
                    total_cost TEXT NOT NULL,
                    remaining_budget TEXT NOT NULL,
                    supplier_delivery_charges TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (request_id) REFERENCES procurement_requests(request_id)
                );

                CREATE TABLE IF NOT EXISTS order_line_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    supplier_id TEXT NOT NULL,
                    supplier_name TEXT NOT NULL,
                    ordered_quantity INTEGER NOT NULL,
                    unit_cost TEXT NOT NULL,
                    line_total TEXT NOT NULL,
                    lead_time_days INTEGER NOT NULL,
                    pack_size INTEGER NOT NULL,
                    moq INTEGER NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES purchase_orders(order_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS deferred_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    needed_quantity INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    estimated_cost TEXT,
                    FOREIGN KEY (order_id) REFERENCES purchase_orders(order_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS order_audit_events (
                    event_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES purchase_orders(order_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status);
                CREATE INDEX IF NOT EXISTS idx_audit_order ON order_audit_events(order_id);
                """
            )

    # -------------------------------------------------------------
    # Procurement Requests
    # -------------------------------------------------------------
    def save_procurement_request(self, req: ProcurementRequest) -> None:
        """Saves a new procurement request."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO procurement_requests (request_id, user_query, budget, created_at, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (req.request_id, req.user_query, str(req.budget), req.created_at, req.status),
            )

    def get_procurement_request(self, request_id: str) -> Optional[ProcurementRequest]:
        """Retrieves a procurement request by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM procurement_requests WHERE request_id = ?", (request_id,)
            ).fetchone()
            if not row:
                return None
            return ProcurementRequest(
                request_id=row["request_id"],
                user_query=row["user_query"],
                budget=Decimal(row["budget"]),
                created_at=row["created_at"],
                status=row["status"],
            )

    # -------------------------------------------------------------
    # Purchase Order CRUD
    # -------------------------------------------------------------
    def save_purchase_order(self, po: PurchaseOrder, actor: str = "system") -> None:
        """Saves or updates a purchase order with its line items in a single transaction."""
        now = utc_now_iso()
        created_at = po.created_at or now
        updated_at = now

        with self._get_connection() as conn:
            # Check existing status for initial audit event
            existing = conn.execute(
                "SELECT status FROM purchase_orders WHERE order_id = ?", (po.order_id,)
            ).fetchone()

            conn.execute(
                """
                INSERT OR REPLACE INTO purchase_orders (
                    order_id, request_id, status, budget, subtotal, total_delivery_charges,
                    total_cost, remaining_budget, supplier_delivery_charges, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    po.order_id,
                    po.request_id,
                    po.status.value,
                    str(po.budget),
                    str(po.subtotal),
                    str(po.total_delivery_charges),
                    str(po.total_cost),
                    str(po.remaining_budget),
                    json.dumps({k: str(v) for k, v in po.supplier_delivery_charges.items()}),
                    created_at,
                    updated_at,
                ),
            )

            # Refresh line items
            conn.execute("DELETE FROM order_line_items WHERE order_id = ?", (po.order_id,))
            for item in po.items:
                conn.execute(
                    """
                    INSERT INTO order_line_items (
                        order_id, sku, product_name, supplier_id, supplier_name,
                        ordered_quantity, unit_cost, line_total, lead_time_days, pack_size, moq
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        po.order_id,
                        item.sku,
                        item.product_name,
                        item.supplier_id,
                        item.supplier_name,
                        item.ordered_quantity,
                        str(item.unit_cost),
                        str(item.line_total),
                        item.lead_time_days,
                        item.pack_size,
                        item.moq,
                    ),
                )

            # Refresh deferred items
            conn.execute("DELETE FROM deferred_items WHERE order_id = ?", (po.order_id,))
            for d in po.deferred_items:
                conn.execute(
                    """
                    INSERT INTO deferred_items (
                        order_id, sku, product_name, needed_quantity, reason, estimated_cost
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        po.order_id,
                        d.sku,
                        d.product_name,
                        d.needed_quantity,
                        d.reason,
                        str(d.estimated_cost) if d.estimated_cost is not None else None,
                    ),
                )

            # If brand new record, record initial creation audit event
            if existing is None:
                event_id = f"EVT-{uuid.uuid4().hex[:8].upper()}"
                conn.execute(
                    """
                    INSERT INTO order_audit_events (event_id, order_id, from_state, to_state, reason, timestamp, actor)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (event_id, po.order_id, "none", po.status.value, "Order created", now, actor),
                )

    def get_purchase_order(self, order_id: str) -> Optional[PurchaseOrder]:
        """Loads a complete purchase order including line items and deferred items."""
        with self._get_connection() as conn:
            po_row = conn.execute(
                "SELECT * FROM purchase_orders WHERE order_id = ?", (order_id,)
            ).fetchone()
            if not po_row:
                return None

            # Load line items
            item_rows = conn.execute(
                "SELECT * FROM order_line_items WHERE order_id = ? ORDER BY id ASC", (order_id,)
            ).fetchall()
            items = [
                OrderLineItem(
                    sku=r["sku"],
                    product_name=r["product_name"],
                    supplier_id=r["supplier_id"],
                    supplier_name=r["supplier_name"],
                    ordered_quantity=r["ordered_quantity"],
                    unit_cost=Decimal(r["unit_cost"]),
                    line_total=Decimal(r["line_total"]),
                    lead_time_days=r["lead_time_days"],
                    pack_size=r["pack_size"],
                    moq=r["moq"],
                )
                for r in item_rows
            ]

            # Load deferred items
            deferred_rows = conn.execute(
                "SELECT * FROM deferred_items WHERE order_id = ? ORDER BY id ASC", (order_id,)
            ).fetchall()
            deferred_items = [
                DeferredItem(
                    sku=r["sku"],
                    product_name=r["product_name"],
                    needed_quantity=r["needed_quantity"],
                    reason=r["reason"],
                    estimated_cost=Decimal(r["estimated_cost"]) if r["estimated_cost"] else None,
                )
                for r in deferred_rows
            ]

            # Parse delivery charges dictionary
            delivery_charges_raw = json.loads(po_row["supplier_delivery_charges"])
            supplier_delivery_charges = {k: Decimal(v) for k, v in delivery_charges_raw.items()}

            return PurchaseOrder(
                order_id=po_row["order_id"],
                request_id=po_row["request_id"],
                status=OrderStatus(po_row["status"]),
                items=items,
                supplier_delivery_charges=supplier_delivery_charges,
                subtotal=Decimal(po_row["subtotal"]),
                total_delivery_charges=Decimal(po_row["total_delivery_charges"]),
                total_cost=Decimal(po_row["total_cost"]),
                budget=Decimal(po_row["budget"]),
                remaining_budget=Decimal(po_row["remaining_budget"]),
                deferred_items=deferred_items,
                created_at=po_row["created_at"],
                updated_at=po_row["updated_at"],
            )

    def list_all_purchase_orders(self) -> List[PurchaseOrder]:
        """Loads all purchase orders ordered by creation date descending."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT order_id FROM purchase_orders ORDER BY created_at DESC"
            ).fetchall()
            orders: List[PurchaseOrder] = []
            for r in rows:
                po = self.get_purchase_order(r["order_id"])
                if po:
                    orders.append(po)
            return orders

    # -------------------------------------------------------------
    # Audit Trail
    # -------------------------------------------------------------
    def record_audit_event(
        self,
        order_id: str,
        from_state: str,
        to_state: str,
        reason: str,
        actor: str = "system",
    ) -> OrderAuditEvent:
        """Appends an immutable audit event for an order state transition."""
        event_id = f"EVT-{uuid.uuid4().hex[:8].upper()}"
        now = utc_now_iso()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO order_audit_events (event_id, order_id, from_state, to_state, reason, timestamp, actor)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, order_id, from_state, to_state, reason, now, actor),
            )
        return OrderAuditEvent(
            event_id=event_id,
            order_id=order_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            timestamp=now,
            actor=actor,
        )

    def get_order_audit_trail(self, order_id: str) -> List[OrderAuditEvent]:
        """Returns the complete audit log history for an order, ordered chronologically."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM order_audit_events WHERE order_id = ? ORDER BY timestamp ASC",
                (order_id,),
            ).fetchall()
            return [
                OrderAuditEvent(
                    event_id=r["event_id"],
                    order_id=r["order_id"],
                    from_state=r["from_state"],
                    to_state=r["to_state"],
                    reason=r["reason"],
                    timestamp=r["timestamp"],
                    actor=r["actor"],
                )
                for r in rows
            ]

    # -------------------------------------------------------------
    # Transaction-Safe State Transitions & Idempotency
    # -------------------------------------------------------------
    def transition_order_status(
        self,
        order_id: str,
        target_status: OrderStatus,
        reason: str,
        actor: str = "system",
    ) -> PurchaseOrder:
        """Transitions an order from current status to target_status.

        Guarantees:
        - Atomic update
        - Idempotency: if already in target_status, returns current order without duplicate transition
        - Validates transition according to PERMITTED_TRANSITIONS
        """
        now = utc_now_iso()
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM purchase_orders WHERE order_id = ?", (order_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Purchase order {order_id} does not exist.")

            current_status = OrderStatus(row["status"])

            # Idempotency check: if already in the target state, return gracefully
            if current_status == target_status:
                po = self.get_purchase_order(order_id)
                assert po is not None
                return po

            # Validation check
            allowed = PERMITTED_TRANSITIONS.get(current_status, [])
            if target_status not in allowed:
                raise InvalidStateTransitionError(
                    f"Illegal order state transition for {order_id}: cannot transition "
                    f"from '{current_status.value}' to '{target_status.value}'. "
                    f"Allowed transitions: {[s.value for s in allowed]}"
                )

            # Update status
            conn.execute(
                "UPDATE purchase_orders SET status = ?, updated_at = ? WHERE order_id = ?",
                (target_status.value, now, order_id),
            )

            # Record audit event
            event_id = f"EVT-{uuid.uuid4().hex[:8].upper()}"
            conn.execute(
                """
                INSERT INTO order_audit_events (event_id, order_id, from_state, to_state, reason, timestamp, actor)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, order_id, current_status.value, target_status.value, reason, now, actor),
            )

        po = self.get_purchase_order(order_id)
        assert po is not None
        return po


# -------------------------------------------------------------
# Revalidation & Safe Approval Service
# -------------------------------------------------------------
class OrderApprovalService:
    """Provides safe, idempotent, revalidated order approvals."""

    def __init__(self, db: ProcurementDatabase):
        self.db = db

    def submit_for_approval(self, order_id: str, actor: str = "user") -> PurchaseOrder:
        """Transitions order from DRAFT to PENDING_APPROVAL."""
        return self.db.transition_order_status(
            order_id=order_id,
            target_status=OrderStatus.PENDING_APPROVAL,
            reason="Submitted for managerial approval",
            actor=actor,
        )

    def validate_order_pre_approval(
        self,
        order: PurchaseOrder,
        suppliers: List[Supplier],
        max_budget: Optional[Decimal] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Revalidates budget, line items, and current supplier availability.

        Returns (is_valid, error_message).
        """
        # 1. Check line items exist
        if not order.items:
            return False, "Order contains no line items."

        # 2. Check budget compliance
        effective_budget = max_budget if max_budget is not None else order.budget
        if order.total_cost > effective_budget:
            return False, (
                f"Budget violation: Total landed cost ₹{order.total_cost:,.2f} "
                f"exceeds authorized limit ₹{effective_budget:,.2f}"
            )

        # 3. Check live supplier availability and catalog match
        supplier_map = {s.id: s for s in suppliers}
        for item in order.items:
            sup = supplier_map.get(item.supplier_id)
            if not sup:
                return False, f"Supplier {item.supplier_id} is no longer recognized in vendor directory."
            offer = sup.catalog.get(item.sku)
            if not offer:
                return False, f"Supplier {item.supplier_id} no longer catalogs SKU {item.sku}."
            if not offer.available:
                return False, f"Supplier {item.supplier_id} currently reports SKU {item.sku} out of stock."
            if item.ordered_quantity < offer.moq:
                return False, f"Quantity {item.ordered_quantity} for {item.sku} violates current supplier MOQ ({offer.moq})."

        return True, None

    def approve_order(
        self,
        order_id: str,
        suppliers: List[Supplier],
        actor: str = "store_manager",
        max_budget: Optional[Decimal] = None,
    ) -> PurchaseOrder:
        """Approves a purchase order with strict pre-approval revalidation.

        Idempotent: If the order is already APPROVED, returns immediately without re-transition.
        """
        po = self.db.get_purchase_order(order_id)
        if not po:
            raise ValueError(f"Purchase order {order_id} not found.")

        # Idempotency check: if already approved, return current order safely
        if po.status == OrderStatus.APPROVED:
            return po

        # Must be in pending_approval
        if po.status != OrderStatus.PENDING_APPROVAL:
            raise InvalidStateTransitionError(
                f"Cannot approve order {order_id} in status '{po.status.value}'. Must be 'pending_approval'."
            )

        # Revalidate order contents and supplier availability immediately prior to approval
        is_valid, error_msg = self.validate_order_pre_approval(po, suppliers, max_budget=max_budget)
        if not is_valid:
            # Transition to failed with explicit reason
            self.db.transition_order_status(
                order_id=order_id,
                target_status=OrderStatus.FAILED,
                reason=f"Pre-approval revalidation failed: {error_msg}",
                actor=actor,
            )
            raise OrderValidationError(f"Pre-approval revalidation failed: {error_msg}")

        # Revalidation passed -> approve
        return self.db.transition_order_status(
            order_id=order_id,
            target_status=OrderStatus.APPROVED,
            reason="Pre-approval revalidation passed; order approved",
            actor=actor,
        )

    def reject_order(self, order_id: str, reason: str, actor: str = "store_manager") -> PurchaseOrder:
        """Rejects a purchase order."""
        return self.db.transition_order_status(
            order_id=order_id,
            target_status=OrderStatus.REJECTED,
            reason=f"Order rejected: {reason}",
            actor=actor,
        )

    def place_simulated_order(
        self,
        order_id: str,
        suppliers: List[Supplier],
        actor: str = "procurement_agent",
    ) -> PurchaseOrder:
        """Simulates placing an approved order with vendors.

        Labelled as explicitly simulated per MASTER_PLAN.md:
        The agent must never claim that a real commercial purchase was placed.
        Idempotent: If already SIMULATED_PLACED, returns safely.
        """
        po = self.db.get_purchase_order(order_id)
        if not po:
            raise ValueError(f"Purchase order {order_id} not found.")

        # Idempotency check
        if po.status == OrderStatus.SIMULATED_PLACED:
            return po

        if po.status != OrderStatus.APPROVED:
            raise InvalidStateTransitionError(
                f"Cannot place simulated order {order_id} in status '{po.status.value}'. Order must be 'approved'."
            )

        # Revalidate one final time before simulated dispatch
        is_valid, error_msg = self.validate_order_pre_approval(po, suppliers)
        if not is_valid:
            self.db.transition_order_status(
                order_id=order_id,
                target_status=OrderStatus.FAILED,
                reason=f"Simulated dispatch failed revalidation: {error_msg}",
                actor=actor,
            )
            raise OrderValidationError(f"Simulated placement revalidation failed: {error_msg}")

        return self.db.transition_order_status(
            order_id=order_id,
            target_status=OrderStatus.SIMULATED_PLACED,
            reason="Simulated vendor dispatch completed successfully (Test / Demo Mode)",
            actor=actor,
        )
