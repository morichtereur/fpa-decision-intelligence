"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { CommentaryResponse, DriverConfig, DriverValues, PresetsResponse, ScenarioResponse } from "@/lib/types";
import DriverControl from "@/components/DriverControl";
import PresetSelector from "@/components/PresetSelector";
import ScenarioComparisonTable from "@/components/ScenarioComparisonTable";
import BridgeChart from "@/components/BridgeChart";
import CommentaryPanel from "@/components/CommentaryPanel";
import styles from "./planner.module.css";

const DRIVER_ORDER = ["revenue_growth", "ebitda_margin", "working_capital_pct", "capex_eur_m", "tax_rate_pct"];

/** Surface what actually went wrong. A collapsed "it failed" hides the two
 *  cases that look identical from the outside and need opposite fixes: the
 *  API answering with an error, and the browser never reaching it. */
function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    return `API error ${err.status}${err.message ? `: ${err.message}` : ""}`;
  }
  if (err instanceof TypeError) {
    // fetch() rejects with a TypeError when the request never completes —
    // CORS rejection, DNS, offline. The browser console carries the reason;
    // the response itself is unreadable to JavaScript by design.
    return "Could not reach the API — blocked before a response was readable (CORS, network, or wrong API URL). See the browser console.";
  }
  return err instanceof Error ? err.message : String(err);
}

export default function PlannerClient({
  driverConfig,
  presets,
  initialScenario,
}: {
  driverConfig: DriverConfig;
  presets: PresetsResponse;
  initialScenario: ScenarioResponse;
}) {
  const baseValues = useMemo(
    () => Object.fromEntries(Object.entries(driverConfig).map(([id, spec]) => [id, spec.default])),
    [driverConfig],
  );

  const [driverValues, setDriverValues] = useState<DriverValues>(baseValues);
  const [activePresetId, setActivePresetId] = useState<string | null>("base");
  const [scenario, setScenario] = useState<ScenarioResponse>(initialScenario);
  const [commentary, setCommentary] = useState<CommentaryResponse | null>(null);
  const [commentaryLoading, setCommentaryLoading] = useState(false);
  const [commentaryError, setCommentaryError] = useState<string | null>(null);
  const [scenarioError, setScenarioError] = useState<string | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const recompute = useCallback((values: DriverValues) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const result = await api.scenario(values);
        setScenario(result);
        setScenarioError(null);
      } catch (err) {
        // Without this the await rejects inside a setTimeout callback, where
        // nothing is listening: the results column silently keeps the previous
        // scenario and the failure looks like the sliders doing nothing.
        console.error("POST /api/scenario failed", err);
        setScenarioError(describeError(err));
      }
    }, 120);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // Mount-only: the page opens on the Base preset, so fetch its
  // pre-generated commentary once. All later scenario changes fetch (or
  // clear) commentary directly from the handler that caused them — see
  // handleDriverChange / handlePresetSelect below.
  useEffect(() => {
    api
      .commentary("base")
      .then(setCommentary)
      .catch(() => setCommentary(null));
  }, []);

  // Commentary is loaded directly by whichever user action changes the
  // scenario, not reactively via an effect watching activePresetId — moving
  // a slider away from a named preset clears commentary immediately (no
  // stale text for a scenario the user has since changed), and picking a
  // preset fetches its pre-generated commentary right away.
  function handleDriverChange(driverId: string, value: number) {
    const next = { ...driverValues, [driverId]: value };
    setDriverValues(next);
    setActivePresetId(null);
    setCommentary(null);
    setCommentaryError(null);
    recompute(next);
  }

  function handlePresetSelect(presetId: string) {
    const values = presets[presetId].values;
    setDriverValues(values);
    setActivePresetId(presetId);
    setCommentary(null);
    setCommentaryError(null);
    recompute(values);
    api
      .commentary(presetId)
      .then(setCommentary)
      .catch(() => setCommentary(null));
  }

  function handleReset() {
    handlePresetSelect("base");
  }

  async function handleGenerateCommentary() {
    setCommentaryLoading(true);
    setCommentaryError(null);
    try {
      const result = await api.commentaryLive(driverValues);
      setCommentary(result);
    } catch (err) {
      console.error("POST /api/commentary/live failed", err);
      setCommentaryError(
        err instanceof ApiError && err.status === 503
          ? "Commentary unavailable — set ANTHROPIC_API_KEY on the API server to enable it."
          : describeError(err),
      );
    } finally {
      setCommentaryLoading(false);
    }
  }

  const hasChanges = Object.keys(scenario.changed_drivers).length > 0;
  const outOfGuidanceIds = Object.keys(scenario.out_of_guidance);

  return (
    <div className={styles.page}>
      <div className={`label ${styles.eyebrow}`}>02 — Scenario Planner</div>
      <h1 className={styles.heading}>Change an assumption, see the financial consequence</h1>

      <div className={styles.layout}>
        <div className={styles.controlsColumn}>
          <div className={styles.presetsBlock}>
            <div className={styles.presetsHeader}>
              <span className="label">Scenario</span>
              <button type="button" className={styles.resetAll} onClick={handleReset} disabled={!hasChanges}>
                Reset to Base
              </button>
            </div>
            <PresetSelector presets={presets} activePresetId={activePresetId} onSelect={handlePresetSelect} />
          </div>

          <div className={styles.controls}>
            {DRIVER_ORDER.map((driverId) => (
              <DriverControl
                key={driverId}
                driverId={driverId}
                spec={driverConfig[driverId]}
                value={driverValues[driverId]}
                onChange={handleDriverChange}
              />
            ))}
          </div>
        </div>

        <div className={styles.resultsColumn}>
          {outOfGuidanceIds.length > 0 && (
            <div className={styles.guidanceWarning}>
              <span className={styles.warningLabel}>Outside disclosed guidance</span>
              <span>
                {outOfGuidanceIds.map((id) => driverConfig[id].label).join(", ")} — useful for stress testing,
                but adidas has not guided to this range.
              </span>
            </div>
          )}

          {scenarioError && (
            <div className={styles.guidanceWarning} role="alert">
              <span className={styles.warningLabel}>Scenario not recalculated</span>
              <span>
                {scenarioError} The figures below are the last ones the model returned, not this
                scenario.
              </span>
            </div>
          )}

          <section className={styles.block}>
            <h2 className={styles.blockHeading}>Scenario vs. Base</h2>
            <ScenarioComparisonTable base={scenario.base} scenario={scenario.scenario} />
          </section>

          <section className={styles.block}>
            <h2 className={styles.blockHeading}>Free cash flow bridge</h2>
            <BridgeChart steps={scenario.bridge} />
          </section>

          <section className={styles.block}>
            <CommentaryPanel
              commentary={commentary}
              loading={commentaryLoading}
              error={commentaryError}
              onGenerate={handleGenerateCommentary}
              canGenerate={true}
            />
          </section>
        </div>
      </div>
    </div>
  );
}
