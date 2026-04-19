'use client';

import type { Trade } from '@/lib/types';

function fmt(n: number | null | undefined, decimals = 2, prefix = '') {
  if (n == null) return '—';
  const formatted = n.toFixed(decimals);
  return `${prefix}${formatted}`;
}

function ts(epoch: number | null | undefined) {
  if (epoch == null) return '—';
  return new Date(epoch * 1000).toLocaleString();
}

function PnLCell({ pnl }: { pnl: number | null }) {
  if (pnl == null) return <td className="px-3 py-2 text-slate-500">—</td>;
  return (
    <td className={`px-3 py-2 font-mono ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
      {pnl >= 0 ? '+' : ''}
      {pnl.toFixed(2)}
    </td>
  );
}

function TradeRow({ trade }: { trade: Trade }) {
  const isOpen = trade.status === 'open';
  return (
    <tr className="border-b border-slate-800 hover:bg-slate-800/40 transition-colors">
      <td className="px-3 py-2 text-slate-500 text-xs font-mono">{trade.id}</td>
      <td className="px-3 py-2">
        <span
          className={`px-2 py-0.5 rounded text-xs font-bold border ${
            trade.direction === 'BUY'
              ? 'bg-green-900 text-green-400 border-green-700'
              : 'bg-red-900 text-red-400 border-red-700'
          }`}
        >
          {trade.direction}
        </span>
      </td>
      <td className="px-3 py-2 font-mono text-sm text-slate-200">
        {fmt(trade.entry_price, 5)}
      </td>
      <td className="px-3 py-2 font-mono text-sm text-red-400">{fmt(trade.sl_price, 5)}</td>
      <td className="px-3 py-2 font-mono text-sm text-green-400">{fmt(trade.tp_price, 5)}</td>
      <td className="px-3 py-2 font-mono text-sm text-slate-400">
        {trade.close_price != null ? fmt(trade.close_price, 5) : '—'}
      </td>
      <PnLCell pnl={trade.pnl_usd} />
      <td className="px-3 py-2 font-mono text-xs text-slate-500">{fmt(trade.pnl_pips, 1)}</td>
      <td className="px-3 py-2 text-xs text-slate-500">{ts(trade.opened_at)}</td>
      <td className="px-3 py-2 text-xs text-slate-500">{isOpen ? '—' : ts(trade.closed_at)}</td>
      <td className="px-3 py-2 text-xs text-slate-400">{trade.close_reason ?? '—'}</td>
      <td className="px-3 py-2">
        <span
          className={`px-2 py-0.5 rounded text-xs font-semibold ${
            isOpen ? 'bg-blue-900 text-blue-300' : 'bg-slate-800 text-slate-400'
          }`}
        >
          {trade.status}
        </span>
      </td>
    </tr>
  );
}

interface Props {
  open: Trade[];
  closed: Trade[];
}

const HEADERS = [
  'ID', 'Dir', 'Entry', 'SL', 'TP', 'Close', 'P&L ($)', 'P&L (pip)',
  'Opened', 'Closed', 'Reason', 'Status',
];

export function TradeLog({ open, closed }: Props) {
  const trades = [...open, ...[...closed].reverse()];

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 pt-3 pb-2 border-b border-slate-800 flex items-center gap-3">
        <span className="text-slate-300 text-sm font-semibold uppercase tracking-wider">
          Trade Log
        </span>
        <span className="text-xs text-slate-500">
          {open.length} open · {closed.length} closed
        </span>
      </div>
      <div className="flex-1 overflow-auto">
        {trades.length === 0 ? (
          <div className="flex items-center justify-center h-24 text-slate-500 text-sm">
            No trades yet
          </div>
        ) : (
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 bg-slate-900 text-slate-400 text-xs uppercase">
              <tr>
                {HEADERS.map((h) => (
                  <th key={h} className="px-3 py-2 text-left font-medium whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <TradeRow key={t.id} trade={t} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
