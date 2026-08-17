"use client";

import { useState } from "react";
import type { MonteCarloResponse } from "@/lib/types";
import { formatEur } from "@/lib/format";
import styles from "./MonteCarloChart.module.css";

export default function MonteCarloChart({
  monteCarlo,
  actualFcf,
}: {
  monteCarlo: MonteCarloResponse;
  actualFcf: number;
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const { counts, bin_edges } = monteCarlo.histogram;
  const maxCount = Math.max(...counts);
  const domainMin = bin_edges[0];
  const domainMax = bin_edges[bin_edges.length - 1];
  const span = domainMax - domainMin;

  const toX = (v: number) => ((v - domainMin) / span) * 100;

  const width = 720;
  const height = 220;
  const barGap = 1;
  const barWidth = width / counts.length - barGap;

  return (
    <div className={styles.wrap}>
      <svg viewBox={`0 0 ${width} ${height}`} className={styles.svg} role="img" aria-label="Monte Carlo free cash flow distribution">
        {counts.map((count, i) => {
          const barHeight = (count / maxCount) * (height - 30);
          const x = i * (barWidth + barGap);
          return (
            <rect
              key={i}
              x={x}
              y={height - 30 - barHeight}
              width={barWidth}
              height={barHeight}
              className={styles.bar}
              onMouseEnter={() => setHoverIndex(i)}
              onMouseLeave={() => setHoverIndex(null)}
              opacity={hoverIndex === null || hoverIndex === i ? 1 : 0.5}
            />
          );
        })}
        <line x1={0} y1={height - 30} x2={width} y2={height - 30} className={styles.axis} />

        {/* P50 marker */}
        <line
          x1={(toX(monteCarlo.fcf_p50) / 100) * width}
          x2={(toX(monteCarlo.fcf_p50) / 100) * width}
          y1={0}
          y2={height - 30}
          className={styles.p50Line}
        />
        {/* Actual FY2025 marker */}
        <line
          x1={(toX(actualFcf) / 100) * width}
          x2={(toX(actualFcf) / 100) * width}
          y1={0}
          y2={height - 30}
          className={styles.actualLine}
        />
      </svg>

      <div className={styles.axisLabels}>
        <span>{formatEur(domainMin)}</span>
        <span>{formatEur(domainMax)}</span>
      </div>

      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={`${styles.swatch} ${styles.swatchP50}`} /> Median (P50): {formatEur(monteCarlo.fcf_p50)}
        </span>
        <span className={styles.legendItem}>
          <span className={`${styles.swatch} ${styles.swatchActual}`} /> Actual FY2025: {formatEur(actualFcf)}
        </span>
      </div>

      {hoverIndex !== null && (
        <div className={styles.tooltip}>
          {formatEur(bin_edges[hoverIndex])} – {formatEur(bin_edges[hoverIndex + 1])}: {counts[hoverIndex]} draws
        </div>
      )}

      <div className={styles.percentiles}>
        <div>
          <span className="label">P10</span>
          <span className="mono">{formatEur(monteCarlo.fcf_p10)}</span>
        </div>
        <div>
          <span className="label">P50</span>
          <span className="mono">{formatEur(monteCarlo.fcf_p50)}</span>
        </div>
        <div>
          <span className="label">P90</span>
          <span className="mono">{formatEur(monteCarlo.fcf_p90)}</span>
        </div>
      </div>
    </div>
  );
}
