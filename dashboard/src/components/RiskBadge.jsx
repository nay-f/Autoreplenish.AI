import React from 'react';

export function RiskBadge({ status }) {
  const configs = {
    STOCKOUT_RISK: {
      label: 'Stockout Risk',
      bg: 'bg-rose-500/10',
      border: 'border-rose-500/30',
      text: 'text-rose-400'
    },
    OVERSTOCK_RISK: {
      label: 'Overstock Risk',
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/30',
      text: 'text-amber-400'
    },
    HEALTHY: {
      label: 'Healthy',
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/30',
      text: 'text-emerald-400'
    },
    APPROVED: {
      label: 'Approved',
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/30',
      text: 'text-emerald-400'
    },
    EDITED: {
      label: 'Edited by Store',
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/30',
      text: 'text-blue-400'
    },
    REJECTED: {
      label: 'Rejected',
      bg: 'bg-rose-500/10',
      border: 'border-rose-500/30',
      text: 'text-rose-400'
    },
    SUCCESS: {
      label: 'SAP PR Created',
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/30',
      text: 'text-emerald-400'
    },
    FAILED_SAP: {
      label: 'SAP Error',
      bg: 'bg-rose-500/10',
      border: 'border-rose-500/30',
      text: 'text-rose-400'
    },
    PENDING: {
      label: 'Pending Approval',
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/30',
      text: 'text-amber-400'
    }
  };

  const current = configs[status] || {
    label: status,
    bg: 'bg-slate-800',
    border: 'border-slate-700',
    text: 'text-slate-300'
  };

  return (
    <span className={`inline-flex items-center text-xs font-semibold px-2.5 py-1 rounded-md border ${current.bg} ${current.border} ${current.text}`}>
      {current.label}
    </span>
  );
}
