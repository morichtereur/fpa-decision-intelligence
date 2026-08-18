import { api } from "@/lib/api";
import { clientFrom, type SearchParams } from "@/lib/client";
import PlannerClient from "./PlannerClient";

export const dynamic = "force-dynamic";

export default async function PlannerPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const client = clientFrom(await searchParams);
  const [driverConfig, presets, summary] = await Promise.all([
    api.drivers(client),
    api.presets(client),
    api.client(client),
  ]);
  const baseValues = Object.fromEntries(
    Object.entries(driverConfig).map(([id, spec]) => [id, spec.default]),
  );
  const [initialScenario, initialBrief] = await Promise.all([
    api.scenario(baseValues, client),
    api.decisionBriefFor(baseValues, client),
  ]);

  return (
    <PlannerClient
      client={client}
      summary={summary}
      driverConfig={driverConfig}
      presets={presets}
      initialScenario={initialScenario}
      initialBrief={initialBrief}
    />
  );
}
