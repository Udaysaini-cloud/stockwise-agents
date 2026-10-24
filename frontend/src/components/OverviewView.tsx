'use client';

import React from 'react';
import {
  Boxes,
  AlertTriangle,
  ClipboardList,
  ArrowRight,
  TrendingUp,
  ShieldCheck,
  ChevronRight,
  CheckCircle2,
  Clock,
  ExternalLink,
} from 'lucide-react';
import { OverviewMetrics } from '@/types';
import { formatINR, formatDate } from '@/lib/format';
import { MetricCard } from '@/components/common/MetricCard';
import { StatusBadge } from '@/components/common/StatusBadge';
import { PageHeader } from '@/components/common/PageHeader';
import { EmptyState } from '@/components/common/EmptyState';

interface OverviewViewProps {
  metrics: OverviewMetrics | null;
  loading: boolean;
  onNavigate: (tab: any) => void;
  onSelectOrder: (orderId: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  metrics,
  loading,
  onNavigate,
  onSelectOrder,
}) => {
  if (loading || !metrics) {
    return (
      <div className="p-8 space-y-6 max-w-7xl mx-auto">
        <div className="h-8 bg-slate-200 rounded-lg w-48 animate-pulse" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-white border border-slate-200 rounded-xl animate-pulse" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 h-80 bg-white border border-slate-200 rounded-xl animate-pulse" />
          <div className="h-80 bg-white border border-slate-200 rounded-xl animate-pulse" />
        </div>
      </div>
    );
  }

  // Stock health proportions calculation
  const total = metrics.total_skus || 1;
  const critical = metrics.critical_shortages_count || 0;
  const moderate = Math.max(0, (metrics.shortages_count || 0) - critical);
  const healthy = Math.max(0, total - (metrics.shortages_count || 0));

  const criticalPct = Math.round((critical / total) * 100);
  const moderatePct = Math.round((moderate / total) * 100);
  const healthyPct = Math.max(0, 100 - criticalPct - moderatePct);

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <PageHeader
        title="Procurement Overview"
        description="Real-time replenishment health, catalog stockout analytics, and purchase order lifecycle ledger."
      >
        <button
          onClick={() => onNavigate('planner')}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-all"
        >
          <span>Create purchase plan</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </PageHeader>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Catalog SKUs"
          value={metrics.total_skus}
          subtitle={`${metrics.total_units_in_stock.toLocaleString()} total units in warehouse`}
          icon={Boxes}
          onClick={() => onNavigate('inventory')}
          actionText="View catalog"
        />

        <MetricCard
          title="Low-Stock Products"
          value={metrics.shortages_count}
          subtitle="Reorder required to hit safety target"
          badge={{
            text: `${Math.round((metrics.shortages_count / total) * 100)}% of catalog`,
            variant: metrics.shortages_count > 0 ? 'warning' : 'success',
          }}
          icon={AlertTriangle}
          onClick={() => onNavigate('inventory')}
          actionText="Filter low stock"
        />

        <MetricCard
          title="Critical Shortages"
          value={metrics.critical_shortages_count}
          subtitle="Stockouts within supplier lead time"
          badge={{
            text: metrics.critical_shortages_count > 0 ? 'Action required' : 'Optimal',
            variant: metrics.critical_shortages_count > 0 ? 'danger' : 'success',
          }}
          icon={AlertTriangle}
          onClick={() => onNavigate('inventory')}
          actionText="Inspect urgent"
        />

        <MetricCard
          title="Open Purchase Orders"
          value={metrics.active_orders_count}
          subtitle={`Committed: ${formatINR(metrics.total_committed_orders_cost)}`}
          badge={{
            text: `${metrics.recent_orders.filter((o) => o.status === 'pending_approval').length} awaiting approval`,
            variant: 'brand',
          }}
          icon={ClipboardList}
          onClick={() => onNavigate('orders')}
          actionText="Manage POs"
        />
      </div>

      {/* Stock Health Summary Bar */}
      <div className="bg-white border border-slate-200/90 rounded-xl p-5 shadow-xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Inventory Health Breakdown
            </h3>
            <p className="text-xs text-slate-500">
              Distribution across {total} managed catalog SKUs
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-medium">
            <span className="flex items-center gap-1.5 text-emerald-700">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
              Healthy: {healthy} ({healthyPct}%)
            </span>
            <span className="flex items-center gap-1.5 text-amber-700">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
              Reorder: {moderate} ({moderatePct}%)
            </span>
            <span className="flex items-center gap-1.5 text-rose-700">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
              Critical: {critical} ({criticalPct}%)
            </span>
          </div>
        </div>

        {/* Multi-segment progress bar */}
        <div className="h-2.5 w-full bg-slate-100 rounded-full overflow-hidden flex">
          <div
            style={{ width: `${healthyPct}%` }}
            className="bg-emerald-500 transition-all duration-300"
            title={`Healthy: ${healthyPct}%`}
          />
          <div
            style={{ width: `${moderatePct}%` }}
            className="bg-amber-400 transition-all duration-300"
            title={`Reorder needed: ${moderatePct}%`}
          />
          <div
            style={{ width: `${criticalPct}%` }}
            className="bg-rose-500 transition-all duration-300"
            title={`Critical stockout: ${criticalPct}%`}
          />
        </div>
      </div>

      {/* Main Grid: Restock Priorities & Recent Purchase Orders */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Restock Priorities Table (2 cols) */}
        <div className="lg:col-span-2 bg-white border border-slate-200/90 rounded-xl shadow-xs overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-200/80 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Restock Priorities</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Items ranked by runout urgency and days of coverage left
              </p>
            </div>
            <button
              onClick={() => onNavigate('inventory')}
              className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
            >
              <span>View all inventory</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold">
                <tr>
                  <th className="py-2.5 px-4">Product / SKU</th>
                  <th className="py-2.5 px-3 text-right">Current Stock</th>
                  <th className="py-2.5 px-3 text-right">Coverage Left</th>
                  <th className="py-2.5 px-3 text-right">Recommended Reorder</th>
                  <th className="py-2.5 px-4 text-center">Urgency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {metrics.critical_items.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-400">
                      No critical replenishment items detected. All stock levels healthy.
                    </td>
                  </tr>
                ) : (
                  metrics.critical_items.slice(0, 7).map((item) => (
                    <tr key={item.sku} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900">{item.name}</div>
                        <div className="text-[11px] font-mono text-slate-400">{item.sku}</div>
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-medium text-slate-800">
                        {item.current_stock}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span
                          className={`font-mono font-bold ${
                            item.days_of_stock_left <= item.min_supplier_lead_time_days
                              ? 'text-rose-600'
                              : 'text-amber-600'
                          }`}
                        >
                          {item.days_of_stock_left.toFixed(1)} days
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-semibold text-slate-900">
                        {item.gross_reorder_qty} units
                      </td>
                      <td className="py-3 px-4 text-center">
                        <StatusBadge
                          status={item.is_urgent ? 'urgent' : 'shortage'}
                          label={item.is_urgent ? 'Stockout Risk' : 'Low Stock'}
                        />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Purchase Orders & Activity (1 col) */}
        <div className="bg-white border border-slate-200/90 rounded-xl shadow-xs overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-200/80 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Recent Purchase Orders</h2>
              <p className="text-xs text-slate-500 mt-0.5">Live order states & commitments</p>
            </div>
            <button
              onClick={() => onNavigate('orders')}
              className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
            >
              <span>All orders</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="divide-y divide-slate-100 flex-1 overflow-y-auto max-h-[380px]">
            {metrics.recent_orders.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                No purchase orders created yet.
              </div>
            ) : (
              metrics.recent_orders.slice(0, 6).map((order) => (
                <div
                  key={order.order_id}
                  onClick={() => onSelectOrder(order.order_id)}
                  className="p-3.5 hover:bg-slate-50/70 transition-colors cursor-pointer space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-xs text-blue-700 hover:underline">
                      {order.order_id}
                    </span>
                    <StatusBadge status={order.status} />
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500 font-medium">
                      {order.items.length} {order.items.length === 1 ? 'item' : 'items'}
                    </span>
                    <span className="font-mono font-bold text-slate-900">
                      {formatINR(order.total_cost)}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-400 flex items-center gap-1">
                    <Clock className="w-3 h-3 text-slate-300" />
                    <span>{formatDate(order.created_at)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
