'use client';

import { useState } from 'react';
import type { Signal, Direction } from '@/lib/types';

const BADGE: Record<Direction, string> = {
  BUY: 'bg-green-900 text-green-400 border border-green-700',
  SELL: 'bg-red-900 text-red-400 border border-red-700',
  HOLD: 'bg-slate-800 text-slate-400 border border-slate-600',
};

function SignalRow({ signal }: { signal: Signal }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="border-b border-slate-800 last:border-0 cursor-pointer hover:bg-slate-800/50 transition-colors"
      onClick={() => setExpanded((e) => !e)}
    >
      <div className="flex items-center gap-3 px-4 py-2">
        <span className="text-slate-500 text-xs font-mono w-24 shrink-0">
          {new Date(signal.timestamp * 1000).toLocaleTimeString()}
        </span>
        <span className={`px-2 py-0.5 rounded text-xs font-bold ${BADGE[signal.direction]}`}>
          {signal.direction}
        </span>
        <span className="text-slate-400 text-xs font-mono">
          {(signal.confidence * 100).toFixed(0)}%
        </span>
        <div className="ml-auto flex gap-2 text-xs text-slate-500">
          {signal.claude_direction && (
            <span>
              C:{' '}
              <span
                className={
                  signal.claude_direction === 'BUY'
                    ? 'text-green-400'
                    : signal.claude_direction === 'SELL'
                    ? 'text-red-400'
                    : 'text-slate-400'
                }
              >
                {signal.claude_direction}
              </span>
            </span>
          )}
          {signal.gemini_direction && (
            <span>
              G:{' '}
              <span
                className={
                  signal.gemini_direction === 'BUY'
                    ? 'text-green-400'
                    : signal.gemini_direction === 'SELL'
                    ? 'text-red-400'
                    : 'text-slate-400'
                }
              >
                {signal.gemini_direction}
              </span>
            </span>
          )}
        </div>
      </div>
      {expanded && signal.reasoning && (
        <div className="px-4 pb-3 text-xs text-slate-400 leading-relaxed bg-slate-900/50">
          {signal.reasoning}
        </div>
      )}
    </div>
  );
}

interface Props {
  data: Signal[] | undefined;
}

export function SignalFeed({ data }: Props) {
  const signals = data ? [...data].reverse().slice(0, 20) : [];

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 pt-3 pb-2 border-b border-slate-800">
        <span className="text-slate-300 text-sm font-semibold uppercase tracking-wider">
          Signal Feed
        </span>
        <span className="ml-2 text-slate-500 text-xs">(tap to expand)</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {signals.length === 0 ? (
          <div className="flex items-center justify-center h-full text-slate-500 text-sm">
            No signals yet
          </div>
        ) : (
          signals.map((s) => <SignalRow key={s.id} signal={s} />)
        )}
      </div>
    </div>
  );
}
