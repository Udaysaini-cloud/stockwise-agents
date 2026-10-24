import React from 'react';

export type StatusVariant =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'simulated_placed'
  | 'rejected'
  | 'failed'
  | 'healthy'
  | 'shortage'
  | 'urgent';

interface StatusBadgeProps {
  status: string;
  label?: string;
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  size = 'sm',
}) => {
  const norm = status?.toLowerCase().replace(/\s+/g, '_');

  let style = 'bg-slate-100 text-slate-700 border-slate-200';
  let dotColor = 'bg-slate-400';
  let displayLabel = label || status;

  switch (norm) {
    case 'approved':
      style = 'bg-emerald-50 text-emerald-800 border-emerald-200';
      dotColor = 'bg-emerald-500';
      displayLabel = label || 'Approved';
      break;
    case 'simulated_placed':
      style = 'bg-blue-50 text-blue-800 border-blue-200';
      dotColor = 'bg-blue-500';
      displayLabel = label || 'Simulated Placed';
      break;
    case 'pending_approval':
      style = 'bg-amber-50 text-amber-800 border-amber-200';
      dotColor = 'bg-amber-500';
      displayLabel = label || 'Pending Approval';
      break;
    case 'draft':
      style = 'bg-slate-100 text-slate-700 border-slate-200';
      dotColor = 'bg-slate-400';
      displayLabel = label || 'Draft';
      break;
    case 'rejected':
      style = 'bg-rose-50 text-rose-800 border-rose-200';
      dotColor = 'bg-rose-500';
      displayLabel = label || 'Rejected';
      break;
    case 'failed':
      style = 'bg-rose-100 text-rose-900 border-rose-300';
      dotColor = 'bg-rose-600';
      displayLabel = label || 'Failed';
      break;
    case 'urgent':
      style = 'bg-rose-50 text-rose-700 border-rose-200';
      dotColor = 'bg-rose-500';
      displayLabel = label || 'Critical Shortage';
      break;
    case 'shortage':
      style = 'bg-amber-50 text-amber-700 border-amber-200';
      dotColor = 'bg-amber-500';
      displayLabel = label || 'Reorder Needed';
      break;
    case 'healthy':
      style = 'bg-emerald-50 text-emerald-700 border-emerald-200';
      dotColor = 'bg-emerald-500';
      displayLabel = label || 'Healthy Stock';
      break;
  }

  const sizeClasses =
    size === 'sm'
      ? 'text-[11px] px-2 py-0.5'
      : 'text-xs px-2.5 py-1';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border shadow-2xs whitespace-nowrap ${style} ${sizeClasses}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColor}`} />
      <span>{displayLabel}</span>
    </span>
  );
};
