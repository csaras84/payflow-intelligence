# PayFlow Intelligence — Architecture

An agent that finds trapped cash in a merchant's PayPal account (frozen disputes,
overdue invoices), ranks the options, asks the merchant to approve, and then pays
a supplier — all against the live PayPal Sandbox.

---

## 1. Design principles

1. **The AI judges, Python counts.** Claude reads the merchant's request, reads
   courier PDFs, chooses a strategy per dispute and writes messages. Every amount,
   probability, ranking and total is computed in plain Python. AI output is
   validated against a schema before it is used.
2. **Nothing changes before approval.** Every step before the approval gate only
   reads from PayPal. Every call that changes something in PayPal happens after
   the merchant approves, and only for the options they approved.
3. **Real sandbox data only.** Disputes, invoices and the supplier payout are real
   Sandbox objects. Demo data is created ahead of time by a seed script plus a few
   manual buyer actions (see §9).
4. **One currency: USD.** PayPal and the UI both use USD, so every number on
   screen is the same number PayPal holds; no conversion step.
5. **Every PayPal change is logged and safe to retry.** Each write sends a
   `PayPal-Request-Id` header and is written to an audit log with the PayPal ID
   it returned.

---

## 2. System overview

```text
+-------------------------------------------------------------------------+
|  FRONTEND  React + TypeScript + Vite + AG Grid                          |
|  [Cash-gap header]  [Options grid (AG Grid)]  [Approval panel]  [Log]   |
+-----------------------------------+-------------------------------------+
                                    | REST (JSON)
+-----------------------------------v-------------------------------------+
|  API  FastAPI                                                           |
|  POST /api/treasury/plan    POST /api/treasury/execute                  |
|  GET  /api/treasury/runs/{thread_id}    GET /health                     |
+-----------------------------------+-------------------------------------+
                                    |
+-----------------------------------v-------------------------------------+
|  AGENT  LangGraph StateGraph  (checkpointed: SQLite, or Postgres)       |
|                                                                         |
|              [1] diagnose_liquidity                                     |
|                   /              \          (parallel)                  |
|      [2A] analyze_disputes   [2B] analyze_receivables                   |
|                   \              /          (join)                      |
|              [3] synthesize_plan                                        |
|                        |                                                |
|        ======  interrupt(): merchant approval  ======                   |
|                        |                                                |
|              [4] execute_plan          <- only PayPal writes            |
|                        |                                                |
|              [5] verify_and_audit                                       |
+-------------+---------------------------------------+-------------------+
              |                                       |
   +----------v-----------+             +-------------v--------------+
   | Claude (Anthropic)   |             | PayPal Sandbox REST APIs   |
   | structured outputs   |             | via paypal-agent-toolkit   |
   +----------------------+             | + httpx client             |
                                        +----------------------------+
```

---

## 3. Graph steps

| # | Step | Reads / calls | AI's job | Python's job | Output added to state |
|---|------|---------------|----------|--------------|-----------------------|
| 1 | `diagnose_liquidity` | `GET /v1/reporting/balances` | Parse request → `{amount, currency, deadline, supplier_name, supplier_email}` | Compute `gap = target − available` | `goal`, `available_cash`, `gap` |
| 2A | `analyze_disputes` | `list_disputes`, `get_dispute`; courier PDFs from `backend/demo_assets/` | Extract tracking no./carrier/delivery date from PDF; recommend **contest** or **accept partial** with a reason | Match PDF to dispute by transaction ID; score each option (§5) | `dispute_options[]` |
| 2B | `analyze_receivables` | `list_invoices` (status `SENT`, `UNPAID`, `PARTIALLY_PAID`) | Write a short, personalised reminder per invoice | Days overdue, payment likelihood, expected value (§5) | `invoice_options[]` |
| 3 | `synthesize_plan` | — | One-paragraph plain-English plan summary | Merge, rank by expected cash before deadline, pre-select the smallest set that covers the gap, compute projected balance | `levers[]`, `plan_summary`, `coverage` |
| ⏸ | approval gate | — | — | `interrupt()` returns levers to UI; resumes with approved IDs + any edited messages | `approval` |
| 4 | `execute_plan` | Writes only (§4), approved levers only | — | Run each action once, record success/failure per lever, **never retry a failed write automatically** | `executions[]` |
| 5 | `verify_and_audit` | `get_dispute`, `get_invoice`, `GET` payout batch | Short "what happened" summary | Confirm statuses, update projected balance, persist audit rows | `audit_log[]`, `final_summary` |

Steps 2A and 2B run in parallel and both write to separate state keys, so no merge
conflicts. The supplier payout is always shown as the last lever and must be
approved explicitly.

---

## 4. PayPal API map

| Action | Endpoint | Via | Step |
|--------|----------|-----|------|
| Get token | `POST /v1/oauth2/token` | httpx | all |
| Balance | `GET /v1/reporting/balances` | httpx | 1 |
| List / get disputes | `GET /v1/customer/disputes[/{id}]` | toolkit `list_disputes`, `get_dispute` | 2A, 5 |
| List / get invoices | `GET /v2/invoicing/invoices[/{id}]` | toolkit `list_invoices`, `get_invoice` | 2B, 5 |
| **Contest dispute** | `POST /v1/customer/disputes/{id}/provide-evidence` | httpx (multipart; PDF + tracking note) | 4 |
| Add tracking to sale | `POST /v1/shipping/trackers-batch` | toolkit `create_shipment_tracking` | 4 |
| **Accept partial claim** | `POST /v1/customer/disputes/{id}/accept-claim` (with `refund_amount`) | toolkit `accept_dispute_claim` | 4 |
| **Invoice reminder** | `POST /v2/invoicing/invoices/{id}/remind` | toolkit `send_invoice_reminder` | 4 |
| Invoice QR code | `POST /v2/invoicing/invoices/{id}/generate-qr-code` | toolkit `generate_invoice_qr_code` | 4 |
| **Pay supplier** | `POST /v1/payments/payouts` | httpx | 4 |
| Check payout | `GET /v1/payments/payouts/{batch_id}` | httpx | 5 |
| *(demo only)* Resolve dispute | Sandbox-only dispute settle endpoint | httpx | demo script |

**Bold** = changes something in PayPal; only runs after approval.

The supplier is paid with **Payouts**, not Orders: Orders are for the merchant
*receiving* money; Payouts send money *out* of the merchant's balance.

---

## 5. Scoring (deterministic)

Each option gets:

```
expected_cash_by_deadline = amount × p_success × p_before_deadline
```

| Option | `p_success` | `p_before_deadline` |
|--------|-------------|---------------------|
| Contest dispute, tracking shows delivered | 0.85 | 0.6 (PayPal review time) |
| Contest dispute, no delivery proof | 0.30 | 0.6 |
| Accept partial claim (release `amount − refund`) | 1.00 | 1.0 (funds released on acceptance) |
| Invoice reminder, 1–15 days overdue | 0.60 | 0.7 |
| Invoice reminder, 16–45 days overdue | 0.40 | 0.5 |
| Invoice reminder, 45+ days overdue | 0.15 | 0.3 |

These numbers live in one config table (`scoring.py`) and are shown in the UI as
"assumptions", so judges can see they are rules, not AI guesses.

Plan selection: sort by `expected_cash_by_deadline` (ties → higher `p_success`),
then pre-select options until `Σ expected ≥ gap × 1.1`. The merchant can change
the selection in the grid.

---

## 6. Where the AI is used (and how it's kept in check)

| Task | Step | Output schema (Pydantic) | Guardrail |
|------|------|--------------------------|-----------|
| Read merchant request | 1 | `Goal{amount, currency, deadline, supplier_name, supplier_email}` | Amount > 0; deadline in the future; currency is USD |
| Read courier PDF | 2A | `Evidence{tracking_number, carrier, delivered_on, recipient_name}` | Tracking no. format check; `delivered_on` ≤ today |
| Choose dispute strategy | 2A | `DisputeDecision{action: contest\|accept_partial, refund_amount?, reason}` | `refund_amount` ≤ disputed amount; reason required |
| Write reminder text | 2B | `Reminder{subject, body}` | ≤ 600 chars; no amounts that differ from the invoice |
| Plan / result summaries | 3, 5 | plain text | Numbers are inserted by Python, not generated |

Model: Claude via `langchain-anthropic`, model name from `LLM_MODEL`.
If an AI call fails, the step falls back to a safe default (contest only if
evidence was extracted; generic reminder text) and flags it in the UI.

---

## 7. State

```python
class Lever(TypedDict):
    id: str                    # "DISP-<id>" | "INV-<id>" | "PAYOUT-SUPPLIER"
    kind: Literal["dispute_contest", "dispute_accept", "invoice_remind", "supplier_payout"]
    paypal_ref: str            # dispute_id / invoice_id
    counterparty: str
    amount_usd: float
    expected_usd: float
    p_success: float
    p_before_deadline: float
    ai_reason: str
    draft_message: str | None
    selected: bool
    status: Literal["proposed", "approved", "executed", "failed", "skipped"]

class TreasuryState(TypedDict):
    thread_id: str
    merchant_query: str
    goal: Goal
    available_usd: float
    gap_usd: float
    dispute_options: list[Lever]
    invoice_options: list[Lever]
    levers: list[Lever]
    plan_summary: str
    approval: dict | None      # {approved_ids, edited_messages}
    executions: list[dict]
    audit_log: list[dict]
    final_summary: str
    warnings: list[str]
```

---

## 8. API contract

**`POST /api/treasury/plan`**
```json
// request
{ "merchant_query": "I need $1,800 by Friday to pay Apex Roasters (apex@example.com)." }
// response
{ "thread_id": "…", "status": "PENDING_REVIEW",
  "goal": {…}, "available_usd": 412.50, "gap_usd": 1387.50,
  "levers": [ Lever, … ], "plan_summary": "…", "warnings": [] }
```

**`POST /api/treasury/execute`**
```json
// request
{ "thread_id": "…", "approved_lever_ids": ["DISP-PP-D-123", "INV-0042", "PAYOUT-SUPPLIER"],
  "edited_messages": { "INV-0042": "…" } }
// response
{ "status": "COMPLETED" | "PARTIAL",
  "levers": [ … with status ],
  "audit_log": [ { "lever_id", "action", "paypal_id", "http_status", "at" } ],
  "projected_balance_usd": 1840.00, "final_summary": "…" }
```

**`GET /api/treasury/runs/{thread_id}`** — current state (used to restore the UI after a refresh).

Approval resumes the graph with `Command(resume={...})`. Calling `execute` twice for
the same thread returns the stored result instead of running writes again.

---

## 9. Persistence

| What | Where |
|------|-------|
| Graph checkpoints | `SqliteSaver` (`langgraph-checkpoint-sqlite`) by default; `PostgresSaver` when `DATABASE_URL` starts with `postgresql://` |
| Audit log | `audit_log` table in the same database (append-only) |

The app runs with zero setup on SQLite; Postgres is optional.

---

## 10. Frontend

| Area | Contents |
|------|----------|
| Cash-gap header | Target, available now, gap, expected recovery, projected balance, all in USD |
| Options grid (AG Grid) | One row per lever: type, counterparty, amount, p(success), p(before deadline), expected cash, AI reason; checkbox to select; running total vs gap |
| Approval panel | Selected actions in plain language, editable reminder/evidence text, "Approve & execute" button |
| Audit log | After execution: each PayPal call, its returned ID, status, time |

---

## 11. Sandbox setup (before recording)

1. App linked to a **US business** sandbox account; features on: Transaction Search,
   Invoicing, Payouts, Customer disputes.
2. `python -m app.seed.seed_sandbox` creates and sends 4–5 invoices with mixed due
   dates to the personal sandbox account.
3. As the **personal** account: pay the business account 3 times, then open
   3 disputes in the Resolution Center (item not received ×2, not as described ×1).
4. Put matching courier PDFs in `backend/demo_assets/` (one with delivery proof,
   one without).
5. Do steps 2–4 at least a few hours before recording so everything is indexed.

---

## 12. Code layout

```text
backend/app/
├── main.py                 # FastAPI routes
├── config.py               # env settings, FX rate
├── graph/
│   ├── state.py            # TypedDicts above
│   ├── nodes.py            # steps 1–5
│   ├── scoring.py          # probability table + ranking (pure functions)
│   ├── llm.py              # Claude calls with Pydantic schemas
│   └── workflow.py         # StateGraph, parallel branches, interrupt, checkpointer
├── tools/
│   └── paypal_client.py    # toolkit wrapper + httpx calls, request IDs
├── db/
│   └── audit.py            # audit log table
├── seed/
│   └── seed_sandbox.py
└── demo_assets/            # courier PDFs
frontend/src/
├── App.tsx
├── api.ts
└── components/
    ├── GapHeader.tsx
    ├── LiquidityGrid.tsx   # AG Grid
    ├── ApprovalCard.tsx
    └── AuditLog.tsx
```

---

## 13. Out of scope (future work)

Live accounts, multi-merchant auth, real FX rates, webhooks for dispute/invoice
updates, background scheduling, learned (not table-based) probabilities.
