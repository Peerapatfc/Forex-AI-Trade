'use client';

import { useEffect, useRef } from 'react';
import {
  createChart,
  ColorType,
  type IChartApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import type { Candle } from '@/lib/types';

interface Props {
  candles: Candle[];
}

export function PriceChart({ candles }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

    const container = containerRef.current;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: '#0f172a' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: {
        vertLine: { color: '#475569' },
        horzLine: { color: '#475569' },
      },
      width: container.clientWidth,
      height: container.clientHeight || 360,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#334155',
      },
      rightPriceScale: { borderColor: '#334155' },
    });
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    candleSeries.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    // EMA 20 — amber
    const ema20 = candles.filter((c) => c.ema20 != null);
    if (ema20.length > 0) {
      const s = chart.addLineSeries({ color: '#f59e0b', lineWidth: 1, priceLineVisible: false });
      s.setData(ema20.map((c) => ({ time: c.time as UTCTimestamp, value: c.ema20! })));
    }

    // EMA 50 — blue
    const ema50 = candles.filter((c) => c.ema50 != null);
    if (ema50.length > 0) {
      const s = chart.addLineSeries({ color: '#3b82f6', lineWidth: 1, priceLineVisible: false });
      s.setData(ema50.map((c) => ({ time: c.time as UTCTimestamp, value: c.ema50! })));
    }

    // EMA 200 — purple
    const ema200 = candles.filter((c) => c.ema200 != null);
    if (ema200.length > 0) {
      const s = chart.addLineSeries({ color: '#a855f7', lineWidth: 1, priceLineVisible: false });
      s.setData(ema200.map((c) => ({ time: c.time as UTCTimestamp, value: c.ema200! })));
    }

    chart.timeScale().fitContent();

    const observer = new ResizeObserver(() => {
      if (container) {
        chart.applyOptions({ width: container.clientWidth });
      }
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [candles]);

  return (
    <div className="w-full h-full flex flex-col">
      <div className="flex items-center gap-4 px-4 pt-3 pb-2">
        <span className="text-slate-300 text-sm font-semibold uppercase tracking-wider">
          Price Chart
        </span>
        <span className="flex items-center gap-1 text-xs text-amber-400">
          <span className="w-6 h-0.5 bg-amber-400 inline-block" /> EMA20
        </span>
        <span className="flex items-center gap-1 text-xs text-blue-400">
          <span className="w-6 h-0.5 bg-blue-400 inline-block" /> EMA50
        </span>
        <span className="flex items-center gap-1 text-xs text-purple-400">
          <span className="w-6 h-0.5 bg-purple-400 inline-block" /> EMA200
        </span>
      </div>
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}
