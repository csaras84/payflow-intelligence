import React, { useState, useMemo } from "react";
import LiquidityGrid, { LiquidityLever } from "./components/LiquidityGrid";
import ApprovalCard, { AuditLogEntry } from "./components/ApprovalCard";

const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

interface TreasuryState {
  merchant_query: string;
  available_balance_usd: number;
  target_obligation: {
    supplier_name: string;
    supplier_paypal_email: string;
    purchase_order_id: string;
    amount_required_usd: number;
    due_description: string;
  };
  initial_gap_usd: number;
  ranked_options: LiquidityLever[];
  immediate_friday_cash_usd: number;
  expected_total_recovery_usd: number;
  projected_friday_balance_usd: number;
  approval_status: "PENDING_APPROVAL" | "APPROVED" | "REJECTED";
  audit_log: AuditLogEntry[];
  final_summary?: string | null;
}

const fmtUsd = (n?: number) =>
  typeof n === "number" ? `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "$0.00";

export default function App() {
  const [query, setQuery] = useState(
    "I need $1,800 by Friday to pay our wholesale coffee supplier, Apex Roasters."
  );
  const [threadId, setThreadId] = useState<string | null>(null);
  const [state, setState] = useState<TreasuryState | null>(null);
  const [selectedIds, setSelectedIds] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runPlan() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ merchant_query: query }),
      });
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
      const data = await res.json();
      setThreadId(data.thread_id);
      setState(data.state);

      const defaults: Record<string, boolean> = {};
      (data.state.ranked_options || []).forEach((opt: LiquidityLever) => {
        if (opt.status === "PROPOSED" && opt.expected_recovery_usd > 0) {
          defaults[opt.lever_id] = true;
        }
      });
      setSelectedIds(defaults);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function runExecute() {
    if (!threadId) return;
    setLoading(true);
    setError(null);
    const approved_lever_ids = Object.keys(selectedIds).filter((k) => selectedIds[k]);
    try {
      const res = await fetch(`${API}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId, approved_lever_ids }),
      });
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
      const data = await res.json();
      setState(data.state);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const selectedFridayUsd = useMemo(() => {
    if (!state?.ranked_options) return 0;
    return state.ranked_options
      .filter((o) => selectedIds[o.lever_id])
      .reduce((sum, o) => sum + o.available_by_friday_usd, 0);
  }, [state, selectedIds]);

  const selectedExpectedUsd = useMemo(() => {
    if (!state?.ranked_options) return 0;
    return state.ranked_options
      .filter((o) => selectedIds[o.lever_id])
      .reduce((sum, o) => sum + o.expected_recovery_usd, 0);
  }, [state, selectedIds]);

  return (
    <main style={{ maxWidth: 1400, margin: "0 auto", padding: 24, fontFamily: "Inter, system-ui, sans-serif", color: "#111827" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24 }}>PayFlow Intelligence</h1>
          <p style={{ margin: "4px 0 0", color: "#4b5563", fontSize: 14 }}>
            Human-approved Working-Capital & Dispute-Resolution Agent (LangGraph + Azure OpenAI GPT-4.1 mini + PayPal Sandbox)
          </p>
        </div>
        {threadId && (
          <span style={{ background: "#f3f4f6", padding: "6px 12px", borderRadius: 6, fontSize: 13, fontFamily: "monospace" }}>
            Thread: {threadId} · {state?.approval_status}
          </span>
        )}
      </header>

      <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ flex: 1, padding: "10px 14px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 15 }}
        />
        <button
          onClick={runPlan}
          disabled={loading}
          style={{ background: "#003087", color: "white", border: "none", padding: "10px 20px", borderRadius: 6, fontWeight: 600, cursor: "pointer" }}
        >
          {loading && !state ? "Diagnosing..." : "1. Diagnose Cash Gap & Plan (Read-Only)"}
        </button>
      </div>

      {error && (
        <div style={{ background: "#fef2f2", color: "#991b1b", padding: 12, borderRadius: 6, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {state && (
        <>
          {/* Gap Header */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12, marginBottom: 20 }}>
            <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 14, background: "#f9fafb" }}>
              <div style={{ fontSize: 11, color: "#6b7280", fontWeight: 600 }}>AVAILABLE BALANCE</div>
              <div style={{ fontSize: 20, fontWeight: 700, marginTop: 4 }}>{fmtUsd(state.available_balance_usd)}</div>
            </div>
            <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 14, background: "#f9fafb" }}>
              <div style={{ fontSize: 11, color: "#6b7280", fontWeight: 600 }}>FRIDAY OBLIGATION</div>
              <div style={{ fontSize: 20, fontWeight: 700, marginTop: 4 }}>
                {fmtUsd(state.target_obligation.amount_required_usd)}
              </div>
              <div style={{ fontSize: 12, color: "#4b5563" }}>{state.target_obligation.supplier_name}</div>
            </div>
            <div style={{ border: "1px solid #fecaca", borderRadius: 8, padding: 14, background: "#fef2f2" }}>
              <div style={{ fontSize: 11, color: "#991b1b", fontWeight: 600 }}>INITIAL CASH GAP</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#b91c1c", marginTop: 4 }}>
                {fmtUsd(state.initial_gap_usd)}
              </div>
            </div>
            <div style={{ border: "1px solid #a7f3d0", borderRadius: 8, padding: 14, background: "#ecfdf5" }}>
              <div style={{ fontSize: 11, color: "#065f46", fontWeight: 600 }}>CASH AVAILABLE BY FRIDAY</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#047857", marginTop: 4 }}>
                +{fmtUsd(selectedFridayUsd)}
              </div>
              <div style={{ fontSize: 12, color: "#065f46" }}>
                Total w/ balance: {fmtUsd(state.available_balance_usd + selectedFridayUsd)}
              </div>
            </div>
            <div style={{ border: "1px solid #bfdbfe", borderRadius: 8, padding: 14, background: "#eff6ff" }}>
              <div style={{ fontSize: 11, color: "#1e40af", fontWeight: 600 }}>TOTAL EXPECTED RECOVERY</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: "#1d4ed8", marginTop: 4 }}>
                +{fmtUsd(selectedExpectedUsd)}
              </div>
              <div style={{ fontSize: 12, color: "#1e40af" }}>Includes post-Friday invoices</div>
            </div>
          </div>

          <LiquidityGrid
            rows={state.ranked_options || []}
            selectedIds={selectedIds}
            onToggle={(id, checked) => setSelectedIds((prev) => ({ ...prev, [id]: checked }))}
            locked={state.approval_status === "APPROVED"}
          />

          <ApprovalCard
            approvalStatus={state.approval_status}
            selectedCount={Object.values(selectedIds).filter(Boolean).length}
            selectedFridayUsd={selectedFridayUsd}
            supplierName={state.target_obligation.supplier_name}
            poId={state.target_obligation.purchase_order_id}
            requiredUsd={state.target_obligation.amount_required_usd}
            projectedBalanceUsd={state.available_balance_usd + selectedFridayUsd}
            loading={loading}
            onApprove={runExecute}
            finalSummary={state.final_summary}
            auditLog={state.audit_log}
          />
        </>
      )}
    </main>
  );
}