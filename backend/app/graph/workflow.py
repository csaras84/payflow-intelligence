from typing import Any, Dict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import interrupt
from app.graph.state import TreasuryState
from app.graph.nodes import (
    diagnose_cash_gap,
    analyze_disputes,
    analyze_invoices,
    synthesize_plan,
    execute_plan,
    verify_and_audit,
)


def merchant_approval(state: TreasuryState) -> Dict[str, Any]:
    """Pauses execution using LangGraph interrupt() until the merchant approves selected actions."""
    decision = interrupt(
        {
            "thread_status": "WAITING_FOR_MERCHANT_APPROVAL",
            "initial_gap_usd": state["initial_gap_usd"],
            "initial_gap_inr": state["initial_gap_inr"],
            "immediate_friday_cash_usd": state["immediate_friday_cash_usd"],
            "immediate_friday_cash_inr": state["immediate_friday_cash_inr"],
            "ranked_options_count": len(state.get("ranked_options", [])),
        }
    )
    approved_ids = decision.get("approved_lever_ids", [])
    return {
        "approval_status": "APPROVED" if approved_ids else "REJECTED",
        "approved_lever_ids": approved_ids,
    }


def build_treasury_graph():
    builder = StateGraph(TreasuryState)

    builder.add_node("diagnose_cash_gap", diagnose_cash_gap)
    builder.add_node("analyze_disputes", analyze_disputes)
    builder.add_node("analyze_invoices", analyze_invoices)
    builder.add_node("synthesize_plan", synthesize_plan)
    builder.add_node("merchant_approval", merchant_approval)
    builder.add_node("execute_plan", execute_plan)
    builder.add_node("verify_and_audit", verify_and_audit)

    # Parallel fan-out & fan-in matching the architecture diagram
    builder.add_edge(START, "diagnose_cash_gap")
    builder.add_edge("diagnose_cash_gap", "analyze_disputes")
    builder.add_edge("diagnose_cash_gap", "analyze_invoices")
    builder.add_edge("analyze_disputes", "synthesize_plan")
    builder.add_edge("analyze_invoices", "synthesize_plan")
    builder.add_edge("synthesize_plan", "merchant_approval")
    builder.add_edge("merchant_approval", "execute_plan")
    builder.add_edge("execute_plan", "verify_and_audit")
    builder.add_edge("verify_and_audit", END)

    # Allow LangGraph to restore our own Pydantic state classes from checkpoints
    # (LangGraph 1.2+ warns on unregistered types and will block them in future).
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("app.graph.state", "SupplierObligation"),
            ("app.graph.state", "DisputeEvidence"),
            ("app.graph.state", "OverdueInvoice"),
            ("app.graph.state", "LiquidityLever"),
            ("app.graph.state", "AuditLogEntry"),
        ]
    )
    checkpointer = MemorySaver(serde=serde)
    return builder.compile(checkpointer=checkpointer)


treasury_graph = build_treasury_graph()