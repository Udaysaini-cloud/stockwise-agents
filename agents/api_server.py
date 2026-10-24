"""FastAPI Backend Server for StockWise Agents Web Dashboard.

Provides REST endpoints for the Next.js frontend to interact with the
deterministic procurement service, inventory analytics, supplier scoring,
knapsack budget optimizer, order state machine, and chat command handler.
"""

import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.inventory import analyze_all_inventory
from core.persistence import (
    InvalidStateTransitionError,
    OrderAuditEvent,
    OrderValidationError,
    ProcurementDatabase,
)
from core.procurement_service import ProcurementService
from core.schemas import (
    DeferredItem,
    OrderLineItem,
    OrderStatus,
    Product,
    PurchaseOrder,
    StockRequirement,
    Supplier,
)
from core.supplier_scoring import rank_suppliers_for_requirement
from agents.coordinator import generate_response

app = FastAPI(
    title="StockWise Agents Procurement API",
    version="1.0.0",
    description="REST backend connecting StockWise procurement engine to the web dashboard.",
)

# Allow local Next.js frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stable paths resolved to project root
DB_PATH = PROJECT_ROOT / "data" / "stockwise.db"
INVENTORY_PATH = PROJECT_ROOT / "data" / "inventory.json"
SUPPLIERS_PATH = PROJECT_ROOT / "data" / "suppliers.json"

procurement_service = ProcurementService(
    db_path=DB_PATH,
    inventory_path=INVENTORY_PATH,
    suppliers_path=SUPPLIERS_PATH,
)


# ---------------------------------------------------------------------------
# Request & Response Models
# ---------------------------------------------------------------------------
class CreatePlanRequest(BaseModel):
    budget: float = Field(..., gt=0, description="Authorized budget in INR (₹)")
    user_query: Optional[str] = Field("Dashboard procurement request", description="Optional query notes")


class ApproveOrderRequest(BaseModel):
    actor: Optional[str] = Field("store_manager", description="Identity approving the order")


class RejectOrderRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Reason for rejection")
    actor: Optional[str] = Field("store_manager", description="Identity rejecting the order")


class SimulatePlacementRequest(BaseModel):
    actor: Optional[str] = Field("procurement_agent", description="Identity simulating placement")


class ChatCommandRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Natural language prompt or command")


class SupplierFailureRequest(BaseModel):
    supplier_id: str = Field(..., min_length=3, description="Supplier ID that failed (e.g. SUP-001)")
    budget: Optional[float] = Field(20000.0, gt=0, description="Budget for recalculation")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "StockWise Agents Dashboard API",
        "version": "1.0.0",
        "synthetic_data_mode": True,
    }


@app.get("/api/overview")
def get_overview_metrics() -> Dict[str, Any]:
    """Computes aggregated dashboard overview statistics from real backend data."""
    products = procurement_service.get_inventory()
    suppliers = procurement_service.get_suppliers()
    requirements = analyze_all_inventory(products, suppliers)

    shortages = [r for r in requirements if r.gross_reorder_qty > 0]
    critical = [r for r in shortages if r.is_urgent]
    orders = procurement_service.list_orders()

    total_units_in_stock = sum(p.current_stock for p in products)
    total_committed_orders = sum(
        o.total_cost for o in orders if o.status in (OrderStatus.APPROVED, OrderStatus.SIMULATED_PLACED)
    )

    # Categories breakdown
    categories: Dict[str, int] = {}
    for p in products:
        categories[p.category] = categories.get(p.category, 0) + 1

    return {
        "total_skus": len(products),
        "total_units_in_stock": total_units_in_stock,
        "shortages_count": len(shortages),
        "critical_shortages_count": len(critical),
        "total_suppliers": len(suppliers),
        "active_orders_count": len([o for o in orders if o.status in (OrderStatus.PENDING_APPROVAL, OrderStatus.APPROVED)]),
        "total_committed_orders_cost": float(total_committed_orders),
        "recent_orders": [o.model_dump(mode="json") for o in orders[:5]],
        "categories": categories,
        "critical_items": [r.model_dump(mode="json") for r in critical[:5]],
    }


@app.get("/api/inventory")
def get_inventory_requirements() -> List[Dict[str, Any]]:
    """Returns complete inventory status with shortage analytics."""
    products = procurement_service.get_inventory()
    suppliers = procurement_service.get_suppliers()
    requirements = analyze_all_inventory(products, suppliers)
    return [r.model_dump(mode="json") for r in requirements]


@app.get("/api/suppliers")
def get_suppliers() -> List[Dict[str, Any]]:
    """Returns catalog of all registered suppliers and their products."""
    suppliers = procurement_service.get_suppliers()
    return [s.model_dump(mode="json") for s in suppliers]


@app.get("/api/suppliers/compare")
def compare_suppliers_for_shortages() -> List[Dict[str, Any]]:
    """Compares supplier offers for urgent shortage items."""
    products = procurement_service.get_inventory()
    suppliers = procurement_service.get_suppliers()
    requirements = analyze_all_inventory(products, suppliers)
    shortages = [r for r in requirements if r.gross_reorder_qty > 0]

    comparison_results: List[Dict[str, Any]] = []
    for req in shortages:
        ranked = rank_suppliers_for_requirement(
            req, suppliers, failed_supplier_ids=procurement_service.failed_supplier_ids
        )
        comparison_results.append({
            "requirement": req.model_dump(mode="json"),
            "ranked_offers": [offer.model_dump(mode="json") for offer in ranked],
        })
    return comparison_results


@app.post("/api/procurement/plan")
def create_procurement_plan(payload: CreatePlanRequest) -> Dict[str, Any]:
    """Generates an optimized budget-constrained purchase order and persists it."""
    try:
        budget_decimal = Decimal(str(payload.budget))
        po, formatted_summary = procurement_service.create_procurement_plan(
            budget=budget_decimal,
            user_query=payload.user_query or "Dashboard request",
        )
        return {
            "order": po.model_dump(mode="json"),
            "summary_text": formatted_summary,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate plan: {str(e)}",
        )


@app.get("/api/orders")
def list_orders() -> List[Dict[str, Any]]:
    """Lists all stored purchase orders ordered by creation date."""
    orders = procurement_service.list_orders()
    return [o.model_dump(mode="json") for o in orders]


@app.get("/api/orders/{order_id}")
def get_order(order_id: str) -> Dict[str, Any]:
    """Fetches details for a specific purchase order."""
    po = procurement_service.get_order(order_id.upper())
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase order '{order_id}' not found.",
        )
    audit_trail = procurement_service.db.get_order_audit_trail(order_id.upper())
    return {
        "order": po.model_dump(mode="json"),
        "audit_trail": [e.model_dump(mode="json") for e in audit_trail],
    }


@app.post("/api/orders/{order_id}/approve")
def approve_order(order_id: str, payload: ApproveOrderRequest) -> Dict[str, Any]:
    """Approves a pending order with strict pre-approval revalidation."""
    try:
        suppliers = procurement_service.get_suppliers()
        po = procurement_service.approval_service.approve_order(
            order_id=order_id.upper(),
            suppliers=suppliers,
            actor=payload.actor or "store_manager",
        )
        audit_trail = procurement_service.db.get_order_audit_trail(order_id.upper())
        return {
            "order": po.model_dump(mode="json"),
            "audit_trail": [e.model_dump(mode="json") for e in audit_trail],
            "message": f"Order {order_id} approved successfully.",
        }
    except OrderValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Order safety validation failed: {str(e)}",
        )
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@app.post("/api/orders/{order_id}/reject")
def reject_order(order_id: str, payload: RejectOrderRequest) -> Dict[str, Any]:
    """Rejects an order and persists the audit trail."""
    try:
        po = procurement_service.approval_service.reject_order(
            order_id=order_id.upper(),
            reason=payload.reason,
            actor=payload.actor or "store_manager",
        )
        audit_trail = procurement_service.db.get_order_audit_trail(order_id.upper())
        return {
            "order": po.model_dump(mode="json"),
            "audit_trail": [e.model_dump(mode="json") for e in audit_trail],
            "message": f"Order {order_id} rejected.",
        }
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@app.post("/api/orders/{order_id}/simulate-placement")
def simulate_placement(order_id: str, payload: SimulatePlacementRequest) -> Dict[str, Any]:
    """Simulates placement of an approved purchase order."""
    try:
        suppliers = procurement_service.get_suppliers()
        po = procurement_service.approval_service.place_simulated_order(
            order_id=order_id.upper(),
            suppliers=suppliers,
            actor=payload.actor or "procurement_agent",
        )
        audit_trail = procurement_service.db.get_order_audit_trail(order_id.upper())
        return {
            "order": po.model_dump(mode="json"),
            "audit_trail": [e.model_dump(mode="json") for e in audit_trail],
            "message": "Simulated vendor dispatch completed successfully (Test / Demo Mode). No real payment or goods moved.",
        }
    except OrderValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Revalidation error before simulated placement: {str(e)}",
        )
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@app.post("/api/chat")
def handle_chat_command(payload: ChatCommandRequest) -> Dict[str, Any]:
    """Executes a conversational procurement command through the existing engine."""
    reply = generate_response(payload.message, service=procurement_service)
    return {
        "reply": reply,
        "input": payload.message,
    }


@app.post("/api/suppliers/failure")
def handle_supplier_failure(payload: SupplierFailureRequest) -> Dict[str, Any]:
    """Flags a supplier as offline and recalculates plan with remaining suppliers."""
    budget_decimal = Decimal(str(payload.budget or 20000.0))
    po, summary_text = procurement_service.report_supplier_failure_and_replan(
        supplier_id=payload.supplier_id,
        budget=budget_decimal,
    )
    return {
        "order": po.model_dump(mode="json"),
        "summary_text": summary_text,
        "failed_supplier_ids": procurement_service.failed_supplier_ids,
    }
