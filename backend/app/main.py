import uuid
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.types import Command
from app.graph.workflow import treasury_graph

app = FastAPI(title="PayFlow Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanRequest(BaseModel):
    merchant_query: str = "I need ₹1,50,000 by Friday to pay our wholesale coffee supplier, Apex Roasters."
    usd_to_inr_rate: float = 84.0


class ExecuteRequest(BaseModel):
    thread_id: str
    approved_lever_ids: List[str]


@app.post("/plan")
def create_treasury_plan(req: PlanRequest):
    thread_id = f"run-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "merchant_query": req.merchant_query,
        "usd_to_inr_rate": req.usd_to_inr_rate,
        "audit_log": [],
    }

    treasury_graph.invoke(initial_state, config=config)
    snapshot = treasury_graph.get_state(config)
    return {"thread_id": thread_id, "state": snapshot.values}


@app.post("/execute")
def execute_approved_plan(req: ExecuteRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    snapshot = treasury_graph.get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="Run thread_id not found")

    treasury_graph.invoke(
        Command(resume={"approved_lever_ids": req.approved_lever_ids}),
        config=config,
    )
    final_snapshot = treasury_graph.get_state(config)
    return {"thread_id": req.thread_id, "state": final_snapshot.values}


@app.get("/runs/{thread_id}")
def get_run_state(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = treasury_graph.get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail="Run thread_id not found")
    return {"thread_id": thread_id, "state": snapshot.values}