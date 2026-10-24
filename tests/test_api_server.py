"""Tests for FastAPI Web Dashboard API Endpoints."""

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from pathlib import Path

from agents.api_server import app, procurement_service
from core.persistence import ProcurementDatabase, OrderApprovalService
from core.schemas import OrderStatus


@pytest.fixture(autouse=True)
def setup_isolated_db(tmp_path: Path):
    """Use an isolated temporary SQLite database for each API test."""
    temp_db = tmp_path / "test_api_stockwise.db"
    procurement_service.db = ProcurementDatabase(temp_db)
    procurement_service.approval_service = OrderApprovalService(procurement_service.db)
    procurement_service.failed_supplier_ids = []


@pytest.fixture
def client():
    return TestClient(app)


def test_api_health(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["synthetic_data_mode"] is True


def test_api_overview(client: TestClient):
    response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()
    assert "total_skus" in data
    assert data["total_skus"] == 15
    assert "shortages_count" in data
    assert "total_units_in_stock" in data
    assert "categories" in data


def test_api_inventory(client: TestClient):
    response = client.get("/api/inventory")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 15
    first = items[0]
    assert "sku" in first
    assert "current_stock" in first
    assert "gross_reorder_qty" in first
    assert "days_of_stock_left" in first


def test_api_suppliers_and_compare(client: TestClient):
    # Suppliers list
    resp = client.get("/api/suppliers")
    assert resp.status_code == 200
    suppliers = resp.json()
    assert len(suppliers) == 4

    # Supplier comparison
    resp2 = client.get("/api/suppliers/compare")
    assert resp2.status_code == 200
    comparisons = resp2.json()
    assert len(comparisons) > 0
    assert "requirement" in comparisons[0]
    assert "ranked_offers" in comparisons[0]


def test_api_plan_creation_approval_and_placement_lifecycle(client: TestClient):
    # 1. Create plan
    plan_resp = client.post("/api/procurement/plan", json={"budget": 25000.0, "user_query": "Test plan"})
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    order = plan_data["order"]
    order_id = order["order_id"]
    assert order["status"] == "pending_approval"
    assert float(order["budget"]) == 25000.0
    assert float(order["total_cost"]) <= 25000.0

    # 2. List orders
    list_resp = client.get("/api/orders")
    assert list_resp.status_code == 200
    orders = list_resp.json()
    assert any(o["order_id"] == order_id for o in orders)

    # 3. Get specific order
    get_resp = client.get(f"/api/orders/{order_id}")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["order"]["order_id"] == order_id
    assert len(get_data["audit_trail"]) >= 1

    # 4. Attempt simulated placement without approval -> MUST FAIL (HTTP 409)
    bad_place = client.post(f"/api/orders/{order_id}/simulate-placement", json={"actor": "test"})
    assert bad_place.status_code == 409

    # 5. Approve order
    appr_resp = client.post(f"/api/orders/{order_id}/approve", json={"actor": "manager_alice"})
    assert appr_resp.status_code == 200
    assert appr_resp.json()["order"]["status"] == "approved"

    # 6. Simulate placement of approved order -> SUCCESS
    place_resp = client.post(f"/api/orders/{order_id}/simulate-placement", json={"actor": "procurement_bot"})
    assert place_resp.status_code == 200
    assert place_resp.json()["order"]["status"] == "simulated_placed"
    assert "Test / Demo Mode" in place_resp.json()["message"]


def test_api_order_rejection(client: TestClient):
    plan_resp = client.post("/api/procurement/plan", json={"budget": 18000.0})
    order_id = plan_resp.json()["order"]["order_id"]

    rej_resp = client.post(f"/api/orders/{order_id}/reject", json={"reason": "Excess inventory elsewhere"})
    assert rej_resp.status_code == 200
    assert rej_resp.json()["order"]["status"] == "rejected"

    # Cannot approve a rejected order
    appr_fail = client.post(f"/api/orders/{order_id}/approve", json={})
    assert appr_fail.status_code == 409


def test_api_chat_command(client: TestClient):
    chat_resp = client.post("/api/chat", json={"message": "Check inventory"})
    assert chat_resp.status_code == 200
    reply = chat_resp.json()["reply"]
    assert "STOCKWISE INVENTORY STATUS REPORT" in reply


def test_api_supplier_failure(client: TestClient):
    fail_resp = client.post("/api/suppliers/failure", json={"supplier_id": "SUP-001", "budget": 20000.0})
    assert fail_resp.status_code == 200
    data = fail_resp.json()
    assert "SUP-001" in data["failed_supplier_ids"]
    assert "SUPPLIER FAILURE NOTIFICATION" in data["summary_text"]
