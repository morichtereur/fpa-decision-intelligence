import type {
  AssumptionRow,
  BacktestResult,
  CommentaryResponse,
  DriverConfig,
  DriverPriorityRow,
  DriverValues,
  MonteCarloResponse,
  OutlookResponse,
  PresetsResponse,
  ScenarioResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

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
  outlook: () => request<OutlookResponse>("/api/outlook"),
  drivers: () => request<DriverConfig>("/api/drivers"),
  presets: () => request<PresetsResponse>("/api/presets"),
  backtest: () => request<BacktestResult>("/api/backtest"),
  driverPriority: () => request<DriverPriorityRow[]>("/api/driver-priority"),
  monteCarlo: () => request<MonteCarloResponse>("/api/monte-carlo"),
  assumptions: () => request<AssumptionRow[]>("/api/assumptions"),
  commentary: (scenarioId: string) => request<CommentaryResponse>(`/api/commentary/${scenarioId}`),
  scenario: (driverValues: DriverValues) =>
    request<ScenarioResponse>("/api/scenario", {
      method: "POST",
      body: JSON.stringify({ driver_values: driverValues }),
    }),
  commentaryLive: (driverValues: DriverValues) =>
    request<CommentaryResponse>("/api/commentary/live", {
      method: "POST",
      body: JSON.stringify({ driver_values: driverValues }),
    }),
};

export { ApiError };
