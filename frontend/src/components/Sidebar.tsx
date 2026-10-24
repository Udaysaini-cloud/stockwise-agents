import React from 'react';
import {
  LayoutDashboard,
  Boxes,
  Truck,
  Calculator,
  ClipboardList,
  MessageSquareCode,
  ShieldCheck,
  Zap,
  ChevronRight,
  Sparkles,
} from 'lucide-react';

export type NavTab = 'overview' | 'inventory' | 'suppliers' | 'planner' | 'orders' | 'agent';

interface SidebarProps {
  currentTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  shortagesCount?: number;
  pendingOrdersCount?: number;
  isBackendHealthy?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  shortagesCount = 0,
  pendingOrdersCount = 0,
  isBackendHealthy = true,
}) => {
  const navItems = [
    {
      id: 'overview' as NavTab,
      label: 'Overview',
      icon: LayoutDashboard,
      badge: null,
    },
    {
      id: 'inventory' as NavTab,
      label: 'Inventory',
      icon: Boxes,
      badge: shortagesCount > 0 ? shortagesCount : null,
      badgeVariant: 'danger',
    },
    {
      id: 'suppliers' as NavTab,
      label: 'Suppliers',
      icon: Truck,
      badge: null,
    },
    {
      id: 'planner' as NavTab,
      label: 'Procurement Planner',
      icon: Calculator,
      badge: null,
    },
    {
      id: 'orders' as NavTab,
      label: 'Purchase Orders',
      icon: ClipboardList,
      badge: pendingOrdersCount > 0 ? pendingOrdersCount : null,
      badgeVariant: 'warning',
    },
    {
      id: 'agent' as NavTab,
      label: 'Agent Workspace',
      icon: MessageSquareCode,
      badge: 'Fetch.ai',
      badgeVariant: 'brand',
    },
  ];

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col justify-between shrink-0 select-none text-slate-300">
      <div className="flex flex-col">
        {/* Brand header */}
        <div className="h-16 flex items-center px-5 border-b border-slate-800/80 gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-sm tracking-wider shadow-sm shadow-blue-500/20">
            <Zap className="w-4 h-4 fill-white" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-white text-sm tracking-tight">StockWise</span>
              <span className="text-[9px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                B2B SaaS
              </span>
            </div>
            <div className="text-[11px] text-slate-400 truncate">Intelligent Procurement</div>
          </div>
        </div>

        {/* Section title */}
        <div className="px-5 pt-5 pb-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
          Platform Workspace
        </div>

        {/* Navigation items */}
        <nav className="px-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-blue-600 text-white font-semibold shadow-xs'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800/70'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon
                    className={`w-4 h-4 shrink-0 ${
                      isActive ? 'text-white' : 'text-slate-400'
                    }`}
                  />
                  <span className="truncate">{item.label}</span>
                </div>

                {item.badge !== null && (
                  <span
                    className={`text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded-full shrink-0 ml-2 ${
                      isActive
                        ? 'bg-blue-700/80 text-white'
                        : item.badgeVariant === 'danger'
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                        : item.badgeVariant === 'warning'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer / Safety Badge & Backend Connection */}
      <div className="p-4 border-t border-slate-800/80 space-y-3">
        {/* Guardrail badge */}
        <div className="bg-slate-800/60 rounded-lg p-2.5 border border-slate-700/50 flex items-start gap-2.5">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
          <div className="text-[11px] leading-tight text-slate-400">
            <span className="text-slate-200 font-semibold block">Safety Guardrails Active</span>
            <span className="text-[10px]">Strict INR caps • Simulated dispatch</span>
          </div>
        </div>

        {/* Connection status indicator */}
        <div className="flex items-center justify-between px-1 text-[11px]">
          <span className="text-slate-400 text-[10px] font-medium">Engine API (FastAPI)</span>
          <div className="flex items-center gap-1.5">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isBackendHealthy ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
              }`}
            />
            <span
              className={`text-[10px] font-mono ${
                isBackendHealthy ? 'text-emerald-400' : 'text-rose-400'
              }`}
            >
              {isBackendHealthy ? 'Live: 8000' : 'Disconnected'}
            </span>
          </div>
        </div>

        {/* User profile */}
        <div className="flex items-center gap-2.5 pt-1 px-1 border-t border-slate-800/60">
          <div className="w-7 h-7 rounded-full bg-slate-700 text-slate-200 flex items-center justify-center text-xs font-bold border border-slate-600">
            SM
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold text-slate-200 leading-tight truncate">
              Store Manager
            </div>
            <div className="text-[10px] text-slate-400 truncate">Mumbai Central Hub</div>
          </div>
        </div>
      </div>
    </aside>
  );
};
