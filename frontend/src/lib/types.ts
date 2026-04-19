export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema20: number | null;
  ema50: number | null;
  ema200: number | null;
}

export type Direction = 'BUY' | 'SELL' | 'HOLD';

export interface Signal {
  id: number;
  timestamp: number;
  direction: Direction;
  confidence: number;
  claude_direction: string | null;
  claude_confidence: number | null;
  gemini_direction: string | null;
  gemini_confidence: number | null;
  reasoning: string | null;
  sl_pips: number | null;
  tp_pips: number | null;
  created_at: number;
}

export interface Trade {
  id: number;
  pair: string;
  timeframe: string;
  signal_id: number;
  direction: 'BUY' | 'SELL';
  entry_price: number;
  sl_price: number;
  tp_price: number;
  lot_size: number;
  sl_pips: number;
  tp_pips: number;
  opened_at: number;
  closed_at: number | null;
  close_price: number | null;
  close_reason: string | null;
  pnl_pips: number | null;
  pnl_usd: number | null;
  status: 'open' | 'closed';
}

export interface EquityPoint {
  time: number;
  value: number;
}

export interface TradesResponse {
  open: Trade[];
  closed: Trade[];
  equity_curve: EquityPoint[];
}

export interface Stats {
  pair: string;
  updated_at: number;
  trade_count: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
  total_pnl_pips: number;
  total_pnl_usd: number;
  avg_win_pips: number | null;
  avg_loss_pips: number | null;
  profit_factor: number | null;
  max_drawdown_usd: number;
}

export interface StatusResponse {
  pair: string;
  balance: number;
  signal: {
    direction: Direction;
    confidence: number;
    reasoning: string | null;
    timestamp: number;
  } | null;
}
