export interface ProposedAction {
  kind: "payout" | "hold" | "none";
  amount?: number;
  currency?: string;
  recipient?: string;
  rationale?: string;
}

interface Props {
  action: ProposedAction;
  pending: boolean;
  loading: boolean;
  onDecide: (decision: "approved" | "rejected") => void;
  result: Record<string, unknown> | null;
}

export default function ApprovalCard({ action, pending, loading, onDecide, result }: Props) {
  return (
    <section
      style={{ marginTop: 24, padding: 16, border: "1px solid #ddd", borderRadius: 8, background: "#fafafa" }}
    >
      <h2 style={{ marginTop: 0 }}>Proposed action</h2>

      {action.kind === "none" ? (
        <p>{action.rationale ?? "No action needed."}</p>
      ) : (
        <>
          <p>
            <strong>{action.kind.toUpperCase()}</strong> {action.amount?.toFixed(2)} {action.currency} →{" "}
            {action.recipient}
          </p>
          {action.rationale && <p style={{ color: "#555" }}>{action.rationale}</p>}
        </>
      )}

      {pending && (
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => onDecide("approved")} disabled={loading}>Approve</button>
          <button onClick={() => onDecide("rejected")} disabled={loading}>Reject</button>
        </div>
      )}

      {result && (
        <pre style={{ marginTop: 12, background: "#fff", padding: 8, overflowX: "auto" }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </section>
  );
}
