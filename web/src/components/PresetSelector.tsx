"use client";

import type { PresetsResponse } from "@/lib/types";
import styles from "./PresetSelector.module.css";

export default function PresetSelector({
  presets,
  activePresetId,
  onSelect,
}: {
  presets: PresetsResponse;
  activePresetId: string | null;
  onSelect: (presetId: string) => void;
}) {
  return (
    <div className={styles.row}>
      {Object.entries(presets).map(([id, preset]) => (
        <button
          key={id}
          type="button"
          className={id === activePresetId ? `${styles.chip} ${styles.active}` : styles.chip}
          onClick={() => onSelect(id)}
          aria-pressed={id === activePresetId}
        >
          {preset.label}
        </button>
      ))}
    </div>
  );
}
