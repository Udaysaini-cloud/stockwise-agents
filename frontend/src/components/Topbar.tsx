import React from 'react';
import { Search, RefreshCw, Bell, ShieldCheck, CheckCircle2 } from 'lucide-react';

interface TopbarProps {
  currentTabTitle: string;
  categoryContext?: string;
  onRefresh: () => void;
  isLoading: boolean;
  isBackendHealthy: boolean;
  globalSearchTerm: string;
  onGlobalSearchChange: (val: string) => void;
}

export const Topbar: React.FC<TopbarProps> = ({
  currentTabTitle,
  categoryContext = 'Procurement Operations',
  onRefresh,
  isLoading,
  isBackendHealthy,
  globalSearchTerm,
  onGlobalSearchChange,
}) => {
  return (
    <header className="h-14 border-b border-slate-200/90 bg-white/90 backdrop-blur-xs px-6 flex items-center justify-between shrink-0 sticky top-0 z-20">
      {/* Breadcrumbs / Page context */}
      <div className="flex items-center gap-2 text-xs">
        <span className="text-slate-400 font-medium">{categoryContext}</span>
        <span className="text-slate-300">/</span>
        <span className="text-slate-800 font-bold capitalize">{currentTabTitle}</span>
      </div>

      {/* Global Search & Action cluster */}
      <div className="flex items-center gap-3">
        {/* Global Search Input */}
        <div className="relative w-64 md:w-80 hidden sm:block">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search inventory, orders, SKU..."
            value={globalSearchTerm}
            onChange={(e) => onGlobalSearchChange(e.target.value)}
            className="w-full bg-slate-50 hover:bg-slate-100/80 focus:bg-white border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
          />
        </div>

        {/* Sync / Refresh button */}
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="px-2.5 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 bg-white hover:bg-slate-50 border border-slate-200 text-xs font-medium flex items-center gap-1.5 shadow-2xs transition-colors"
          title="Sync with live backend database"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-slate-500 ${isLoading ? 'animate-spin' : ''}`} />
          <span className="hidden md:inline">Sync Data</span>
        </button>

        {/* Live Backend Connection Indicator */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-[11px] font-medium text-emerald-700">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="hidden sm:inline">Engine Live</span>
        </div>
      </div>
    </header>
  );
};
