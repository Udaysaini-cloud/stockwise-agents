// StockWise Frontend TypeScript Type Definitions

export type OrderStatus =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'simulated_placed'
  | 'rejected'
  | 'failed';

export interface Product {
  sku: string;
  name: string;
  category: string;
  current_stock: number;
  average_daily_sales: number;
  outstanding_orders: number;
  safety_stock: number;
  target_stock_cover_days: number;
  unit: string;
}

export interface StockRequirement {
  sku: string;
  name: string;
  category: string;
  current_stock: number;
  average_daily_sales: number;
  outstanding_orders: number;
  safety_stock: number;
  target_stock_cover_days: number;
  target_stock: number;
  effective_stock: number;
  net_deficit: number;
  gross_reorder_qty: number;
  days_of_stock_left: number;
  is_urgent: boolean;
  min_supplier_lead_time_days: number;
}

export interface OrderLineItem {
  sku: string;
  product_name: string;
  supplier_id: string;
  supplier_name: string;
  ordered_quantity: number;
  unit_cost: number | string;
  line_total: number | string;
  lead_time_days: number;
  pack_size: number;
  moq: number;
}

export interface DeferredItem {
  sku: string;
  product_name: string;
  needed_quantity: number;
  reason: string;
  estimated_cost?: number | string | null;
}

export interface PurchaseOrder {
  order_id: string;
  request_id: string;
  status: OrderStatus;
  items: OrderLineItem[];
  supplier_delivery_charges: Record<string, number | string>;
  subtotal: number | string;
  total_delivery_charges: number | string;
  total_cost: number | string;
  budget: number | string;
  remaining_budget: number | string;
  deferred_items: DeferredItem[];
  created_at: string;
  updated_at: string;
}

export interface OrderAuditEvent {
  event_id: string;
  order_id: string;
  from_state: string;
  to_state: string;
  reason: string;
  timestamp: string;
  actor: string;
}

export interface SupplierOffer {
  supplier_id: string;
  supplier_name: string;
  sku: string;
  unit_cost: number;
  lead_time_days: number;
  moq: number;
  pack_size: number;
  available: boolean;
  feasible_quantity: number;
  item_total_cost: number;
  quality_score: number;
  on_time_delivery_rate: number;
  composite_score: number;
  disqualification_reason: string | null;
}

export interface SupplierComparisonResult {
  requirement: StockRequirement;
  ranked_offers: SupplierOffer[];
}

export interface SupplierProductOffer {
  unit_cost: number | string;
  lead_time_days: number;
  moq: number;
  pack_size: number;
  available: boolean;
}

export interface Supplier {
  id?: string;
  supplier_id?: string;
  name: string;
  location?: string;
  quality_rating?: number;
  on_time_delivery_rate?: number;
  minimum_order_value?: number | string;
  delivery_charge: number | string;
  catalog: Record<string, SupplierProductOffer>;
}

export interface OverviewMetrics {
  total_skus: number;
  total_units_in_stock: number;
  shortages_count: number;
  critical_shortages_count: number;
  total_suppliers: number;
  active_orders_count: number;
  total_committed_orders_cost: number;
  recent_orders: PurchaseOrder[];
  categories: Record<string, number>;
  critical_items: StockRequirement[];
}
