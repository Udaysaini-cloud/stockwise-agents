"""StockWise Inventory Analysis.

Implements the official MASTER_PLAN inventory calculations:
Target Stock = Average Daily Sales * (Lead Time + Target Stock Cover) + Safety Stock
Reorder Quantity = max(0, Target Stock - Available Stock - Outstanding Purchase Quantity)
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Optional
from core.schemas import Product, StockRequirement, Supplier


def load_inventory(filepath: str | Path) -> List[Product]:
    """Load inventory list from a JSON file."""
    path = Path(filepath)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Product(**item) for item in data]


def load_suppliers(filepath: str | Path) -> List[Supplier]:
    """Load supplier list from a JSON file."""
    path = Path(filepath)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Supplier(**item) for item in data]


def get_default_lead_time_for_sku(sku: str, suppliers: List[Supplier], fallback_days: int = 3) -> int:
    """Find the minimum or typical available lead time across suppliers offering this SKU."""
    lead_times = [
        s.catalog[sku].lead_time_days
        for s in suppliers
        if sku in s.catalog and s.catalog[sku].available
    ]
    if lead_times:
        return min(lead_times)
    # If no available supplier, check if any supplier catalogs it
    all_times = [s.catalog[sku].lead_time_days for s in suppliers if sku in s.catalog]
    return min(all_times) if all_times else fallback_days


def calculate_stock_requirement(
    product: Product,
    lead_time_days: Optional[int] = None,
    suppliers: Optional[List[Supplier]] = None,
) -> StockRequirement:
    """Calculate the stock shortfall and reorder quantity for a single product."""
    if lead_time_days is None:
        if suppliers:
            lead_time_days = get_default_lead_time_for_sku(product.sku, suppliers)
        else:
            lead_time_days = 3

    # Formula per MASTER_PLAN.md:
    # Target Stock = Average Daily Sales * (Lead Time + Target Stock Cover) + Safety Stock
    exact_target = product.average_daily_sales * (lead_time_days + product.target_stock_cover_days) + product.safety_stock
    target_stock = math.ceil(exact_target)

    # Reorder Quantity = max(0, Target Stock - Available Stock - Outstanding Orders)
    available_stock = product.current_stock
    effective_stock = available_stock + product.outstanding_orders
    gross_reorder = max(0, target_stock - effective_stock)

    # Days of stock left based on current physical stock and sales rate
    if product.average_daily_sales > 0:
        days_of_stock_left = round(available_stock / product.average_daily_sales, 1)
    else:
        days_of_stock_left = 999.0

    # Urgency assessment
    # An item is urgent if current physical stock <= safety stock or days of stock left <= lead time
    is_urgent = (available_stock <= product.safety_stock) or (days_of_stock_left <= lead_time_days)
    
    # Priority score for sorting: items with fewer days of stock left have higher urgency
    if days_of_stock_left <= 0:
        urgency_score = 100.0
    else:
        # Scale: e.g. 0.5 days left -> score ~ 95, 10 days left -> score ~ 10
        urgency_score = round(max(0.0, 100.0 - (days_of_stock_left * 8.0)), 2)

    return StockRequirement(
        sku=product.sku,
        name=product.name,
        current_stock=available_stock,
        outstanding_orders=product.outstanding_orders,
        effective_stock=effective_stock,
        average_daily_sales=product.average_daily_sales,
        lead_time_days_used=lead_time_days,
        safety_stock=product.safety_stock,
        target_stock_cover_days=product.target_stock_cover_days,
        target_stock=target_stock,
        gross_reorder_qty=gross_reorder,
        days_of_stock_left=days_of_stock_left,
        urgency_score=urgency_score,
        is_urgent=is_urgent,
    )


def analyze_all_inventory(
    products: List[Product],
    suppliers: List[Supplier],
) -> List[StockRequirement]:
    """Calculate requirements for all products and sort by descending urgency."""
    requirements = [
        calculate_stock_requirement(p, suppliers=suppliers)
        for p in products
    ]
    # Sort: shortages first, highest urgency score first
    requirements.sort(key=lambda r: (r.gross_reorder_qty > 0, r.urgency_score), reverse=True)
    return requirements
