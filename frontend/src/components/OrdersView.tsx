'use client';

import React, { useState } from 'react';
import {
  ClipboardList,
  CheckCircle2,
  XCircle,
  Truck,
  History,
  AlertTriangle,
  FileText,
  ShieldCheck,
  Clock,
  RefreshCw,
  Search,
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { PurchaseOrder, OrderAuditEvent } from '@/types';
import { api } from '@/lib/api';
import { formatINR, formatDate } from '@/lib/format';
import { PageHeader } from '@/components/common/PageHeader';
import { StatusBadge } from '@/components/common/StatusBadge';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { EmptyState } from '@/components/common/EmptyState';

interface OrdersViewProps {
  orders: PurchaseOrder[];
  selectedOrderId: string | null;
  onSelectOrder: (orderId: string | null) => void;
  onRefreshOrders: () => void;
}

export const OrdersView: React.FC<OrdersViewProps> = ({
  orders,
  selectedOrderId,
  onSelectOrder,
  onRefreshOrders,
}) => {
  const [orderDetails, setOrderDetails] = useState<{
    order: PurchaseOrder;
    audit_trail: OrderAuditEvent[];
  } | null>(null);
  const [loadingDetails, setLoadingDetails] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');

  // Dialog States
  const [showApproveDialog, setShowApproveDialog] = useState<boolean>(false);
  const [showRejectDialog, setShowRejectDialog] = useState<boolean>(false);
  const [showPlacementDialog, setShowPlacementDialog] = useState<boolean>(false);
  const [rejectReason, setRejectReason] = useState<string>('');

  // Fetch full order details whenever selectedOrderId changes
  React.useEffect(() => {
    if (!selectedOrderId) {
      setOrderDetails(null);
      return;
    }

    let active = true;
    setLoadingDetails(true);
    setActionMessage(null);

    api
      .getOrderDetails(selectedOrderId)
      .then((data) => {
        if (active) setOrderDetails(data);
      })
      .catch((err) => {
        if (active) setActionMessage({ type: 'error', text: err.message });
      })
      .finally(() => {
        if (active) setLoadingDetails(false);
      });

    return () => {
      active = false;
    };
  }, [selectedOrderId]);

  // Handle Approve Order
  const handleApprove = async () => {
    if (!selectedOrderId) return;
    try {
      setActionLoading(true);
      setActionMessage(null);
      const res = await api.approveOrder(selectedOrderId, 'store_manager');
      setOrderDetails({ order: res.order, audit_trail: res.audit_trail });
      setActionMessage({ type: 'success', text: res.message });
      setShowApproveDialog(false);
      onRefreshOrders();
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.message });
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Reject Order
  const handleReject = async () => {
    if (!selectedOrderId) return;
    try {
      setActionLoading(true);
      setActionMessage(null);
      const res = await api.rejectOrder(
        selectedOrderId,
        rejectReason || 'Order rejected by store manager during procurement review',
        'store_manager'
      );
      setOrderDetails({ order: res.order, audit_trail: res.audit_trail });
      setActionMessage({ type: 'success', text: res.message });
      setShowRejectDialog(false);
      setRejectReason('');
      onRefreshOrders();
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.message });
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Simulate Placement
  const handleSimulatePlacement = async () => {
    if (!selectedOrderId) return;
    try {
      setActionLoading(true);
      setActionMessage(null);
      const res = await api.simulatePlacement(selectedOrderId, 'procurement_agent');
      setOrderDetails({ order: res.order, audit_trail: res.audit_trail });
      setActionMessage({ type: 'success', text: res.message });
      setShowPlacementDialog(false);
      onRefreshOrders();
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.message });
    } finally {
      setActionLoading(false);
    }
  };

  // Filter orders by search
  const filteredOrders = orders.filter(
    (o) =>
      o.order_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      o.request_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      o.status.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <PageHeader
        title="Purchase Orders & Audit Ledger"
        description="Comprehensive purchase order governance with strict state machine enforcement (draft &rarr; pending_approval &rarr; approved &rarr; simulated_placed)."
        badge={`${orders.length} Records`}
      >
        <button
          onClick={onRefreshOrders}
          className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-2xs flex items-center gap-1.5"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh Ledger</span>
        </button>
      </PageHeader>

      {/* Global Action Message Banner */}
      {actionMessage && (
        <div
          className={`p-3.5 rounded-xl border text-xs flex items-center justify-between ${
            actionMessage.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          <div className="flex items-center gap-2">
            {actionMessage.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            )}
            <span>{actionMessage.text}</span>
          </div>
          <button
            onClick={() => setActionMessage(null)}
            className="font-bold ml-2 underline text-[11px]"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Master-Detail Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Side: Order Master List (5 cols) */}
        <div className="lg:col-span-5 bg-white border border-slate-200/90 rounded-xl shadow-xs overflow-hidden flex flex-col">
          {/* List Header & Search */}
          <div className="p-3.5 border-b border-slate-200/80 bg-slate-50/50 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-700">
                Order Ledger
              </span>
              <span className="text-xs font-mono font-medium text-slate-500">
                {filteredOrders.length} showing
              </span>
            </div>
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search by PO ID or state..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-white border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          {/* Orders Scrollable List */}
          <div className="divide-y divide-slate-100 max-h-[640px] overflow-y-auto">
            {filteredOrders.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                No purchase orders found matching &quot;{searchTerm}&quot;
              </div>
            ) : (
              filteredOrders.map((order) => {
                const isSelected = order.order_id === selectedOrderId;
                return (
                  <div
                    key={order.order_id}
                    onClick={() => onSelectOrder(order.order_id)}
                    className={`p-4 transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-blue-50/60 border-l-4 border-l-blue-600'
                        : 'hover:bg-slate-50/70'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-bold text-xs text-slate-900">
                        {order.order_id}
                      </span>
                      <StatusBadge status={order.status} />
                    </div>

                    <div className="flex items-center justify-between text-xs mt-2">
                      <span className="text-slate-500">
                        {order.items.length} {order.items.length === 1 ? 'item' : 'items'} •{' '}
                        {formatDate(order.created_at)}
                      </span>
                      <span className="font-mono font-bold text-slate-900">
                        {formatINR(order.total_cost)}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Side: Order Detail Panel (7 cols) */}
        <div className="lg:col-span-7 bg-white border border-slate-200/90 rounded-xl shadow-xs overflow-hidden">
          {!selectedOrderId ? (
            <div className="p-16 text-center">
              <EmptyState
                icon={ClipboardList}
                title="No purchase order selected"
                description="Select any purchase order from the ledger list on the left to review line items, cost details, and inspect the complete audit trail."
              />
            </div>
          ) : loadingDetails ? (
            <div className="p-8 space-y-4">
              <div className="h-6 bg-slate-200 rounded w-48 animate-pulse" />
              <div className="h-24 bg-slate-100 rounded-lg animate-pulse" />
              <div className="h-48 bg-slate-100 rounded-lg animate-pulse" />
            </div>
          ) : orderDetails ? (
            <div className="space-y-6 p-6">
              {/* Order Detail Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-100">
                <div>
                  <div className="flex items-center gap-2.5">
                    <h2 className="text-base font-bold font-mono text-slate-900">
                      {orderDetails.order.order_id}
                    </h2>
                    <StatusBadge status={orderDetails.order.status} size="md" />
                  </div>
                  <div className="text-xs text-slate-500 mt-1 flex items-center gap-2">
                    <span>Created: {formatDate(orderDetails.order.created_at)}</span>
                    <span>•</span>
                    <span className="font-mono text-[11px] text-slate-400">
                      Req: {orderDetails.order.request_id}
                    </span>
                  </div>
                </div>

                {/* State Machine Action Buttons */}
                <div className="flex items-center gap-2">
                  {orderDetails.order.status === 'pending_approval' && (
                    <>
                      <button
                        onClick={() => setShowRejectDialog(true)}
                        disabled={actionLoading}
                        className="px-3 py-1.5 rounded-lg border border-rose-200 bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold transition-colors"
                      >
                        Reject
                      </button>
                      <button
                        onClick={() => setShowApproveDialog(true)}
                        disabled={actionLoading}
                        className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Approve Order</span>
                      </button>
                    </>
                  )}

                  {orderDetails.order.status === 'approved' && (
                    <button
                      onClick={() => setShowPlacementDialog(true)}
                      disabled={actionLoading}
                      className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5"
                    >
                      <Truck className="w-3.5 h-3.5" />
                      <span>Simulate Placement</span>
                    </button>
                  )}

                  {orderDetails.order.status === 'simulated_placed' && (
                    <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-50 border border-blue-200 text-xs font-semibold text-blue-700">
                      <Truck className="w-3.5 h-3.5" />
                      <span>Simulated Dispatched</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Financial Metrics Summary */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
                  <span className="text-[11px] text-slate-500 block">Subtotal (Items):</span>
                  <span className="text-xs font-bold font-mono text-slate-900">
                    {formatINR(orderDetails.order.subtotal)}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
                  <span className="text-[11px] text-slate-500 block">Delivery Fees:</span>
                  <span className="text-xs font-bold font-mono text-slate-900">
                    {formatINR(orderDetails.order.total_delivery_charges)}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
                  <span className="text-[11px] text-slate-500 block">Total Landed:</span>
                  <span className="text-xs font-bold font-mono text-blue-700">
                    {formatINR(orderDetails.order.total_cost)}
                  </span>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200/70">
                  <span className="text-[11px] text-slate-500 block">Remaining Budget:</span>
                  <span className="text-xs font-bold font-mono text-emerald-700">
                    {formatINR(orderDetails.order.remaining_budget)}
                  </span>
                </div>
              </div>

              {/* Order Line Items */}
              <div>
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2.5">
                  Order Line Items ({orderDetails.order.items.length})
                </h3>
                <div className="border border-slate-200 rounded-lg overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold">
                      <tr>
                        <th className="py-2.5 px-3">Product / SKU</th>
                        <th className="py-2.5 px-3">Supplier</th>
                        <th className="py-2.5 px-3 text-right">Qty</th>
                        <th className="py-2.5 px-3 text-right">Unit Price</th>
                        <th className="py-2.5 px-3 text-right">Line Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {orderDetails.order.items.map((item) => (
                        <tr key={item.sku} className="hover:bg-slate-50/60">
                          <td className="py-2.5 px-3">
                            <div className="font-semibold text-slate-900">{item.product_name}</div>
                            <div className="font-mono text-[10px] text-slate-400">{item.sku}</div>
                          </td>
                          <td className="py-2.5 px-3 font-medium text-slate-800">
                            {item.supplier_name}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono font-bold text-slate-900">
                            {item.ordered_quantity}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-slate-600">
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

              {/* Audit Timeline */}
              <div>
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                  <History className="w-3.5 h-3.5 text-slate-500" />
                  <span>State Audit Timeline ({orderDetails.audit_trail.length})</span>
                </h3>
                <div className="border border-slate-200 rounded-lg p-3.5 bg-slate-50/50 space-y-3">
                  {orderDetails.audit_trail.map((evt, idx) => (
                    <div key={evt.event_id || idx} className="flex items-start gap-3 text-xs">
                      <div className="w-2 h-2 rounded-full bg-blue-600 shrink-0 mt-1.5" />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900">
                            {evt.from_state} &rarr; {evt.to_state}
                          </span>
                          <span className="text-[10px] text-slate-400 font-mono">
                            by {evt.actor}
                          </span>
                        </div>
                        <p className="text-slate-600 text-[11px] mt-0.5">{evt.reason}</p>
                        <span className="text-[10px] text-slate-400 block mt-0.5">
                          {formatDate(evt.timestamp)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* Confirmation Dialogs */}
      <ConfirmDialog
        isOpen={showApproveDialog}
        title="Approve Purchase Order"
        description={`Are you sure you want to approve purchase order ${selectedOrderId}? This authorizes committing ${orderDetails ? formatINR(orderDetails.order.total_cost) : ''} to suppliers.`}
        confirmLabel="Authorize & Approve"
        variant="success"
        isLoading={actionLoading}
        onConfirm={handleApprove}
        onCancel={() => setShowApproveDialog(false)}
      />

      <ConfirmDialog
        isOpen={showRejectDialog}
        title="Reject Purchase Order"
        description={`Provide a specific rejection reason for the permanent audit trail.`}
        confirmLabel="Reject Order"
        variant="danger"
        isLoading={actionLoading}
        onConfirm={handleReject}
        onCancel={() => setShowRejectDialog(false)}
      >
        <div className="pt-2">
          <label className="text-xs font-semibold text-slate-700 block mb-1">
            Rejection Justification:
          </label>
          <textarea
            rows={2}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="e.g. Budget re-allocation required for urgent dairy restock"
            className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-blue-500"
          />
        </div>
      </ConfirmDialog>

      <ConfirmDialog
        isOpen={showPlacementDialog}
        title="Simulate Supplier Placement"
        description="This action marks the approved purchase order as simulated_placed in the system. Note: This is an internal sandbox simulation and does NOT trigger real financial transactions or live carrier pickups."
        confirmLabel="Confirm Simulated Placement"
        variant="primary"
        isLoading={actionLoading}
        onConfirm={handleSimulatePlacement}
        onCancel={() => setShowPlacementDialog(false)}
      />
    </div>
  );
};
