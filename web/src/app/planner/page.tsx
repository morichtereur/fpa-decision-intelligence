import { api } from "@/lib/api";
import PlannerClient from "./PlannerClient";

export const dynamic = "force-dynamic";

export default async function PlannerPage() {
  const [driverConfig, presets] = await Promise.all([api.drivers(), api.presets()]);
  const baseValues = Object.fromEntries(Object.entries(driverConfig).map(([id, spec]) => [id, spec.default]));
  const initialScenario = await api.scenario(baseValues);

  return <PlannerClient driverConfig={driverConfig} presets={presets} initialScenario={initialScenario} />;
}
