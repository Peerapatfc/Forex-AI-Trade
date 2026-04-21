'use client';

import { useState } from 'react';
import type { DbError, FileLogLine, LogsResponse } from '@/lib/types';
import { fetcher } from '@/lib/api';
import useSWR from 'swr';

function ts(epoch: number | null | undefined) {
  if (epoch == null) return '—';
  return new Date(epoch * 1000).toLocaleString();
}

const DB_ERROR_HEADERS = ['Time', 'Pair', 'TF', 'Provider', 'Error'];

function DbErrorTable({ errors }: { errors: DbError[] }) {
  if (errors.length === 0) {
    return (
      <div className="flex items-center justify-center h-16 text-slate-500 text-sm">
        No DB errors
      </div>
    );
  }
  return (
    <div className="overflow-auto max-h-40">
      <table className="w-full text-xs border-collapse">
        <thead className="sticky top-0 bg-slate-900 text-slate-400 uppercase">
          <tr>
            {DB_ERROR_HEADERS.map((h) => (
              <th key={h} className="px-3 py-1.5 text-left font-medium whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {errors.map((e, i) => (
            <tr
              key={i}
              className="border-b border-slate-800 hover:bg-slate-800/40 transition-colors"
            >
              <td className="px-3 py-1.5 font-mono text-slate-400 whitespace-nowrap">
                {ts(e.timestamp)}
              </td>
              <td className="px-3 py-1.5 text-slate-300">{e.pair ?? '—'}</td>
              <td className="px-3 py-1.5 text-slate-400">{e.timeframe ?? '—'}</td>
              <td className="px-3 py-1.5 text-slate-400">{e.provider ?? '—'}</td>
              <td className="px-3 py-1.5 text-red-400 font-mono break-all">
                {e.error_msg ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FileLogPane({ lines }: { lines: FileLogLine[] }) {
  if (lines.length === 0) {
    return (
      <div className="flex items-center justify-center h-16 text-slate-500 text-sm">
        No log file found
      </div>
    );
  }
  return (
    <pre className="flex-1 overflow-auto text-xs font-mono text-slate-300 bg-slate-950 rounded p-3 leading-relaxed whitespace-pre-wrap break-all max-h-56">
      {lines.map((l, i) => (
        <span key={i} className="block">
          {l.line}
        </span>
      ))}
    </pre>
  );
}

export function LogViewer() {
  const [refreshKey, setRefreshKey] = useState(0);

  const { data, error, isLoading } = useSWR<LogsResponse>(
    ['/api/logs', refreshKey],
    fetcher,
    { refreshInterval: 30000 }
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 pt-3 pb-2 border-b border-slate-800 flex items-center gap-3 shrink-0">
        <span className="text-slate-300 text-sm font-semibold uppercase tracking-wider">
          System Logs
        </span>
        {data && (
          <span className="text-xs text-slate-500">
            {data.file_logs.length} lines · {data.db_errors.length} DB errors
          </span>
        )}
        <button
          onClick={() => setRefreshKey((k) => k + 1)}
          className="ml-auto px-3 py-1 text-xs rounded bg-slate-700 text-slate-200 hover:bg-slate-600 transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-hidden flex flex-col divide-y divide-slate-800">
        {isLoading && (
          <div className="flex items-center justify-center flex-1 text-slate-500 text-sm animate-pulse">
            Loading logs…
          </div>
        )}
        {error && (
          <div className="flex items-center justify-center flex-1 text-red-400 text-sm">
            Failed to load logs
          </div>
        )}
        {data && (
          <>
            {/* DB Errors section */}
            <div className="shrink-0">
              <div className="px-4 py-1.5 bg-slate-900/60 text-xs text-slate-500 uppercase tracking-wider font-medium">
                DB Fetch Errors
              </div>
              <DbErrorTable errors={data.db_errors} />
            </div>

            {/* File log section */}
            <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
              <div className="px-4 py-1.5 bg-slate-900/60 text-xs text-slate-500 uppercase tracking-wider font-medium shrink-0">
                File Log (last {data.file_logs.length} lines)
              </div>
              <div className="flex-1 overflow-auto p-2">
                <FileLogPane lines={data.file_logs} />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
