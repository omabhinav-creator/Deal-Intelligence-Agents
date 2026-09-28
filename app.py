"""Small HTTP API for the DealMind intelligence services."""

from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from Hindsight.ai.agent import (
    InteractionProcessingError,
    process_sales_interaction,
)
from Hindsight.ai.deal_autopsy import DealAutopsyAnalyzer, DealAutopsyError
from Hindsight.ai.deal_brief import DealBriefError, DealBriefGenerator
from Hindsight.ai.deal_changes import DealChangeAnalyzer, DealChangeError
from Hindsight.ai.recommendations import RecommendationError, RecommendationExplainer
from Hindsight.ai.similar_deals import SimilarDealsError, SimilarDealsFinder
from Hindsight.memory.learning import (
    DealOutcome,
    OutcomeLearningError,
    OutcomeLearningService,
)


class InteractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    notes: str = Field(min_length=1)
    interaction_date: datetime | None = None
    source: str | None = Field(default="meeting_notes", min_length=1)
    interaction_id: str | None = Field(default=None, min_length=1)
    company: str | None = Field(default=None, min_length=1)
    stakeholder: str | None = Field(default=None, min_length=1)


class WhyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: str = Field(min_length=1)


class OutcomeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    outcome: DealOutcome
    company: str | None = Field(default=None, min_length=1)
    outcome_date: datetime | None = None
    interaction_id: str | None = Field(default=None, min_length=1)


class AutopsyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    outcome: DealOutcome


class InteractionResponse(BaseModel):
    deal_id: str
    extraction: Any
    memories: list[Any]
    retained_memory_count: int


app = FastAPI(title="DealMind API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


_SERVICE_ERRORS = (
    InteractionProcessingError,
    DealBriefError,
    DealChangeError,
    SimilarDealsError,
    RecommendationError,
    OutcomeLearningError,
    DealAutopsyError,
)


async def service_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


for _service_error in _SERVICE_ERRORS:
    app.add_exception_handler(_service_error, service_error_handler)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "The DealMind service could not complete the request."},
    )


@app.post("/api/deals/{deal_id}/interactions", response_model=InteractionResponse)
def ingest_interaction(deal_id: str, payload: InteractionRequest) -> InteractionResponse:
    result = process_sales_interaction(
        deal_id=deal_id,
        meeting_notes=payload.notes,
        customer_company=payload.company,
        interaction_date=payload.interaction_date,
        interaction_id=payload.interaction_id,
        interaction_source=payload.source,
    )
    return InteractionResponse(
        deal_id=deal_id,
        extraction=result.extraction,
        memories=list(result.memories),
        retained_memory_count=len(result.retain_responses),
    )


@app.get("/api/deals/{deal_id}/brief")
def deal_brief(deal_id: str) -> Any:
    return DealBriefGenerator().generate(deal_id)


@app.get("/api/deals/{deal_id}/changes")
def deal_changes(deal_id: str) -> Any:
    return DealChangeAnalyzer().analyze(deal_id)


@app.get("/api/deals/{deal_id}/similar")
def similar_deals(deal_id: str) -> Any:
    return SimilarDealsFinder().find_similar_deals(deal_id)


@app.post("/api/deals/{deal_id}/why")
def explain_recommendation(deal_id: str, payload: WhyRequest) -> Any:
    return RecommendationExplainer().explain(deal_id, payload.action)


@app.post("/api/deals/{deal_id}/outcome")
def learn_outcome(deal_id: str, payload: OutcomeRequest) -> Any:
    return OutcomeLearningService().learn_from_outcome(
        deal_id=deal_id,
        outcome=payload.outcome,
        customer_name=payload.company,
        outcome_date=payload.outcome_date,
        interaction_id=payload.interaction_id,
    )


@app.post("/api/deals/{deal_id}/autopsy")
def deal_autopsy(deal_id: str, payload: AutopsyRequest) -> Any:
    return DealAutopsyAnalyzer().analyze(deal_id, payload.outcome)
