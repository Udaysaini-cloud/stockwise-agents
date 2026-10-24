'use client';

import React, { useState } from 'react';
import {
  Calculator,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  Package,
  ArrowRight,
  TrendingUp,
  FileCheck2,
  ExternalLink,
  Coins,
} from 'lucide-react';
import { PurchaseOrder } from '@/types';
import { api } from '@/lib/api';
import { formatINR } from '@/lib/format';
import { PageHeader } from '@/components/common/PageHeader';
import { StatusBadge } from '@/components/common/StatusBadge';

interface PlannerViewProps {
  onPlanGenerated: (po: PurchaseOrder) => void;
  onNavigateToOrder: (orderId: string) => void;
}

export const PlannerView: React.FC<PlannerViewProps> = ({
  onPlanGenerated,
  onNavigateToOrder,
}) => {
  const [budgetInput, setBudgetInput] = useState<string>('25000');
  const [queryNotes, setQueryNotes] = useState<string>('Replenish critical stockouts for weekend sales');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lastGeneratedPlan, setLastGeneratedPlan] = useState<PurchaseOrder | null>(null);

  const budgetPresets = [10000, 20000, 25000, 50000];

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    const budgetNum = parseFloat(budgetInput);
    if (isNaN(budgetNum) || budgetNum <= 0) {
      setErrorMsg('Please enter a valid positive budget amount in INR (₹).');
      return;
    }

    try {
      setIsGenerating(true);
      const res = await api.createPlan(budgetNum, queryNotes);
      setLastGeneratedPlan(res.order);
      onPlanGenerated(res.order);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to generate procurement plan.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <PageHeader
        title="Procurement Optimizer & Knapsack Planner"
        description="Deterministic integer optimization solving multi-vendor minimum order quantities (MOQ), pack sizes, delivery fees, and strict budget ceilings."
      />

      {/* Input Form Card */}
      <div className="bg-white border border-slate-200/90 rounded-xl p-6 shadow-xs">
        <form onSubmit={handleGenerate} className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Budget Input & Presets */}
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Authorized Budget Cap (INR ₹) <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-mono text-sm font-bold">
                  ₹
                </span>
                <input
                  type="number"
                  step="500"
                  min="1000"
                  value={budgetInput}
                  onChange={(e) => setBudgetInput(e.target.value)}
                  placeholder="25000"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-2 text-sm font-mono font-bold text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-all"
                  required
                />
              </div>

              {/* Preset buttons */}
              <div className="flex items-center gap-1.5 pt-1">
                <span className="text-[11px] text-slate-400">Presets:</span>
                {budgetPresets.map((preset) => (
                  <button
                    key={preset}
                    type="button"
                    onClick={() => setBudgetInput(preset.toString())}
                    className={`px-2 py-0.5 rounded text-[11px] font-mono font-medium transition-colors border ${
                      budgetInput === preset.toString()
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    ₹{(preset / 1000).toFixed(0)}k
                  </button>
                ))}
              </div>
            </div>

            {/* Request Context Notes */}
            <div className="md:col-span-2 space-y-2">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Operational Procurement Context (Optional)
              </label>
              <input
                type="text"
                value={queryNotes}
                onChange={(e) => setQueryNotes(e.target.value)}
                placeholder="e.g. Prioritize high-margin electronics accessories before festival rush"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-all"
              />
              <p className="text-[11px] text-slate-500 leading-normal">
                Notes are logged into the permanent audit trail attached to the created Purchase Order.
              </p>
            </div>
          </div>

          {/* Error Message */}
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Action Row */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-slate-100">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <span>Created plan enters <strong>pending_approval</strong> state. Never auto-places.</span>
            </div>

            <button
              type="submit"
              disabled={isGenerating}
              className={`px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-xs transition-all flex items-center justify-center gap-2 ${
                isGenerating ? 'opacity-70 cursor-not-allowed' : ''
              }`}
            >
              {isGenerating ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Solving Mathematical Knapsack...</span>
                </>
              ) : (
                <>
                  <Calculator className="w-4 h-4" />
                  <span>Calculate optimal plan</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Generated Plan Review Card */}
      {lastGeneratedPlan && (
        <div className="bg-white border border-slate-200/90 rounded-xl shadow-xs overflow-hidden space-y-4 animate-in fade-in duration-200">
          {/* Plan Header */}
          <div className="p-5 bg-slate-50/70 border-b border-slate-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="font-mono text-xs font-bold text-blue-700">
                  {lastGeneratedPlan.order_id}
                </span>
                <StatusBadge status={lastGeneratedPlan.status} />
                <span className="text-xs text-slate-400 font-mono">
                  Req: {lastGeneratedPlan.request_id}
                </span>
              </div>
              <h2 className="text-sm font-bold text-slate-900 mt-1">
                Optimized Procurement Plan Generated
              </h2>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => onNavigateToOrder(lastGeneratedPlan.order_id)}
                className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-colors"
              >
                <span>Review & Approve PO</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Budget & Cost Summary Breakdown */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 px-6 pt-2">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
              <span className="text-[11px] text-slate-500 font-medium block">Authorized Budget:</span>
              <span className="text-sm font-bold font-mono text-slate-900">
                {formatINR(lastGeneratedPlan.budget)}
              </span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
              <span className="text-[11px] text-slate-500 font-medium block">Total Landed Cost:</span>
              <span className="text-sm font-bold font-mono text-blue-700">
                {formatINR(lastGeneratedPlan.total_cost)}
              </span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
              <span className="text-[11px] text-slate-500 font-medium block">Remaining Balance:</span>
              <span className="text-sm font-bold font-mono text-emerald-700">
                {formatINR(lastGeneratedPlan.remaining_budget)}
              </span>
            </div>
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
              <span className="text-[11px] text-slate-500 font-medium block">Supplier Delivery Fees:</span>
              <span className="text-sm font-bold font-mono text-slate-700">
                {formatINR(lastGeneratedPlan.total_delivery_charges)}
              </span>
            </div>
          </div>

          {/* Allocated Line Items Table */}
          <div className="px-6 py-2">
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2.5">
              Allocated Replenishment Items ({lastGeneratedPlan.items.length})
            </h3>
            <div className="border border-slate-200 rounded-lg overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                  <tr>
                    <th className="py-2.5 px-3">Product / SKU</th>
                    <th className="py-2.5 px-3">Supplier</th>
                    <th className="py-2.5 px-3 text-right">Pack Size & MOQ</th>
                    <th className="py-2.5 px-3 text-right">Ordered Units</th>
                    <th className="py-2.5 px-3 text-right">Unit Cost</th>
                    <th className="py-2.5 px-3 text-right">Line Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {lastGeneratedPlan.items.map((item) => (
                    <tr key={item.sku} className="hover:bg-slate-50/60">
                      <td className="py-2.5 px-3">
                        <div className="font-semibold text-slate-900">{item.product_name}</div>
                        <div className="font-mono text-[10px] text-slate-400">{item.sku}</div>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="font-medium text-slate-800">{item.supplier_name}</span>
                        <div className="font-mono text-[10px] text-slate-400">{item.supplier_id}</div>
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-600">
                        pack of {item.pack_size} (MOQ {item.moq})
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono font-bold text-slate-900">
                        {item.ordered_quantity}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-slate-700">
                        {formatINR(item.unit_cost)}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono font-bold text-slate-900">
                        {formatINR(item.line_total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Deferred Items Section (if any) */}
          {lastGeneratedPlan.deferred_items && lastGeneratedPlan.deferred_items.length > 0 && (
            <div className="px-6 pb-6">
              <h3 className="text-xs font-bold text-rose-700 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5" />
                <span>Deferred Products ({lastGeneratedPlan.deferred_items.length})</span>
              </h3>
              <div className="space-y-1.5">
                {lastGeneratedPlan.deferred_items.map((def) => (
                  <div
                    key={def.sku}
                    className="p-3 rounded-lg bg-rose-50/60 border border-rose-200/70 flex items-center justify-between text-xs"
                  >
                    <div>
                      <span className="font-mono font-bold text-rose-900">{def.sku}</span>
                      <span className="text-rose-700 ml-2 font-medium">{def.product_name}</span>
                      <div className="text-[11px] text-rose-600 mt-0.5">{def.reason}</div>
                    </div>
                    <div className="text-right font-mono text-xs text-rose-800">
                      Needed: {def.needed_quantity} units
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
