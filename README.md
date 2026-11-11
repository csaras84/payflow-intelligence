# PayFlow Intelligence

**Autonomous Working-Capital & Dispute-Resolution Agent built on PayPal and LangGraph.**

PayFlow Intelligence helps small and medium merchants solve acute cash-flow shortfalls by treating **PayPal dispute resolution** and **overdue invoice recovery** as unified liquidity levers. Instead of acting as a passive chatbot, the agent diagnoses a merchant's working-capital gap, unlocks trapped funds across frozen PayPal disputes and unpaid invoices, pauses for human-in-the-loop approval, and executes outbound supplier payments in the PayPal Sandbox.

## Key Capabilities

1. **Working-Capital Gap Diagnosis:** Queries merchant balance, transaction history, and pending obligations to compute the exact liquidity shortfall required to fund an upcoming supplier payout.
2. **Dispute Unfreezing:** Inspects open PayPal buyer disputes and extracts delivery proof from merchant courier PDFs. An LLM (Azure OpenAI GPT-4.1 mini) recommends a strategy per dispute: contest it with proof of fulfillment (`POST /v1/customer/disputes/{id}/provide-evidence`, plus carrier tracking via `POST /v1/shipping/trackers-batch`), or settle a quality complaint with a partial refund offer (`POST /v1/customer/disputes/{id}/make-offer`) to release the rest of the held funds sooner. Each option is scored on expected cash recovered before the deadline.
3. **Receivables Acceleration:** Ranks unpaid PayPal invoices by expected yield and dispatches targeted reminders (`send_invoice_reminder`) with instant-settlement QR codes (`generate_invoice_qr_code`).
4. **Human-in-the-Loop Treasury Execution:** Uses LangGraph `interrupt()` checkpoints to present a single approval card showing the net USD cash impact before paying the supplier via PayPal Payouts in the Sandbox.

## System Architecture

![PayFlow Intelligence architecture](docs/architecture.svg)

Teal steps only read from PayPal; coral steps change PayPal and run only after the merchant approves. Full design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).


- **Orchestration:** Python, LangGraph (`StateGraph` with persistent checkpointing)
- **LLM Reasoning:** Azure OpenAI GPT-4.1 mini via LangChain (`AzureChatOpenAI`, structured outputs); Anthropic Claude supported as an alternative
- **Payment & Commerce Execution:** PayPal Agent Toolkit (`paypal-agent-toolkit`) & PayPal REST APIs (Sandbox)
- **Backend API & Audit Store:** FastAPI, SQLite (PostgreSQL optional)
- **Frontend Command Center:** React, TypeScript, AG Grid

## Repository Structure

- `backend/` — FastAPI server, LangGraph treasury state machine, PayPal Agent Toolkit bindings, and Sandbox seeding scripts
- `frontend/` — React + AG Grid working-capital dashboard and Human-in-the-Loop approval interface
- `LICENSE` — MIT Open Source License

## Prerequisites

- Python 3.11+
- Node.js 20+
- PayPal Developer Account (Sandbox Client ID and Secret)
- PostgreSQL 15+ (optional; SQLite is used by default, no setup needed)

## Local Setup Instructions

### 1. Clone and Configure Environment

```cmd
git clone https://github.com/csaras84/payflow-intelligence.git
cd payflow-intelligence
copy .env.example .env
```

Update `.env` with your PayPal Sandbox credentials and LLM API keys:

```env
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
PAYPAL_ENVIRONMENT=SANDBOX
AZURE_OPENAI_API_KEY=your_azure_openai_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_API_VERSION=2024-10-21
# Optional: leave unset to use SQLite
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/payflow
```

### 2. Backend Setup (Windows Command Prompt)

```cmd
cd backend
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Seed PayPal Sandbox Demo State

```cmd
cd backend
venv\Scripts\activate.bat
python -m app.seed.seed_sandbox
```

### 4. Frontend Setup

```cmd
cd frontend
npm install
npm run dev
```

## License

Distributed under the MIT License. See `LICENSE` for full details.
