export function formatINR(amount: number | string | undefined | null): string {
  if (amount === undefined || amount === null) return '₹0.00';
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '₹0.00';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(num);
}

export function formatDate(dateString: string): string {
  if (!dateString) return '—';
  try {
    const d = new Date(dateString);
    return d.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateString;
  }
}

export function getStatusBadgeClasses(status: string): string {
  switch (status?.toLowerCase()) {
    case 'approved':
      return 'bg-emerald-50 text-emerald-700 border-emerald-200 ring-1 ring-emerald-600/10';
    case 'simulated_placed':
      return 'bg-blue-50 text-blue-700 border-blue-200 ring-1 ring-blue-600/10';
    case 'pending_approval':
      return 'bg-amber-50 text-amber-700 border-amber-200 ring-1 ring-amber-600/10';
    case 'draft':
      return 'bg-slate-100 text-slate-700 border-slate-200 ring-1 ring-slate-600/10';
    case 'rejected':
      return 'bg-rose-50 text-rose-700 border-rose-200 ring-1 ring-rose-600/10';
    case 'failed':
      return 'bg-red-50 text-red-700 border-red-200 ring-1 ring-red-600/10';
    default:
      return 'bg-slate-100 text-slate-700 border-slate-200 ring-1 ring-slate-600/10';
  }
}
