'use client';

import type { Direction, StatusResponse } from '@/lib/types';

const BADGE: Record<Direction, string> = {
  BUY: 'bg-green-900 text-green-400 border border-green-700',
  SELL: 'bg-red-900 text-red-400 border border-red-700',
  HOLD: 'bg-slate-800 text-slate-400 border border-slate-600',
};

interface Props {
  data: StatusResponse | undefined;
}

export function StatusBar({ data }: Props) {
  const signal = data?.signal ?? null;

  return (
    <div className="flex items-center gap-5 px-6 py-3 bg-slate-900 border-b border-slate-800 flex-wrap">
      <span className="font-mono text-lg font-bold tracking-widest text-white">
        {data?.pair ?? 'EURUSD'}
      </span>

      {signal ? (
        <>
          <span className={`px-3 py-1 rounded font-bold text-sm ${BADGE[signal.direction]}`}>
            {signal.direction}
          </span>
          <span className="text-slate-400 text-sm">
            Conf:{' '}
            <span className="text-white font-mono font-semibold">
              {(signal.confidence * 100).toFixed(0)}%
            </span>
          </span>
          <span className="text-slate-500 text-xs font-mono">
            {new Date(signal.timestamp * 1000).toLocaleString()}
          </span>
        </>
      ) : (
        <span className="text-slate-500 text-sm">No signal yet</span>
      )}

      <div className="ml-auto text-right">
        <span className="text-slate-400 text-sm">Balance </span>
        <span className="font-mono text-white font-bold text-lg">
          ${(data?.balance ?? 0).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </span>
      </div>
    </div>
  );
}
