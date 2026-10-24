// API Client connecting to the StockWise FastAPI backend

import {
  OverviewMetrics,
  StockRequirement,
  Supplier,
  SupplierComparisonResult,
  PurchaseOrder,
  OrderAuditEvent,
} from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    let errorMsg = `API Error ${res.status}: ${res.statusText}`;
    try {
      const errorJson = await res.json();
      if (errorJson.detail) {
        errorMsg = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
      }
    } catch {
      // fallback to status text
    }
    throw new Error(errorMsg);
  }

  return res.json();
}

export const api = {
  getHealth: () => request<{ status: string; service: string }>('/api/health'),

  getOverview: () => request<OverviewMetrics>('/api/overview'),

  getInventory: () => request<StockRequirement[]>('/api/inventory'),

  getSuppliers: () => request<Supplier[]>('/api/suppliers'),

  getSupplierComparison: () => request<SupplierComparisonResult[]>('/api/suppliers/compare'),

  createPlan: (budget: number, user_query?: string) =>
    request<{ order: PurchaseOrder; summary_text: string }>('/api/procurement/plan', {
      method: 'POST',
      body: JSON.stringify({ budget, user_query }),
    }),

  getOrders: () => request<PurchaseOrder[]>('/api/orders'),

  getOrderDetails: (orderId: string) =>
    request<{ order: PurchaseOrder; audit_trail: OrderAuditEvent[] }>(`/api/orders/${orderId}`),

  approveOrder: (orderId: string, actor = 'store_manager') =>
    request<{ order: PurchaseOrder; audit_trail: OrderAuditEvent[]; message: string }>(
      `/api/orders/${orderId}/approve`,
      {
        method: 'POST',
        body: JSON.stringify({ actor }),
      }
    ),

  rejectOrder: (orderId: string, reason: string, actor = 'store_manager') =>
    request<{ order: PurchaseOrder; audit_trail: OrderAuditEvent[]; message: string }>(
      `/api/orders/${orderId}/reject`,
      {
        method: 'POST',
        body: JSON.stringify({ reason, actor }),
      }
    ),

  simulatePlacement: (orderId: string, actor = 'procurement_agent') =>
    request<{ order: PurchaseOrder; audit_trail: OrderAuditEvent[]; message: string }>(
      `/api/orders/${orderId}/simulate-placement`,
      {
        method: 'POST',
        body: JSON.stringify({ actor }),
      }
    ),

  sendChatCommand: (message: string) =>
    request<{ reply: string; input: string }>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  reportSupplierFailure: (supplierId: string, budget = 20000) =>
    request<{ order: PurchaseOrder; summary_text: string; failed_supplier_ids: string[] }>(
      '/api/suppliers/failure',
      {
        method: 'POST',
        body: JSON.stringify({ supplier_id: supplierId, budget }),
      }
    ),
};
