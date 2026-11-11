import React from "react";

export interface AuditLogEntry {
  timestamp: string;
  step_name: string;
  paypal_operation: string;
  reference_id: string;
  verified_status: string;
  cash_impact_usd: number;
  details: string;
}

interface Props {
  approvalStatus: "PENDING_APPROVAL" | "APPROVED" | "REJECTED";
  selectedCount: number;
  selectedFridayUsd: number;
  supplierName: string;
  poId: string;
  requiredUsd: number;
  projectedBalanceUsd: number;
  loading: boolean;
  onApprove: () => void;
  finalSummary?: string | null;
  auditLog?: AuditLogEntry[];
}

const fmtUsd = (n?: number) =>
  typeof n === "number" ? `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "$0.00";

export default function ApprovalCard({
  approvalStatus,
  selectedCount,
  selectedFridayUsd,
  supplierName,
  poId,
  requiredUsd,
  projectedBalanceUsd,
  loading,
  onApprove,
  finalSummary,
  auditLog,
}: Props) {
  const isApproved = approvalStatus === "APPROVED";
  const coversObligation = projectedBalanceUsd >= requiredUsd;

  return (
    <section>
      <div
        style={{
          border: `2px solid ${isApproved ? "#10b981" : "#f59e0b"}`,
          background: isApproved ? "#ecfdf5" : "#fffbeb",
          borderRadius: 8,
          padding: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
        }}
      >
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, color: isApproved ? "#065f46" : "#92400e" }}>
            {isApproved
              ? "Merchant Approval Gate: Approved & Executed in PayPal Sandbox"
              : "Merchant Approval Gate (LangGraph interrupt — Read-Only Complete)"}
          </div>
          <div style={{ fontSize: 14, color: isApproved ? "#047857" : "#78350f", marginTop: 4 }}>
            Approving <strong>{selectedCount}</strong> actions unlocks{" "}
            <strong>{fmtUsd(selectedFridayUsd)}</strong> by Friday → Projected Friday balance:{" "}
            <strong>{fmtUsd(projectedBalanceUsd)}</strong>{" "}
            {coversObligation
              ? `(Covers ${fmtUsd(requiredUsd)} payout for ${poId} to ${supplierName})`
              : `(Short of ${fmtUsd(requiredUsd)} target for ${supplierName})`}
          </div>
        </div>

        <button
          onClick={onApprove}
          disabled={loading || isApproved || selectedCount === 0}
          style={{
            background: isApproved ? "#059669" : "#d97706",
            color: "white",
            border: "none",
            padding: "12px 22px",
            borderRadius: 6,
            fontWeight: 700,
            cursor: isApproved || loading ? "default" : "pointer",
          }}
        >
          {loading
            ? "Executing PayPal Writes..."
            : isApproved
            ? "Executed in Sandbox"
            : "2. Approve & Execute Plan"}
        </button>
      </div>

      {finalSummary && (
        <div
          style={{
            background: "#f0fdf4",
            border: "1px solid #86efac",
            padding: 14,
            borderRadius: 8,
            marginBottom: 16,
            fontWeight: 600,
            color: "#166534",
          }}
        >
          {finalSummary}
        </div>
      )}

      {auditLog && auditLog.length > 0 && (
        <div>
          <h3 style={{ margin: "0 0 8px", fontSize: 16 }}>
            Verify & Audit Log (PayPal Sandbox Receipts)
          </h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#f3f4f6", textAlign: "left" }}>
                <th style={{ padding: 8, border: "1px solid #e5e7eb" }}>Step</th>
                <th style={{ padding: 8, border: "1px solid #e5e7eb" }}>PayPal Operation</th>
                <th style={{ padding: 8, border: "1px solid #e5e7eb" }}>Reference ID</th>
                <th style={{ padding: 8, border: "1px solid #e5e7eb" }}>Verified Status</th>
                <th style={{ padding: 8, border: "1px solid #e5e7eb" }}>Friday Cash Impact</th>
                <th style={{ padding: 8, border: "1px solid #e5e7eb" }}>Details / Drafted Note</th>
              </tr>
            </thead>
            <tbody>
              {auditLog.map((entry, idx) => (
                <tr key={idx}>
                  <td style={{ padding: 8, border: "1px solid #e5e7eb" }}>{entry.step_name}</td>
                  <td style={{ padding: 8, border: "1px solid #e5e7eb", fontFamily: "monospace" }}>
                    {entry.paypal_operation}
                  </td>
                  <td style={{ padding: 8, border: "1px solid #e5e7eb", fontFamily: "monospace" }}>
                    {entry.reference_id}
                  </td>
                  <td style={{ padding: 8, border: "1px solid #e5e7eb", fontWeight: 600 }}>
                    {entry.verified_status}
                  </td>
                  <td style={{ padding: 8, border: "1px solid #e5e7eb" }}>
                    {entry.cash_impact_usd !== 0 ? fmtUsd(entry.cash_impact_usd) : "Read-back verified"}
                  </td>
                  <td style={{ padding: 8, border: "1px solid #e5e7eb" }}>{entry.details}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}