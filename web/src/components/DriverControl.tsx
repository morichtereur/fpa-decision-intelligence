"use client";

import type { DriverSpec } from "@/lib/types";
import { formatDriverValue } from "@/lib/format";
import styles from "./DriverControl.module.css";

export default function DriverControl({
  driverId,
  spec,
  value,
  onChange,
}: {
  driverId: string;
  spec: DriverSpec;
  value: number;
  onChange: (driverId: string, value: number) => void;
}) {
  const changed = Math.abs(value - spec.default) > 1e-9;
  const outOfGuidance =
    spec.guidance_low !== null && spec.guidance_high !== null && (value < spec.guidance_low || value > spec.guidance_high);

  const pctOf = (v: number) => ((v - spec.min) / (spec.max - spec.min)) * 100;
  const guidanceLowPct = spec.guidance_low !== null ? pctOf(spec.guidance_low) : null;
  const guidanceHighPct = spec.guidance_high !== null ? pctOf(spec.guidance_high) : null;
  const valuePct = pctOf(value);

  return (
    <div className={styles.control}>
      <div className={styles.headerRow}>
        <span className={styles.name}>{spec.label}</span>
      </div>

      <div className={styles.valueRow}>
        {changed ? (
          <span className={`mono ${styles.valueChange}`}>
            <span className={styles.valueBase}>{formatDriverValue(spec.default, spec.unit)}</span>
            <span className={styles.arrow}>→</span>
            <span className={styles.valueNew}>{formatDriverValue(value, spec.unit)}</span>
          </span>
        ) : (
          <span className={`mono ${styles.valueStatic}`}>{formatDriverValue(value, spec.unit)}</span>
        )}
        {changed && (
          <button type="button" className={styles.resetOne} onClick={() => onChange(driverId, spec.default)}>
            Reset
          </button>
        )}
      </div>

      {/* The track is drawn entirely as custom absolutely-positioned divs,
          not the native <input> track — WebKit/Firefox render the native
          track as an opaque replaced element that ignores sibling z-index,
          so a guidance-range overlay behind it never shows through. The
          native input is made fully transparent and sits on top purely for
          its thumb and interaction/keyboard/accessibility behaviour. */}
      <div className={styles.sliderWrap}>
        <div className={styles.trackVisual}>
          <div className={styles.trackFill} style={{ width: `${valuePct}%` }} />
          {guidanceLowPct !== null && guidanceHighPct !== null && (
            <div
              className={styles.guidanceBand}
              style={{ left: `${guidanceLowPct}%`, width: `${guidanceHighPct - guidanceLowPct}%` }}
              title={spec.guidance_text}
            />
          )}
        </div>
        <input
          type="range"
          className={styles.slider}
          min={spec.min}
          max={spec.max}
          step={spec.step}
          value={value}
          onChange={(e) => onChange(driverId, Number(e.target.value))}
          aria-label={spec.label}
        />
      </div>

      <div className={styles.metaRow}>
        <span className={styles.source}>{spec.guidance_text}</span>
      </div>
      <div className={styles.metaRow}>
        <span className={styles.confidence}>{spec.confidence} confidence</span>
        {outOfGuidance && <span className={styles.warning}>Outside disclosed guidance range</span>}
      </div>
    </div>
  );
}
