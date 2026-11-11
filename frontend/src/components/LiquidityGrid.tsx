export interface LiquidityRow {
  currency: string;
  available: number;
  inflow_30d: number;
  outflow_30d: number;
  net_30d: number;
  status: "low" | "healthy";
}

interface Props {
  rows: LiquidityRow[];
  threshold: number;
}

const fmt = (n: number, cur: string) =>
  new Intl.NumberFormat(undefined, { style: "currency", currency: cur }).format(n);

export default function LiquidityGrid({ rows, threshold }: Props) {
  if (rows.length === 0) return <p>No balance data yet.</p>;

  return (
    <section style={{ marginTop: 24 }}>
      <h2>Liquidity</h2>
      <p style={{ color: "#666" }}>Low-balance threshold: {threshold.toLocaleString()}</p>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
            <th>Currency</th>
            <th>Available</th>
            <th>Inflow (30d)</th>
            <th>Outflow (30d)</th>
            <th>Net (30d)</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.currency} style={{ borderBottom: "1px solid #f0f0f0" }}>
              <td>{r.currency}</td>
              <td>{fmt(r.available, r.currency)}</td>
              <td>{fmt(r.inflow_30d, r.currency)}</td>
              <td>{fmt(r.outflow_30d, r.currency)}</td>
              <td style={{ color: r.net_30d >= 0 ? "green" : "crimson" }}>{fmt(r.net_30d, r.currency)}</td>
              <td>
                <span
                  style={{
                    padding: "2px 8px",
                    borderRadius: 12,
                    background: r.status === "low" ? "#fde2e2" : "#e2f5e9",
                    color: r.status === "low" ? "#a12" : "#185",
                  }}
                >
                  {r.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
