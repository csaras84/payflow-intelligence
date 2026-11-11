import { useState } from "react";
import LiquidityGrid, { LiquidityRow } from "./components/LiquidityGrid";
import ApprovalCard, { ProposedAction } from "./components/ApprovalCard";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

interface RunResponse {
  run_id: string;
  awaiting_approval: boolean;
  state: {
    liquidity?: { threshold: number; grid: LiquidityRow[] };
    proposed_action?: ProposedAction | null;
    result?: Record<string, unknown> | null;
    errors?: string[];
  };
}

export default function App() {
  const [run, setRun] = useState<RunResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function call(path: string, body?: unknown) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
      setRun(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const decide = (decision: "approved" | "rejected") =>
    run && call(`/runs/${run.run_id}/approve`, { decision });

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>PayFlow Intelligence</h1>
        <button onClick={() => call("/runs")} disabled={loading}>
          {loading ? "Running…" : "Analyze liquidity"}
        </button>
      </header>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {run?.state.liquidity && (
        <LiquidityGrid rows={run.state.liquidity.grid} threshold={run.state.liquidity.threshold} />
      )}

      {run?.state.proposed_action && (
        <ApprovalCard
          action={run.state.proposed_action}
          pending={run.awaiting_approval}
          loading={loading}
          onDecide={decide}
          result={run.state.result ?? null}
        />
      )}

      {run?.state.errors && run.state.errors.length > 0 && (
        <details style={{ marginTop: 16 }}>
          <summary>Warnings ({run.state.errors.length})</summary>
          <ul>{run.state.errors.map((e) => <li key={e}>{e}</li>)}</ul>
        </details>
      )}
    </main>
  );
}
