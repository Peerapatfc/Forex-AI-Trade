'use client';

import { useEffect, useRef } from 'react';
import {
  createChart,
  ColorType,
  type IChartApi,
  type UTCTimestamp,
} from 'lightweight-charts';
import type { EquityPoint } from '@/lib/types';

interface Props {
  data: EquityPoint[];
  initialBalance: number;
}

export function EquityChart({ data, initialBalance }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

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
      height: container.clientHeight || 200,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#334155',
      },
      rightPriceScale: { borderColor: '#334155' },
    });
    chartRef.current = chart;

    const series = chart.addAreaSeries({
      lineColor: '#22c55e',
      topColor: 'rgba(34, 197, 94, 0.2)',
      bottomColor: 'rgba(34, 197, 94, 0.0)',
      lineWidth: 2,
      priceLineVisible: false,
    });

    if (data.length > 0) {
      series.setData(
        data.map((p) => ({ time: p.time as UTCTimestamp, value: p.value }))
      );
      chart.timeScale().fitContent();
    } else {
      // No trades yet — show flat line at initial balance
      const now = Math.floor(Date.now() / 1000) as UTCTimestamp;
      series.setData([{ time: now, value: initialBalance }]);
    }

    const observer = new ResizeObserver(() => {
      if (container) chart.applyOptions({ width: container.clientWidth });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [data, initialBalance]);

  return (
    <div className="w-full h-full flex flex-col">
      <div className="px-4 pt-3 pb-2">
        <span className="text-slate-300 text-sm font-semibold uppercase tracking-wider">
          Equity Curve
        </span>
      </div>
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}
