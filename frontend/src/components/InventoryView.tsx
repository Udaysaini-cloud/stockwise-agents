'use client';

import React, { useState, useMemo } from 'react';
import {
  Search,
  Filter,
  AlertTriangle,
  CheckCircle2,
  Info,
  Boxes,
  ArrowUpDown,
  ExternalLink,
  ChevronDown,
  Layers,
  X,
} from 'lucide-react';
import { StockRequirement } from '@/types';
import { PageHeader } from '@/components/common/PageHeader';
import { StatusBadge } from '@/components/common/StatusBadge';
import { EmptyState } from '@/components/common/EmptyState';

interface InventoryViewProps {
  requirements: StockRequirement[];
  loading: boolean;
  onSelectSkuForComparison?: (sku: string) => void;
}

type SortField =
  | 'sku'
  | 'name'
  | 'category'
  | 'current_stock'
  | 'days_of_stock_left'
  | 'gross_reorder_qty';

export const InventoryView: React.FC<InventoryViewProps> = ({
  requirements,
  loading,
  onSelectSkuForComparison,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [urgencyFilter, setUrgencyFilter] = useState<string>('all');
  const [sortField, setSortField] = useState<SortField>('days_of_stock_left');
  const [sortAsc, setSortAsc] = useState<boolean>(true);
  const [inspectItem, setInspectItem] = useState<StockRequirement | null>(null);

  // Extract unique categories safely
  const categories = useMemo(() => {
    const set = new Set<string>();
    requirements.forEach((r) => {
      if (r.category) set.add(r.category);
    });
    return Array.from(set).sort();
  }, [requirements]);

  // Filtered and sorted items
  const filteredAndSorted = useMemo(() => {
    const list = requirements.filter((item) => {
      const matchSearch =
        item.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.sku.toLowerCase().includes(searchTerm.toLowerCase());
      const matchCategory =
        selectedCategory === 'all' || item.category === selectedCategory;
      const matchUrgency =
        urgencyFilter === 'all' ||
        (urgencyFilter === 'urgent' && item.is_urgent) ||
        (urgencyFilter === 'shortage' && item.gross_reorder_qty > 0) ||
        (urgencyFilter === 'healthy' && item.gross_reorder_qty === 0);
      return matchSearch && matchCategory && matchUrgency;
    });

    return list.sort((a, b) => {
      let valA: any = a[sortField];
      let valB: any = b[sortField];

      if (typeof valA === 'string') {
        const cmp = valA.localeCompare(valB);
        return sortAsc ? cmp : -cmp;
      }
      return sortAsc ? valA - valB : valB - valA;
    });
  }, [requirements, searchTerm, selectedCategory, urgencyFilter, sortField, sortAsc]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  if (loading) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
        <div className="h-8 bg-slate-200 rounded-lg w-48 animate-pulse" />
        <div className="h-12 bg-white border border-slate-200 rounded-xl animate-pulse" />
        <div className="h-96 bg-white border border-slate-200 rounded-xl animate-pulse" />
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <PageHeader
        title="Inventory & Stockout Management"
        description="Comprehensive SKU inventory status computing daily burn rate, vendor lead times, safety stocks, and replenishment deficits."
        badge={`${requirements.length} SKUs`}
      />

      {/* Filter & Search Bar */}
      <div className="bg-white border border-slate-200/90 rounded-xl p-4 shadow-xs flex flex-col md:flex-row items-center justify-between gap-3.5">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by SKU or product name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-all"
          />
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          {/* Category Dropdown */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-slate-400 font-medium hidden sm:inline">Category:</span>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700 font-medium focus:outline-none focus:border-blue-500"
            >
              <option key="cat-all" value="all">
                All Categories
              </option>
              {categories.map((cat) => (
                <option key={`cat-${cat}`} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-slate-400 font-medium hidden sm:inline">Status:</span>
            <select
              value={urgencyFilter}
              onChange={(e) => setUrgencyFilter(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700 font-medium focus:outline-none focus:border-blue-500"
            >
              <option key="urgency-all" value="all">
                All Health States
              </option>
              <option key="urgency-urgent" value="urgent">
                Critical Shortage (&le; Lead Time)
              </option>
              <option key="urgency-shortage" value="shortage">
                Reorder Required
              </option>
              <option key="urgency-healthy" value="healthy">
                Healthy Stock Level
              </option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Inventory Table */}
      <div className="bg-white border border-slate-200/90 rounded-xl shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold select-none">
              <tr>
                <th
                  onClick={() => toggleSort('sku')}
                  className="py-3 px-4 cursor-pointer hover:text-slate-900 transition-colors"
                >
                  <div className="flex items-center gap-1">
                    <span>SKU / Product</span>
                    <ArrowUpDown className="w-3 h-3 text-slate-400" />
                  </div>
                </th>
                <th
                  onClick={() => toggleSort('category')}
                  className="py-3 px-3 cursor-pointer hover:text-slate-900 transition-colors"
                >
                  <div className="flex items-center gap-1">
                    <span>Category</span>
                    <ArrowUpDown className="w-3 h-3 text-slate-400" />
                  </div>
                </th>
                <th
                  onClick={() => toggleSort('current_stock')}
                  className="py-3 px-3 text-right cursor-pointer hover:text-slate-900 transition-colors"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Current Stock</span>
                    <ArrowUpDown className="w-3 h-3 text-slate-400" />
                  </div>
                </th>
                <th className="py-3 px-3 text-right">Avg Daily Sales</th>
                <th className="py-3 px-3 text-right">Safety Stock</th>
                <th className="py-3 px-3 text-right">Outstanding POs</th>
                <th
                  onClick={() => toggleSort('days_of_stock_left')}
                  className="py-3 px-3 text-right cursor-pointer hover:text-slate-900 transition-colors"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Days Left</span>
                    <ArrowUpDown className="w-3 h-3 text-slate-400" />
                  </div>
                </th>
                <th
                  onClick={() => toggleSort('gross_reorder_qty')}
                  className="py-3 px-3 text-right cursor-pointer hover:text-slate-900 transition-colors"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Rec. Reorder</span>
                    <ArrowUpDown className="w-3 h-3 text-slate-400" />
                  </div>
                </th>
                <th className="py-3 px-4 text-center">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredAndSorted.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center">
                    <EmptyState
                      icon={Boxes}
                      title="No products match filter"
                      description="Try adjusting your search query, category selection, or stock status."
                    />
                  </td>
                </tr>
              ) : (
                filteredAndSorted.map((item) => {
                  const isStockout = item.days_of_stock_left <= item.min_supplier_lead_time_days;
                  return (
                    <tr
                      key={item.sku}
                      className="hover:bg-slate-50/80 transition-colors group"
                    >
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-slate-900">{item.name}</div>
                        <div className="font-mono text-[11px] text-slate-400 mt-0.5">
                          {item.sku}
                        </div>
                      </td>
                      <td className="py-3.5 px-3">
                        <span className="text-[11px] font-medium px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200/70">
                          {item.category}
                        </span>
                      </td>
                      <td className="py-3.5 px-3 text-right font-mono font-bold text-slate-900">
                        {item.current_stock}
                      </td>
                      <td className="py-3.5 px-3 text-right font-mono text-slate-600">
                        {item.average_daily_sales}/day
                      </td>
                      <td className="py-3.5 px-3 text-right font-mono text-slate-500">
                        {item.safety_stock}
                      </td>
                      <td className="py-3.5 px-3 text-right font-mono text-slate-500">
                        {item.outstanding_orders > 0 ? (
                          <span className="text-blue-600 font-semibold">
                            +{item.outstanding_orders}
                          </span>
                        ) : (
                          '0'
                        )}
                      </td>
                      <td className="py-3.5 px-3 text-right">
                        <span
                          className={`font-mono font-bold ${
                            isStockout
                              ? 'text-rose-600'
                              : item.gross_reorder_qty > 0
                              ? 'text-amber-600'
                              : 'text-emerald-600'
                          }`}
                        >
                          {item.days_of_stock_left.toFixed(1)}d
                        </span>
                      </td>
                      <td className="py-3.5 px-3 text-right font-mono font-bold">
                        {item.gross_reorder_qty > 0 ? (
                          <span className="text-slate-900">
                            {item.gross_reorder_qty}
                          </span>
                        ) : (
                          <span className="text-slate-400 font-normal">0</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <StatusBadge
                          status={
                            item.is_urgent
                              ? 'urgent'
                              : item.gross_reorder_qty > 0
                              ? 'shortage'
                              : 'healthy'
                          }
                          label={
                            item.is_urgent
                              ? 'Critical Shortage'
                              : item.gross_reorder_qty > 0
                              ? 'Reorder Needed'
                              : 'Healthy Stock'
                          }
                        />
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => setInspectItem(item)}
                            className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                            title="Inspect calculation details"
                          >
                            <Info className="w-4 h-4" />
                          </button>
                          {onSelectSkuForComparison && item.gross_reorder_qty > 0 && (
                            <button
                              onClick={() => onSelectSkuForComparison(item.sku)}
                              className="px-2 py-1 rounded bg-blue-50 hover:bg-blue-100 text-blue-700 text-[11px] font-semibold border border-blue-200 transition-colors"
                              title="Compare suppliers for this item"
                            >
                              Quotes
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Reorder Calculation Details Drawer / Modal */}
      {inspectItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-start justify-between pb-3 border-b border-slate-100">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                  Replenishment Breakdown
                </span>
                <h3 className="text-sm font-bold text-slate-900">{inspectItem.name}</h3>
                <span className="text-xs font-mono text-blue-600">{inspectItem.sku}</span>
              </div>
              <button
                onClick={() => setInspectItem(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-md"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200/70">
                <div>
                  <span className="text-slate-500 block">Current Warehouse Stock:</span>
                  <span className="font-mono font-bold text-slate-900 text-sm">
                    {inspectItem.current_stock} units
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">Average Daily Burn Rate:</span>
                  <span className="font-mono font-bold text-slate-900 text-sm">
                    {inspectItem.average_daily_sales} units / day
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">Safety Stock Floor:</span>
                  <span className="font-mono font-bold text-slate-900 text-sm">
                    {inspectItem.safety_stock} units
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">Target Coverage Window:</span>
                  <span className="font-mono font-bold text-slate-900 text-sm">
                    {inspectItem.target_stock_cover_days} days
                  </span>
                </div>
              </div>

              <div className="p-3 bg-blue-50/60 rounded-lg border border-blue-200/70 space-y-1.5">
                <span className="font-bold text-blue-900 block">Calculation Logic:</span>
                <p className="text-slate-600 leading-relaxed text-[11px]">
                  <strong>Target Stock:</strong> (Daily Sales &times; Target Cover Days) + Safety Stock ={' '}
                  <span className="font-mono font-bold">{inspectItem.target_stock} units</span>
                </p>
                <p className="text-slate-600 leading-relaxed text-[11px]">
                  <strong>Effective Stock:</strong> Current Stock + Outstanding Orders ={' '}
                  <span className="font-mono font-bold">{inspectItem.effective_stock} units</span>
                </p>
                <p className="text-slate-600 leading-relaxed text-[11px]">
                  <strong>Gross Reorder:</strong> max(0, Target Stock &minus; Effective Stock) ={' '}
                  <span className="font-mono font-bold text-blue-700">
                    {inspectItem.gross_reorder_qty} units
                  </span>
                </p>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setInspectItem(null)}
                className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
