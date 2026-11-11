from typing import Annotated, List, Literal, Optional, TypedDict
from operator import add
from pydantic import BaseModel, Field


class DisputeEvidence(BaseModel):
    dispute_id: str
    capture_id: str
    reason: Literal[
        "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
        "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED",
    ]
    status: str
    disputed_amount_usd: float
    carrier_name: Optional[str] = None
    tracking_number: Optional[str] = None
    delivery_status: Optional[Literal["DELIVERED", "IN_TRANSIT", "MISSING"]] = None
    pdf_source_file: Optional[str] = None
    recommended_strategy: Literal[
        "PROVIDE_EVIDENCE",
        "MAKE_PARTIAL_OFFER",
        "ACCEPT_FULL_CLAIM",
    ]
    offer_amount_usd: float = 0.0
    net_cash_unlocked_usd: float = 0.0
    recovery_probability: float = 0.0
    arrives_by_friday: bool = True
    ai_reasoning: str = ""
    drafted_evidence_note: str = ""


class OverdueInvoice(BaseModel):
    invoice_id: str
    invoice_number: str
    customer_name: str
    customer_email: str
    amount_due_usd: float
    days_overdue: int
    historical_reliability: float = Field(ge=0.0, le=1.0)
    arrives_by_friday: bool = False
    ai_reasoning: str = ""
    drafted_reminder_note: str = ""


class LiquidityLever(BaseModel):
    lever_id: str
    source_type: Literal["PAYPAL_DISPUTE_HOLD", "OVERDUE_PAYPAL_INVOICE"]
    counterparty: str
    gross_amount_usd: float
    gross_amount_inr: float
    net_unlockable_usd: float
    net_unlockable_inr: float
    recovery_probability: float
    expected_recovery_usd: float
    expected_recovery_inr: float
    available_by_friday_usd: float
    available_by_friday_inr: float
    est_settlement_hours: int
    priority_score: float
    paypal_action: str
    ai_reasoning: str
    drafted_message: str
    status: Literal["PROPOSED", "APPROVED", "EXECUTED", "SKIPPED"] = "PROPOSED"


class SupplierObligation(BaseModel):
    supplier_name: str
    supplier_paypal_email: str
    purchase_order_id: str
    amount_required_usd: float
    amount_required_inr: float
    due_description: str


class AuditLogEntry(BaseModel):
    timestamp: str
    step_name: str
    paypal_operation: str
    reference_id: str
    verified_status: str
    cash_impact_usd: float
    cash_impact_inr: float
    details: str


class TreasuryState(TypedDict):
    # 1. Diagnose cash gap
    merchant_query: str
    usd_to_inr_rate: float
    available_balance_usd: float
    available_balance_inr: float
    target_obligation: SupplierObligation
    initial_gap_usd: float
    initial_gap_inr: float

    # 2. Parallel analysis outputs
    open_disputes: List[DisputeEvidence]
    overdue_invoices: List[OverdueInvoice]

    # 3. Synthesize plan outputs (feeds AG Grid)
    ranked_options: List[LiquidityLever]
    immediate_friday_cash_usd: float
    immediate_friday_cash_inr: float
    expected_total_recovery_usd: float
    expected_total_recovery_inr: float
    projected_friday_balance_usd: float
    projected_friday_balance_inr: float

    # 4. Merchant approval gate
    approval_status: Literal["PENDING_APPROVAL", "APPROVED", "REJECTED"]
    approved_lever_ids: List[str]

    # 5. Execute & Verify outputs
    audit_log: Annotated[List[AuditLogEntry], add]
    payout_batch_id: Optional[str]
    payout_status: Literal["NOT_STARTED", "SUCCESS", "PENDING", "SKIPPED_SHORTFALL"]
    final_summary: Optional[str]