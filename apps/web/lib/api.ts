export type SystemStatus = {
  application: string;
  database: string;
  mt5: string;
  market_data: string;
  mode: string;
};

export type Decision = {
  direction: "BUY" | "SELL" | "NO_TRADE";
  strategy: string;
  market_regime: string;
  data_quality_status: string;
  reasons: string[];
  timestamp: string;
};

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:2026";

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API indisponible (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export async function getSystemStatus(): Promise<SystemStatus> {
  return request<SystemStatus>("/system/status");
}

export async function getDecision(symbol: string): Promise<Decision> {
  const payload = await request<{ data: { decision: Decision } }>(
    `/api/v1/decision/${encodeURIComponent(symbol)}?asset_class=forex&timeframe=M15&persist=false`,
  );
  return payload.data.decision;
}
