'use client';

import useSWR from 'swr';
import dynamic from 'next/dynamic';

import { fetcher } from '@/lib/api';
import type { StatusResponse, Candle, Signal, TradesResponse, Stats } from '@/lib/types';
import { StatusBar } from '@/components/StatusBar';
import { StatsPanel } from '@/components/StatsPanel';
import { SignalFeed } from '@/components/SignalFeed';
import { TradeLog } from '@/components/TradeLog';

// Chart components use browser-only APIs — disable SSR
const PriceChart = dynamic(
  () => import('@/components/PriceChart').then((m) => m.PriceChart),
  { ssr: false, loading: () => <ChartSkeleton /> }
);
const EquityChart = dynamic(
  () => import('@/components/EquityChart').then((m) => m.EquityChart),
  { ssr: false, loading: () => <ChartSkeleton /> }
);

function ChartSkeleton() {
  return (
    <div className="w-full h-full flex items-center justify-center bg-slate-900 rounded-lg">
      <span className="text-slate-500 text-sm animate-pulse">Loading chart…</span>
    </div>
  );
}

const PAIR = 'EURUSD';
const TIMEFRAME = '15m';
const REFRESH = 30_000; // 30 s

export default function Dashboard() {
  const { data: status } = useSWR<StatusResponse>(
    `/api/status`,
    fetcher,
    { refreshInterval: REFRESH }
  );
  const { data: candles } = useSWR<Candle[]>(
    `/api/candles?pair=${PAIR}&timeframe=${TIMEFRAME}&n=200`,
    fetcher,
    { refreshInterval: REFRESH }
  );
  const { data: signals } = useSWR<Signal[]>(
    `/api/signals?pair=${PAIR}&timeframe=${TIMEFRAME}&n=50`,
    fetcher,
    { refreshInterval: REFRESH }
  );
  const { data: trades } = useSWR<TradesResponse>(
    `/api/trades?pair=${PAIR}`,
    fetcher,
    { refreshInterval: REFRESH }
  );
  const { data: stats } = useSWR<Stats>(
    `/api/stats?pair=${PAIR}`,
    fetcher,
    { refreshInterval: REFRESH }
  );

  const initialBalance =
    typeof process.env.NEXT_PUBLIC_PAPER_BALANCE === 'string'
      ? parseFloat(process.env.NEXT_PUBLIC_PAPER_BALANCE)
      : 10000;

  return (
    <div className="flex flex-col h-screen bg-slate-950 overflow-hidden">
      {/* Top bar */}
      <StatusBar data={status} />

      {/* Main content */}
      <div className="flex flex-1 min-h-0">
        {/* Left column — charts */}
        <div className="flex flex-col flex-1 min-w-0 divide-y divide-slate-800">
          {/* Price chart */}
          <div className="flex-[3] min-h-0 bg-slate-900">
            <PriceChart candles={candles ?? []} />
          </div>

          {/* Equity curve */}
          <div className="flex-[2] min-h-0 bg-slate-900">
            <EquityChart
              data={trades?.equity_curve ?? []}
              initialBalance={initialBalance}
            />
          </div>
        </div>

        {/* Right column — signals + stats */}
        <div className="w-80 shrink-0 border-l border-slate-800 flex flex-col divide-y divide-slate-800">
          <div className="flex-1 min-h-0 overflow-hidden">
            <SignalFeed data={signals} />
          </div>
          <div className="h-72 shrink-0 overflow-hidden bg-slate-900">
            <StatsPanel data={stats} />
          </div>
        </div>
      </div>

      {/* Trade log */}
      <div className="h-64 shrink-0 border-t border-slate-800 bg-slate-900 overflow-hidden">
        <TradeLog
          open={trades?.open ?? []}
          closed={trades?.closed ?? []}
        />
      </div>
    </div>
  );
}
