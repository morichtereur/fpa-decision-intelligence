import type {
  ClientSummary,
  AssumptionRow,
  BacktestResult,
  CommentaryResponse,
  DriverConfig,
  DriverPriorityRow,
  DecisionBriefResponse,
  DriverValues,
  MonteCarloResponse,
  OutlookResponse,
  PresetsResponse,
  MetricMapping,
  PrioritiesResponse,
  VarianceBridgeResponse,
  ScenarioResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

/** Which planning model the request is against. Threaded explicitly through
 *  every call rather than held in module state: a server component rendering
 *  two clients' pages concurrently must not be able to see one bleed into the
 *  other, and an implicit "current client" is exactly how that happens. */
export type ClientId = string | undefined;

function scoped(path: string, client: ClientId): string {
  if (!client) return path;
  return `${path}${path.includes("?") ? "&" : "?"}client=${encodeURIComponent(client)}`;
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  clients: () => request<{ default: string; clients: ClientSummary[] }>("/api/clients"),
  client: (c?: ClientId) => request<ClientSummary>(scoped("/api/client", c)),
  outlook: (c?: ClientId) => request<OutlookResponse>(scoped("/api/outlook", c)),
  drivers: (c?: ClientId) => request<DriverConfig>(scoped("/api/drivers", c)),
  presets: (c?: ClientId) => request<PresetsResponse>(scoped("/api/presets", c)),
  backtest: (c?: ClientId) => request<BacktestResult | null>(scoped("/api/backtest", c)),
  driverPriority: (c?: ClientId) => request<DriverPriorityRow[]>(scoped("/api/driver-priority", c)),
  monteCarlo: (c?: ClientId) => request<MonteCarloResponse>(scoped("/api/monte-carlo", c)),
  assumptions: (c?: ClientId) => request<AssumptionRow[]>(scoped("/api/assumptions", c)),
  mappings: (c?: ClientId) =>
    request<Record<string, MetricMapping>>(scoped("/api/mappings", c)),
  priorities: (c?: ClientId) => request<PrioritiesResponse>(scoped("/api/priorities", c)),
  variance: (metric = "free_cash_flow", c?: ClientId) =>
    request<VarianceBridgeResponse | null>(scoped(`/api/variance/${metric}`, c)),
  decisionBrief: (c?: ClientId) => request<DecisionBriefResponse>(scoped("/api/decision-brief", c)),
  decisionBriefFor: (driverValues: DriverValues, c?: ClientId) =>
    request<DecisionBriefResponse>("/api/decision-brief", {
      method: "POST",
      body: JSON.stringify({ driver_values: driverValues, client: c }),
    }),
  commentary: (scenarioId: string, c?: ClientId) =>
    request<CommentaryResponse>(scoped(`/api/commentary/${scenarioId}`, c)),
  scenario: (driverValues: DriverValues, c?: ClientId) =>
    request<ScenarioResponse>("/api/scenario", {
      method: "POST",
      body: JSON.stringify({ driver_values: driverValues, client: c }),
    }),
  commentaryLive: (driverValues: DriverValues, c?: ClientId) =>
    request<CommentaryResponse>("/api/commentary/live", {
      method: "POST",
      body: JSON.stringify({ driver_values: driverValues, client: c }),
    }),
};

export { ApiError };
