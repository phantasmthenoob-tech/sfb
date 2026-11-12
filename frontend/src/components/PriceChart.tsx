import { useMemo } from "react";
import { money, simDate } from "../lib/format";
import type { MarketBar } from "../types";

interface Props {
  bars: MarketBar[];
  height?: number;
}

const WIDTH = 760;
const PAD_LEFT = 8;
const PAD_RIGHT = 74;
const PAD_TOP = 18;
const PAD_BOTTOM = 28;

export function PriceChart({ bars, height = 240 }: Props) {
  const geometry = useMemo(() => {
    if (bars.length < 2) return null;
    const closes = bars.map((bar) => bar.close);
    const rawMin = Math.min(...bars.map((bar) => bar.low), ...closes);
    const rawMax = Math.max(...bars.map((bar) => bar.high), ...closes);
    const span = Math.max(rawMax - rawMin, 0.01);
    const min = rawMin - span * 0.08;
    const max = rawMax + span * 0.08;
    const left = PAD_LEFT;
    const right = WIDTH - PAD_RIGHT;
    const top = PAD_TOP;
    const bottom = height - PAD_BOTTOM;

    const x = (index: number) => left + (index / (bars.length - 1)) * (right - left);
    const y = (price: number) => top + ((max - price) / (max - min)) * (bottom - top);

    const line = bars.map((bar, index) => `${index === 0 ? "M" : "L"}${x(index).toFixed(2)},${y(bar.close).toFixed(2)}`).join(" ");
    const area = `${line} L${x(bars.length - 1).toFixed(2)},${bottom} L${left},${bottom} Z`;
    const gridPrices = Array.from({ length: 4 }, (_, i) => max - ((max - min) / 3) * i);
    return {
      line,
      area,
      gridPrices,
      x,
      y,
      min,
      max,
      bottom,
      right,
      left,
      first: bars[0],
      last: bars[bars.length - 1],
    };
  }, [bars, height]);

  if (!geometry) {
    return <div className="chart-empty">Collecting daily bars…</div>;
  }

  const rising = geometry.last.close >= geometry.first.close;
  const stroke = rising ? "var(--green)" : "var(--red)";
  const fillId = rising ? "area-up" : "area-down";

  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        width="100%"
        role="img"
        aria-label={`${geometry.last.close} daily price chart with ${bars.length} bars`}
      >
        <defs>
          <linearGradient id="area-up" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#15803d" stopOpacity="0.12" />
            <stop offset="100%" stopColor="#15803d" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="area-down" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#b91c1c" stopOpacity="0.12" />
            <stop offset="100%" stopColor="#b91c1c" stopOpacity="0" />
          </linearGradient>
        </defs>

        {geometry.gridPrices.map((price) => (
          <g key={price}>
            <line
              x1={geometry.left}
              x2={geometry.right}
              y1={geometry.y(price)}
              y2={geometry.y(price)}
              stroke="var(--grid)"
              strokeWidth="1"
            />
            <text
              x={geometry.right + 8}
              y={geometry.y(price) + 3}
              fill="var(--text-dim)"
              fontSize="10"
              fontFamily="var(--mono)"
            >
              {money(price)}
            </text>
          </g>
        ))}

        <path d={geometry.area} fill={`url(#${fillId})`} />
        <path d={geometry.line} fill="none" stroke={stroke} strokeWidth="1.8" strokeLinejoin="round" />

        <line
          x1={geometry.left}
          x2={geometry.right}
          y1={geometry.y(geometry.last.close)}
          y2={geometry.y(geometry.last.close)}
          stroke={stroke}
          strokeOpacity="0.35"
          strokeDasharray="2 4"
        />
        <circle
          cx={geometry.x(bars.length - 1)}
          cy={geometry.y(geometry.last.close)}
          r="3"
          fill={stroke}
        />

        <text x={geometry.left} y={height - 8} fill="var(--text-dim)" fontSize="10" fontFamily="var(--mono)">
          {simDate(geometry.first.ts)}
        </text>
        <text
          x={geometry.right}
          y={height - 8}
          textAnchor="end"
          fill="var(--text-dim)"
          fontSize="10"
          fontFamily="var(--mono)"
        >
          {simDate(geometry.last.ts)}
        </text>
      </svg>
    </div>
  );
}
