'use client';

import type { Stats } from '@/lib/types';

interface Props {
  data: Stats | undefined;
}

function Stat({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive?: boolean;
}) {
  const color =
    positive === undefined
      ? 'text-white'
      : positive
      ? 'text-green-400'
      : 'text-red-400';

  return (
    <div className="bg-slate-800 rounded-lg p-3">
      <div className="text-slate-400 text-xs mb-1">{label}</div>
      <div className={`font-mono font-bold text-base ${color}`}>{value}</div>
    </div>
  );
}

export function StatsPanel({ data }: Props) {
  if (!data) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        No stats yet
      </div>
    );
  }

  const pnlPositive = data.total_pnl_usd >= 0;

  return (
    <div className="p-4 h-full flex flex-col gap-3">
      <h2 className="text-slate-300 text-sm font-semibold uppercase tracking-wider">
        Performance
      </h2>
      <div className="grid grid-cols-2 gap-3 flex-1">
        <Stat
          label="Win Rate"
          value={`${(data.win_rate * 100).toFixed(1)}%`}
          positive={data.win_rate >= 0.5}
        />
        <Stat label="Trades" value={String(data.trade_count)} />
        <Stat
          label="Total P&L"
          value={`$${data.total_pnl_usd.toFixed(2)}`}
          positive={pnlPositive}
        />
        <Stat
          label="P&L (pips)"
          value={`${data.total_pnl_pips.toFixed(1)}`}
          positive={data.total_pnl_pips >= 0}
        />
        <Stat
          label="Max Drawdown"
          value={`$${Math.abs(data.max_drawdown_usd).toFixed(2)}`}
          positive={false}
        />
        <Stat
          label="Profit Factor"
          value={data.profit_factor != null ? data.profit_factor.toFixed(2) : '—'}
          positive={data.profit_factor != null ? data.profit_factor >= 1 : undefined}
        />
        <Stat label="Wins" value={`${data.win_count}`} positive={true} />
        <Stat label="Losses" value={`${data.loss_count}`} positive={false} />
      </div>
    </div>
  );
}
