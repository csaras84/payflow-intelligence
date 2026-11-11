import React, { useMemo } from "react";
import { AllCommunityModule, ModuleRegistry, ColDef } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";

ModuleRegistry.registerModules([AllCommunityModule]);

export interface LiquidityLever {
  lever_id: string;
  source_type: "PAYPAL_DISPUTE_HOLD" | "OVERDUE_PAYPAL_INVOICE";
  counterparty: string;
  gross_amount_usd: number;
  net_unlockable_usd: number;
  recovery_probability: number;
  expected_recovery_usd: number;
  available_by_friday_usd: number;
  est_settlement_hours: number;
  priority_score: number;
  paypal_action: string;
  ai_reasoning: string;
  drafted_message: string;
  status: "PROPOSED" | "APPROVED" | "EXECUTED" | "SKIPPED";
}

interface Props {
  rows: LiquidityLever[];
  selectedIds: Record<string, boolean>;
  onToggle: (id: string, checked: boolean) => void;
  locked: boolean;
}

const fmtUsd = (n?: number) =>
  typeof n === "number" ? `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "$0.00";

export default function LiquidityGrid({ rows, selectedIds, onToggle, locked }: Props) {
  const columnDefs = useMemo<ColDef<LiquidityLever>[]>(
    () => [
      {
        headerName: "Approve",
        field: "lever_id",
        width: 90,
        cellRenderer: (params: any) => {
          const id = params.value as string;
          return (
            <input
              type="checkbox"
              disabled={locked}
              checked={!!selectedIds[id]}
              onChange={(e) => onToggle(id, e.target.checked)}
              style={{ width: 16, height: 16, cursor: locked ? "default" : "pointer" }}
            />
          );
        },
      },
      {
        headerName: "Source",
        field: "source_type",
        width: 150,
        valueFormatter: (p) =>
          p.value === "PAYPAL_DISPUTE_HOLD" ? "Dispute Hold" : "Overdue Invoice",
      },
      { headerName: "Case / Counterparty", field: "counterparty", width: 220 },
      {
        headerName: "Trapped",
        field: "gross_amount_usd",
        width: 115,
        valueFormatter: (p) => fmtUsd(p.value),
      },
      {
        headerName: "Cash by Friday",
        field: "available_by_friday_usd",
        width: 140,
        cellStyle: (p) => ({
          fontWeight: 700,
          color: (p.value || 0) > 0 ? "#047857" : "#6b7280",
        }),
        valueFormatter: (p) => fmtUsd(p.value),
      },
      {
        headerName: "Expected Recovery",
        field: "expected_recovery_usd",
        width: 165,
        valueFormatter: (p) =>
          `${fmtUsd(p.value)} (${Math.round((p.data?.recovery_probability || 0) * 100)}%)`,
      },
      { headerName: "PayPal Action", field: "paypal_action", width: 230 },
      {
        headerName: "AI Strategy & Reasoning",
        field: "ai_reasoning",
        flex: 1,
        minWidth: 320,
      },
      { headerName: "Status", field: "status", width: 115 },
    ],
    [selectedIds, locked, onToggle]
  );

  return (
    <section style={{ marginBottom: 20 }}>
      <h3 style={{ margin: "0 0 8px", fontSize: 16 }}>
        Ranked Working-Capital Levers (AG Grid — Disputes & Overdue Invoices)
      </h3>
      <div style={{ height: 310, width: "100%" }}>
        <AgGridReact
          rowData={rows}
          columnDefs={columnDefs}
          rowHeight={48}
          headerHeight={40}
        />
      </div>
    </section>
  );
}