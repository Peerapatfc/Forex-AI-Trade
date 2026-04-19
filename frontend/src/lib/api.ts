import type {
  Candle,
  Signal,
  TradesResponse,
  Stats,
  StatusResponse,
} from './types';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const fetcher = (url: string) =>
  fetch(`${BASE_URL}${url}`, { cache: 'no-store' }).then((r) => {
    if (!r.ok) throw new Error(`API ${r.status}`);
    return r.json();
  });

export const api = {
  status: () => get<StatusResponse>('/api/status'),
  candles: (pair = 'EURUSD', timeframe = '15m', n = 200) =>
    get<Candle[]>(`/api/candles?pair=${pair}&timeframe=${timeframe}&n=${n}`),
  signals: (pair = 'EURUSD', timeframe = '15m', n = 50) =>
    get<Signal[]>(`/api/signals?pair=${pair}&timeframe=${timeframe}&n=${n}`),
  trades: (pair = 'EURUSD') =>
    get<TradesResponse>(`/api/trades?pair=${pair}`),
  stats: (pair = 'EURUSD') =>
    get<Stats>(`/api/stats?pair=${pair}`),
};
