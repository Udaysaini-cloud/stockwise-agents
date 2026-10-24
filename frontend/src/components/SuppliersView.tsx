'use client';

import React, { useState } from 'react';
import {
  Truck,
  CheckCircle2,
  XCircle,
  Star,
  Clock,
  Package,
  Layers,
  ChevronDown,
  ChevronUp,
  Award,
  AlertCircle,
  MapPin,
} from 'lucide-react';
import { Supplier, SupplierComparisonResult } from '@/types';
import { formatINR } from '@/lib/format';
import { PageHeader } from '@/components/common/PageHeader';
import { EmptyState } from '@/components/common/EmptyState';

interface SuppliersViewProps {
  suppliers: Supplier[];
  comparisons: SupplierComparisonResult[];
  loading: boolean;
}

export const SuppliersView: React.FC<SuppliersViewProps> = ({
  suppliers,
  comparisons,
  loading,
}) => {
  const [activeTab, setActiveTab] = useState<'compare' | 'catalog'>('compare');
  const [selectedSku, setSelectedSku] = useState<string>('all');

  if (loading) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
        <div className="h-8 bg-slate-200 rounded-lg w-48 animate-pulse" />
        <div className="h-64 bg-white border border-slate-200 rounded-xl animate-pulse" />
      </div>
    );
  }

  const filteredComparisons =
    selectedSku === 'all'
      ? comparisons
      : comparisons.filter((c) => c.requirement.sku === selectedSku);

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <PageHeader
        title="Supplier Evaluation & Comparison"
        description="Multi-vendor competitive ranking based on unit prices (50%), lead times (25%), quality ratings (15%), and fulfillment delivery rates (10%)."
      >
        <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200/80">
          <button
            onClick={() => setActiveTab('compare')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === 'compare'
                ? 'bg-white text-slate-900 shadow-2xs border border-slate-200/60'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Shortage Comparison ({comparisons.length})
          </button>
          <button
            onClick={() => setActiveTab('catalog')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === 'catalog'
                ? 'bg-white text-slate-900 shadow-2xs border border-slate-200/60'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Registered Vendors ({suppliers.length})
          </button>
        </div>
      </PageHeader>

      {activeTab === 'compare' ? (
        /* Multi-Vendor Comparison for Shortage SKUs */
        <div className="space-y-6">
          {/* SKU Filter */}
          <div className="flex items-center justify-between bg-white border border-slate-200/90 rounded-xl p-3.5 shadow-xs">
            <span className="text-xs font-semibold text-slate-700">Filter By Shortage Product:</span>
            <select
              value={selectedSku}
              onChange={(e) => setSelectedSku(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-700 font-medium focus:outline-none focus:border-blue-500"
            >
              <option key="sku-all" value="all">
                All Shortage SKUs ({comparisons.length})
              </option>
              {comparisons.map((c) => (
                <option key={`sku-${c.requirement.sku}`} value={c.requirement.sku}>
                  {c.requirement.sku} — {c.requirement.name}
                </option>
              ))}
            </select>
          </div>

          {filteredComparisons.length === 0 ? (
            <EmptyState
              icon={Truck}
              title="No shortage comparisons available"
              description="Either all SKUs are adequately stocked or no active shortage requirements have been generated yet."
            />
          ) : (
            <div className="space-y-6">
              {filteredComparisons.map((comp) => {
                const req = comp.requirement;
                return (
                  <div
                    key={req.sku}
                    className="bg-white border border-slate-200/90 rounded-xl shadow-xs overflow-hidden"
                  >
                    {/* Item Requirement Summary Header */}
                    <div className="p-4 bg-slate-50/70 border-b border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-blue-700">
                            {req.sku}
                          </span>
                          <span className="text-slate-300">•</span>
                          <h2 className="text-sm font-bold text-slate-900">{req.name}</h2>
                          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-slate-200/80 text-slate-700">
                            {req.category}
                          </span>
                        </div>
                        <div className="text-xs text-slate-500 mt-1 flex flex-wrap items-center gap-3">
                          <span>
                            Current Stock:{' '}
                            <strong className="text-slate-800">{req.current_stock}</strong>
                          </span>
                          <span>•</span>
                          <span>
                            Deficit / Reorder:{' '}
                            <strong className="text-rose-600 font-mono">
                              {req.gross_reorder_qty} units
                            </strong>
                          </span>
                          <span>•</span>
                          <span>
                            Days Left:{' '}
                            <strong className="text-amber-600 font-mono">
                              {req.days_of_stock_left.toFixed(1)}d
                            </strong>
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Offers Comparison Table */}
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-slate-50/50 border-b border-slate-200 text-slate-500 font-semibold">
                          <tr>
                            <th className="py-2.5 px-4">Supplier</th>
                            <th className="py-2.5 px-3 text-right">Unit Price</th>
                            <th className="py-2.5 px-3 text-right">Lead Time</th>
                            <th className="py-2.5 px-3 text-right">MOQ</th>
                            <th className="py-2.5 px-3 text-right">Pack Size</th>
                            <th className="py-2.5 px-3 text-right">Feasible Qty</th>
                            <th className="py-2.5 px-3 text-right">Total Line Cost</th>
                            <th className="py-2.5 px-3 text-center">Availability</th>
                            <th className="py-2.5 px-4 text-right">Rank & Score</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {comp.ranked_offers.map((offer, idx) => {
                            const isRecommended = idx === 0 && offer.available;
                            return (
                              <tr
                                key={offer.supplier_id}
                                className={`transition-colors ${
                                  isRecommended
                                    ? 'bg-blue-50/30 font-medium'
                                    : !offer.available
                                    ? 'bg-slate-50/40 text-slate-400'
                                    : 'hover:bg-slate-50/60'
                                }`}
                              >
                                <td className="py-3 px-4">
                                  <div className="flex items-center gap-2">
                                    {isRecommended && (
                                      <Award className="w-4 h-4 text-blue-600 shrink-0" />
                                    )}
                                    <div>
                                      <div
                                        className={`font-semibold ${
                                          isRecommended ? 'text-blue-950 font-bold' : 'text-slate-900'
                                        }`}
                                      >
                                        {offer.supplier_name}
                                      </div>
                                      <div className="font-mono text-[10px] text-slate-400">
                                        {offer.supplier_id}
                                      </div>
                                    </div>
                                  </div>
                                </td>
                                <td className="py-3 px-3 text-right font-mono font-bold text-slate-900">
                                  {formatINR(offer.unit_cost)}
                                </td>
                                <td className="py-3 px-3 text-right font-mono">
                                  {offer.lead_time_days} days
                                </td>
                                <td className="py-3 px-3 text-right font-mono">{offer.moq}</td>
                                <td className="py-3 px-3 text-right font-mono">
                                  pack of {offer.pack_size}
                                </td>
                                <td className="py-3 px-3 text-right font-mono font-semibold text-slate-800">
                                  {offer.feasible_quantity} units
                                </td>
                                <td className="py-3 px-3 text-right font-mono font-bold text-slate-900">
                                  {formatINR(offer.item_total_cost)}
                                </td>
                                <td className="py-3 px-3 text-center">
                                  {offer.available ? (
                                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                                      <CheckCircle2 className="w-3 h-3" />
                                      Available
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200">
                                      <XCircle className="w-3 h-3" />
                                      Stockout
                                    </span>
                                  )}
                                </td>
                                <td className="py-3 px-4 text-right">
                                  <div className="flex items-center justify-end gap-1.5">
                                    {isRecommended && (
                                      <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-blue-600 text-white shadow-2xs">
                                        Best Pick
                                      </span>
                                    )}
                                    <span className="font-mono font-bold text-xs text-slate-800">
                                      {(offer.composite_score * 100).toFixed(0)}%
                                    </span>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : (
        /* Registered Suppliers Catalog View */
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {suppliers.map((s) => {
            const supplierId = s.id || s.supplier_id || 'SUP-000';
            const shortCode = supplierId.slice(-2);
            const catalogEntries = Object.entries(s.catalog || {});

            return (
              <div
                key={supplierId}
                className="bg-white border border-slate-200/90 rounded-xl p-5 shadow-xs space-y-4"
              >
                <div className="flex items-center justify-between border-b border-slate-100 pb-3.5">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-blue-50 border border-blue-200 flex items-center justify-center font-bold text-blue-700 text-xs font-mono">
                      {shortCode}
                    </div>
                    <div>
                      <h2 className="text-sm font-bold text-slate-900">{s.name}</h2>
                      <div className="flex items-center gap-2 text-[11px] text-slate-400">
                        <span className="font-mono">{supplierId}</span>
                        {s.location && (
                          <>
                            <span>•</span>
                            <span className="flex items-center gap-1">
                              <MapPin className="w-3 h-3" />
                              {s.location}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-[11px] text-slate-500">Catalog SKUs:</span>{' '}
                    <span className="text-xs font-mono font-bold text-slate-900">
                      {catalogEntries.length}
                    </span>
                  </div>
                </div>

                {/* Delivery fee & stats */}
                <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded-lg text-xs">
                  <div>
                    <span className="text-slate-400 block text-[11px]">Delivery Charge:</span>
                    <span className="font-mono font-bold text-slate-800">
                      {formatINR(s.delivery_charge)} flat fee
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px]">Delivery Method:</span>
                    <span className="font-medium text-slate-800">Direct Warehouse Dispatch</span>
                  </div>
                </div>

                {/* Catalog summary */}
                <div>
                  <h3 className="text-xs font-bold text-slate-700 mb-2 uppercase tracking-wider">
                    Offered Catalog Products:
                  </h3>
                  <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
                    {catalogEntries.map(([sku, item]) => (
                      <div
                        key={sku}
                        className="flex items-center justify-between p-2 rounded-lg bg-slate-50 border border-slate-200/60 text-xs"
                      >
                        <div>
                          <span className="font-mono font-bold text-blue-700">{sku}</span>
                          <div className="text-[11px] text-slate-500">
                            Lead time: {item.lead_time_days}d • MOQ: {item.moq} • Pack: {item.pack_size}
                          </div>
                        </div>
                        <div className="text-right">
                          <span className="font-mono font-bold text-slate-900">
                            {formatINR(item.unit_cost)}
                          </span>
                          <div>
                            {item.available ? (
                              <span className="text-[10px] text-emerald-600 font-medium">In Stock</span>
                            ) : (
                              <span className="text-[10px] text-rose-600 font-medium">Out of Stock</span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
