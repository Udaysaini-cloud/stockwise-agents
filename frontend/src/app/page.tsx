'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar, NavTab } from '@/components/Sidebar';
import { Topbar } from '@/components/Topbar';
import { OverviewView } from '@/components/OverviewView';
import { InventoryView } from '@/components/InventoryView';
import { SuppliersView } from '@/components/SuppliersView';
import { PlannerView } from '@/components/PlannerView';
import { OrdersView } from '@/components/OrdersView';
import { AgentChatView } from '@/components/AgentChatView';
import { api } from '@/lib/api';
import {
  OverviewMetrics,
  StockRequirement,
  Supplier,
  SupplierComparisonResult,
  PurchaseOrder,
} from '@/types';
import { AlertCircle } from 'lucide-react';

export default function DashboardPage() {
  const [currentTab, setCurrentTab] = useState<NavTab>('overview');
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [globalSearchTerm, setGlobalSearchTerm] = useState<string>('');

  // Core Data States
  const [overviewMetrics, setOverviewMetrics] = useState<OverviewMetrics | null>(null);
  const [inventoryRequirements, setInventoryRequirements] = useState<StockRequirement[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [comparisons, setComparisons] = useState<SupplierComparisonResult[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const [overviewData, invData, supData, compData, ordersData] = await Promise.all([
        api.getOverview(),
        api.getInventory(),
        api.getSuppliers(),
        api.getSupplierComparison(),
        api.getOrders(),
      ]);

      setOverviewMetrics(overviewData);
      setInventoryRequirements(invData);
      setSuppliers(supData);
      setComparisons(compData);
      setOrders(ordersData);
    } catch (err: any) {
      console.error('Failed to load dashboard data:', err);
      setErrorMsg(
        err.message ||
          'Cannot connect to StockWise backend API. Make sure python agents/api_server.py is running on port 8000.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectOrderAndNavigate = (orderId: string) => {
    setSelectedOrderId(orderId);
    setCurrentTab('orders');
  };

  const handlePlanGenerated = (newOrder: PurchaseOrder) => {
    setOrders((prev) => [newOrder, ...prev.filter((o) => o.order_id !== newOrder.order_id)]);
    // Refresh overview metrics in background
    api.getOverview().then(setOverviewMetrics).catch(console.error);
  };

  const tabTitles: Record<NavTab, string> = {
    overview: 'Procurement Overview',
    inventory: 'Inventory & Stockouts',
    suppliers: 'Suppliers & Evaluation',
    planner: 'Procurement Planner',
    orders: 'Purchase Orders & Audit',
    agent: 'Agent Workspace',
  };

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 overflow-hidden font-sans">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        shortagesCount={overviewMetrics?.shortages_count || 0}
        pendingOrdersCount={
          orders.filter((o) => o.status === 'pending_approval').length
        }
        isBackendHealthy={!errorMsg}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-slate-50">
        {/* Top Minimal Bar */}
        <Topbar
          currentTabTitle={tabTitles[currentTab]}
          categoryContext="StockWise Enterprise"
          onRefresh={loadData}
          isLoading={loading}
          isBackendHealthy={!errorMsg}
          globalSearchTerm={globalSearchTerm}
          onGlobalSearchChange={setGlobalSearchTerm}
        />

        {/* Global Connection Error Banner */}
        {errorMsg && (
          <div className="bg-rose-50 border-b border-rose-200 px-6 py-3 text-xs text-rose-700 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{errorMsg}</span>
            </div>
            <button
              onClick={loadData}
              className="underline hover:text-rose-900 font-semibold ml-4 shrink-0"
            >
              Retry Connection
            </button>
          </div>
        )}

        {/* Page Tab Content Area */}
        <main className="flex-1 overflow-y-auto">
          {currentTab === 'overview' && (
            <OverviewView
              metrics={overviewMetrics}
              loading={loading}
              onNavigate={setCurrentTab}
              onSelectOrder={handleSelectOrderAndNavigate}
            />
          )}

          {currentTab === 'inventory' && (
            <InventoryView
              requirements={inventoryRequirements}
              loading={loading}
              onSelectSkuForComparison={(sku) => {
                setCurrentTab('suppliers');
              }}
            />
          )}

          {currentTab === 'suppliers' && (
            <SuppliersView
              suppliers={suppliers}
              comparisons={comparisons}
              loading={loading}
            />
          )}

          {currentTab === 'planner' && (
            <PlannerView
              onPlanGenerated={handlePlanGenerated}
              onNavigateToOrder={handleSelectOrderAndNavigate}
            />
          )}

          {currentTab === 'orders' && (
            <OrdersView
              orders={orders}
              selectedOrderId={selectedOrderId}
              onSelectOrder={setSelectedOrderId}
              onRefreshOrders={loadData}
            />
          )}

          {currentTab === 'agent' && <AgentChatView />}
        </main>
      </div>
    </div>
  );
}
