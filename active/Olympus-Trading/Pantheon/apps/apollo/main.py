from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import threading
import uvicorn

from core.brain import chat
from core.memory import (
    initialize_database,
    get_recent_conversations,
    get_decisions,
    get_active_patterns,
    clear_session_rules,
)
from core.mind import get_vault_snapshot
from pantheon.api import (
    get_activity_snapshot,
    get_blackbook_snapshot,
    get_doctor_snapshot,
    get_maridian_snapshot,
    get_olympus_snapshot,
    get_overview_snapshot,
    reason,
)
from pantheon.services import blackbook, maridian


def _start_brief_scheduler_thread():
    try:
        from agents.brief import start_brief_scheduler
        start_brief_scheduler()
    except Exception:
        return


def _start_trigger_scheduler():
    try:
        import schedule
        import time
        from core.triggers import run_all_triggers
        from pantheon.services import maridian as _maridian
        schedule.every(1).hours.do(run_all_triggers)
        schedule.every().day.at("06:00").do(_maridian.run_cycle_async)
        while True:
            schedule.run_pending()
            time.sleep(60)
    except Exception:
        return


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    clear_session_rules()
    threading.Thread(target=_start_brief_scheduler_thread, daemon=True).start()
    threading.Thread(target=_start_trigger_scheduler, daemon=True).start()
    yield


app = FastAPI(title="Apollo", version="3.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

conversation_history = []


class ChatRequest(BaseModel):
    message: str
    reset_history: Optional[bool] = False
    channel: Optional[str] = "ui"


class ChatResponse(BaseModel):
    response: str
    history_length: int


class ReasonResponse(BaseModel):
    response: str
    sources: list[dict]
    tools_used: list[str]
    actions_taken: list[str]
    actions_proposed: list[str]
    provider_used: str
    model_used: str
    grounded: bool
    degraded: bool
    degraded_reason: str
    latency_ms: int | None = None
    audit_id: str


class QuickExpenseRequest(BaseModel):
    amount: float
    description: str
    category: str = "Other"
    account: str
    date: Optional[str] = None
    notes: str = ""


class QuickIncomeRequest(BaseModel):
    amount: float
    description: str
    account: str
    date: Optional[str] = None
    notes: str = ""


class JournalEntryRequest(BaseModel):
    entry_date: Optional[str] = None
    tag: str = "General"
    body: str


class SettingsRequest(BaseModel):
    settings: dict


class TransactionRequest(BaseModel):
    amount: float
    description: str
    category: str = "Other"
    account: str
    tx_type: str = "expense"
    to_account: Optional[str] = None
    date: Optional[str] = None
    notes: str = ""


class HoldingRequest(BaseModel):
    symbol: str
    display_name: str
    asset_type: str = "stock"
    account: str
    amount_invested: float
    quantity: float
    avg_price: float
    coingecko_id: str = ""


class HoldingUpdateRequest(BaseModel):
    amount_invested: float
    quantity: float
    avg_price: float


class AllocationRequest(BaseModel):
    payload: dict


class AdvisorRequest(BaseModel):
    message: str


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    global conversation_history
    if request.reset_history:
        conversation_history = []
    response, conversation_history = chat(
        request.message, conversation_history, channel=request.channel
    )
    return ChatResponse(response=response, history_length=len(conversation_history))


@app.post("/reason", response_model=ReasonResponse)
async def reason_endpoint(request: ChatRequest):
    result = reason(request.message, conversation_history=conversation_history, channel=request.channel)
    return ReasonResponse(**result.to_dict())


@app.post("/voice")
async def voice_endpoint(audio: UploadFile = File(...)):
    global conversation_history
    from voice.transcriber import transcribe_bytes

    audio_bytes = await audio.read()
    extension = audio.filename.split(".")[-1] if audio.filename else "wav"
    transcribed = transcribe_bytes(audio_bytes, extension)
    if not transcribed:
        raise HTTPException(status_code=400, detail="Could not transcribe audio")
    response, conversation_history = chat(transcribed, conversation_history, channel="voice")
    return {"transcription": transcribed, "response": response}


@app.post("/brief")
async def trigger_brief():
    from agents.brief import run_brief

    return {"brief": run_brief()}


@app.get("/history")
async def get_history():
    return get_recent_conversations(limit=50)


@app.get("/decisions")
async def get_all_decisions():
    return get_decisions(limit=100)


@app.get("/patterns")
async def get_patterns():
    return get_active_patterns()


@app.get("/vault")
async def get_vault():
    return get_vault_snapshot()


@app.post("/reindex")
async def reindex():
    from search.indexer import index_meridian_vault, index_decisions

    vault_result = index_meridian_vault()
    index_decisions()
    return {"vault": vault_result, "decisions": "indexed"}


@app.post("/triggers/run")
async def run_triggers():
    from core.triggers import run_all_triggers

    run_all_triggers()
    return {"status": "Triggers evaluated"}


@app.get("/pantheon/overview")
async def pantheon_overview():
    return get_overview_snapshot()


@app.get("/pantheon/subsystems")
async def pantheon_subsystems():
    overview = get_overview_snapshot()
    return overview["health"]


@app.get("/pantheon/blackbook")
async def pantheon_blackbook():
    return get_blackbook_snapshot()


@app.post("/pantheon/blackbook/expense")
async def pantheon_blackbook_expense(payload: QuickExpenseRequest):
    result = blackbook.add_expense(
        amount=payload.amount,
        description=payload.description,
        category=payload.category,
        account_name=payload.account,
        tx_date=payload.date,
        notes=payload.notes,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unable to add expense"))
    return get_blackbook_snapshot()


@app.post("/pantheon/blackbook/income")
async def pantheon_blackbook_income(payload: QuickIncomeRequest):
    result = blackbook.add_income(
        amount=payload.amount,
        description=payload.description,
        account_name=payload.account,
        tx_date=payload.date,
        notes=payload.notes,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unable to add income"))
    return get_blackbook_snapshot()


@app.get("/pantheon/blackbook/holdings")
async def pantheon_blackbook_holdings():
    return blackbook.get_holdings_snapshot()


@app.post("/pantheon/blackbook/accounts/{account_id}/balance")
async def pantheon_blackbook_set_balance(account_id: int, payload: dict):
    override = payload.get("override")
    result = blackbook.set_balance_override(account_id, float(override) if override is not None else None)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update balance"))
    return get_blackbook_snapshot()


@app.post("/pantheon/blackbook/holdings/refresh")
async def pantheon_blackbook_holdings_refresh():
    from pantheon.services.blackbook import _queries
    from datetime import datetime
    queries = _queries()
    queries.set_settings({"last_price_refresh_at": datetime.now().isoformat(timespec="seconds")})
    return blackbook.get_holdings_snapshot()


@app.get("/pantheon/blackbook/journal")
async def pantheon_blackbook_journal(tag: str = "All", limit: int = 50):
    return blackbook.get_journal_entries(tag_filter=tag, limit=limit)


@app.post("/pantheon/blackbook/journal")
async def pantheon_blackbook_journal_create(payload: JournalEntryRequest):
    result = blackbook.create_journal_entry(
        entry_date=payload.entry_date,
        tag=payload.tag,
        body=payload.body,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to save entry"))
    return result


@app.delete("/pantheon/blackbook/journal/{entry_id}")
async def pantheon_blackbook_journal_delete(entry_id: int):
    result = blackbook.delete_journal_entry(entry_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to delete entry"))
    return result


@app.get("/pantheon/blackbook/settings")
async def pantheon_blackbook_settings():
    return blackbook.get_bb_settings()


@app.post("/pantheon/blackbook/settings")
async def pantheon_blackbook_settings_save(payload: SettingsRequest):
    result = blackbook.save_bb_settings(payload.settings)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to save settings"))
    return result


@app.get("/pantheon/blackbook/transactions")
async def pantheon_blackbook_transactions(limit: int = 200):
    return {"transactions": blackbook.list_transactions(limit=limit)}


@app.post("/pantheon/blackbook/transactions")
async def pantheon_blackbook_transaction_create(payload: TransactionRequest):
    result = blackbook.add_transaction(
        tx_date=payload.date,
        description=payload.description,
        category=payload.category,
        amount=payload.amount,
        account_name=payload.account,
        tx_type=payload.tx_type,
        to_account_name=payload.to_account,
        notes=payload.notes,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to add transaction"))
    return get_blackbook_snapshot()


@app.delete("/pantheon/blackbook/transactions/{tx_id}")
async def pantheon_blackbook_transaction_delete(tx_id: int):
    result = blackbook.delete_transaction(tx_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to delete transaction"))
    return get_blackbook_snapshot()


@app.post("/pantheon/blackbook/holdings")
async def pantheon_blackbook_holding_create(payload: HoldingRequest):
    result = blackbook.add_holding(
        symbol=payload.symbol,
        display_name=payload.display_name,
        asset_type=payload.asset_type,
        account_name=payload.account,
        amount_invested=payload.amount_invested,
        quantity=payload.quantity,
        avg_price=payload.avg_price,
        coingecko_id=payload.coingecko_id,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to add holding"))
    return blackbook.get_holdings_snapshot()


@app.put("/pantheon/blackbook/holdings/{holding_id}")
async def pantheon_blackbook_holding_update(holding_id: int, payload: HoldingUpdateRequest):
    result = blackbook.update_holding(holding_id, payload.amount_invested, payload.quantity, payload.avg_price)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update holding"))
    return blackbook.get_holdings_snapshot()


@app.delete("/pantheon/blackbook/holdings/{holding_id}")
async def pantheon_blackbook_holding_delete(holding_id: int):
    result = blackbook.delete_holding(holding_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to delete holding"))
    return blackbook.get_holdings_snapshot()


@app.get("/pantheon/blackbook/allocation")
async def pantheon_blackbook_allocation(limit: int = 10):
    return {"snapshots": blackbook.list_allocation_snapshots(limit=limit)}


@app.post("/pantheon/blackbook/allocation")
async def pantheon_blackbook_allocation_save(payload: AllocationRequest):
    result = blackbook.save_allocation_snapshot(payload.payload)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to save snapshot"))
    return {"snapshots": blackbook.list_allocation_snapshots()}


@app.get("/pantheon/blackbook/reports")
async def pantheon_blackbook_reports(limit: int = 30):
    return {"reports": blackbook.list_daily_reports(limit=limit)}


@app.delete("/pantheon/blackbook/reports/{report_date}")
async def pantheon_blackbook_report_delete(report_date: str):
    result = blackbook.delete_daily_report(report_date)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to delete report"))
    return {"reports": blackbook.list_daily_reports()}


@app.get("/pantheon/blackbook/agenda")
async def pantheon_blackbook_agenda():
    return blackbook.get_agenda()


@app.post("/pantheon/blackbook/advisor")
async def pantheon_blackbook_advisor(payload: AdvisorRequest):
    result = reason(
        message=payload.message,
        conversation_history=conversation_history,
        channel="blackbook_advisor",
    )
    return {
        "response": result.response,
        "sources": result.sources,
        "audit_id": result.audit_id,
        "snapshot": get_blackbook_snapshot(),
    }


@app.get("/pantheon/blackbook/meridian")
async def pantheon_blackbook_meridian():
    return get_maridian_snapshot()


@app.get("/pantheon/maridian")
async def pantheon_maridian():
    return get_maridian_snapshot()


@app.post("/pantheon/maridian/run-cycle")
async def pantheon_maridian_run_cycle():
    result = maridian.run_cycle()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error") or result.get("stderr") or "Cycle failed")
    return {
        "status": "ok",
        "result": result,
        "snapshot": get_maridian_snapshot(),
    }


@app.post("/pantheon/maridian/run-cycle/async")
async def pantheon_maridian_run_cycle_async():
    result = maridian.run_cycle_async()
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=result.get("error", "Could not start cycle"))
    return {"status": "started"}


@app.get("/pantheon/maridian/cycle/status")
async def pantheon_maridian_cycle_status():
    return maridian.get_cycle_status()


@app.get("/pantheon/olympus")
async def pantheon_olympus():
    return get_olympus_snapshot()


@app.get("/pantheon/activity")
async def pantheon_activity():
    return get_activity_snapshot(limit=12)


@app.get("/pantheon/doctor")
async def pantheon_doctor():
    return get_doctor_snapshot()


@app.get("/agents")
async def get_agents():
    from agents.hub import list_agents

    return list_agents()


@app.post("/agents")
async def create_new_agent(payload: dict):
    from agents.hub import create_agent

    agent_id = create_agent(
        name=payload["name"],
        description=payload["description"],
        system_prompt=payload["system_prompt"],
        schedule_expr=payload.get("schedule", "daily at 09:00"),
        tools_allowed=payload.get("tools", []),
    )
    return {"agent_id": agent_id, "status": "created"}


@app.delete("/agents/{agent_id}")
async def retire_agent_endpoint(agent_id: int):
    from agents.hub import retire_agent

    retire_agent(agent_id)
    return {"status": "retired"}


@app.get("/health")
async def health():
    return {"status": "Apollo is running"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
