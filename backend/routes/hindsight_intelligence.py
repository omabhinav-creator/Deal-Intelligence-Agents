"""HTTP routes for DealMind's existing Hindsight-backed intelligence services."""

from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from typing import Any
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from backend.database import get_database
from backend.auth import get_current_user
from backend.memory.hindsight_client import HindsightMemoryClient
from backend.memory.hindsight_client import HindsightMemoryClientError
from Hindsight.ai.deal_brief import memory_belongs_to_deal
from backend.schemas import InteractionCreate as MongoInteractionCreate
from backend.routes.interactions import create_interaction as create_mongo_interaction

from Hindsight.ai.agent import InteractionProcessingError, process_sales_interaction
from Hindsight.ai.deal_autopsy import DealAutopsyAnalyzer, DealAutopsyError
from Hindsight.ai.deal_brief import DealBriefError, DealBriefGenerator
from Hindsight.ai.deal_changes import DealChangeAnalyzer, DealChangeError
from Hindsight.ai.recommendations import RecommendationError, RecommendationExplainer
from Hindsight.ai.similar_deals import SimilarDealsError, SimilarDealsFinder
from Hindsight.ai.intelligence import get_next_best_action
from Hindsight.memory.learning import DealOutcome, OutcomeLearningError, OutcomeLearningService

router = APIRouter(
    prefix="/api/deals/{deal_id}",
    tags=["Hindsight intelligence"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger(__name__)


@contextmanager
def _managed_memory_client():
    client = HindsightMemoryClient()
    try:
        yield client
    finally:
        try:
            client.close()
        except HindsightMemoryClientError:
            pass


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


@router.get("/memories")
def deal_memories(deal_id: str) -> dict[str, Any]:
    """Recall only Hindsight records explicitly associated with this deal."""
    with _managed_memory_client() as client:
        recalled = client.recall_memory(
            f"Retrieve the interaction history, concerns, stakeholders, competitors, "
            f"pricing, requirements, risks, commitments, and lessons for deal {deal_id}.",
            tags=[f"deal:{deal_id}"],
            max_tokens=4096,
        )
    memories = []
    for memory in recalled.results:
        if not memory_belongs_to_deal(memory, deal_id):
            continue
        metadata = memory.metadata or {}
        memories.append({
            "memory_id": memory.id,
            "deal_id": deal_id,
            "content": memory.text,
            "memory_type": metadata.get("memory_type") or memory.type,
            "interaction_date": (
                metadata.get("interaction_date")
                or memory.occurred_start
                or memory.mentioned_at
            ),
            "interaction_source": metadata.get("interaction_source"),
            "interaction_id": metadata.get("interaction_id") or memory.document_id,
            "stakeholder_name": metadata.get("stakeholder_name"),
            "status": metadata.get("status"),
            "tags": memory.tags or [],
        })
    return {"deal_id": deal_id, "memories": memories, "empty": not memories}


SERVICE_ERRORS = (
    InteractionProcessingError, DealBriefError, DealChangeError, SimilarDealsError,
    RecommendationError, OutcomeLearningError, DealAutopsyError,
    HindsightMemoryClientError,
)


@router.post("/interactions")
async def ingest_interaction(deal_id: str, request: Request, response: Response) -> Any:
    """Accept the original Hindsight and MongoDB interaction payload contracts."""
    try:
        payload_data = await request.json()
    except ValueError as exc:
        raise RequestValidationError([]) from exc

    if "notes" not in payload_data:
        try:
            mongo_payload = MongoInteractionCreate.model_validate(payload_data)
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc
        database = await get_database()
        created = await create_mongo_interaction(deal_id, mongo_payload, database)
        response.status_code = 201
        return created

    try:
        payload = InteractionRequest.model_validate(payload_data)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    interaction_date = payload.interaction_date or datetime.now(timezone.utc)
    interaction_id = payload.interaction_id or str(uuid4())

    def process_interaction():
        with _managed_memory_client() as client:
            return process_sales_interaction(
                deal_id=deal_id,
                meeting_notes=payload.notes,
                customer_company=payload.company,
                interaction_date=interaction_date,
                interaction_id=interaction_id,
                interaction_source=payload.source,
                memory_client=client,
            )

    result = await run_in_threadpool(process_interaction)
    database = await get_database()
    await database["interactions"].insert_one(
        {
            "deal_id": deal_id,
            "meeting_date": interaction_date,
            "content": payload.notes,
            "key_takeaway": payload.notes,
            "interaction_id": interaction_id,
            "interaction_source": payload.source,
            "extraction": result.extraction.model_dump(mode="json"),
        }
    )
    return InteractionResponse(
        deal_id=deal_id, extraction=result.extraction, memories=list(result.memories),
        retained_memory_count=len(result.retain_responses),
    )


@router.get("/brief")
def deal_brief(deal_id: str) -> Any:
    with _managed_memory_client() as client:
        try:
            return DealBriefGenerator(memory_client=client).generate(deal_id)
        except DealBriefError:
            logger.exception("Deal Brief generation failed for deal %s", deal_id)
            raise


@router.get("/changes")
def deal_changes(deal_id: str) -> Any:
    with _managed_memory_client() as client:
        return DealChangeAnalyzer(memory_client=client).analyze(deal_id)


@router.get("/similar")
def similar_deals(deal_id: str) -> Any:
    with _managed_memory_client() as client:
        return SimilarDealsFinder(memory_client=client).find_similar_deals(deal_id)


@router.get("/recommendations")
def recommendations(deal_id: str) -> Any:
    """Return existing evidence-backed next-best-action recommendations."""
    with _managed_memory_client() as client:
        return get_next_best_action(deal_id, memory_client=client)


@router.post("/why")
def explain_recommendation(deal_id: str, payload: WhyRequest) -> Any:
    with _managed_memory_client() as client:
        return RecommendationExplainer(memory_client=client).explain(deal_id, payload.action)


@router.post("/outcome")
async def learn_outcome(deal_id: str, payload: OutcomeRequest) -> Any:
    def learn():
        with _managed_memory_client() as client:
            return OutcomeLearningService(memory_client=client).learn_from_outcome(
                deal_id=deal_id,
                outcome=payload.outcome,
                customer_name=payload.company,
                outcome_date=payload.outcome_date,
                interaction_id=payload.interaction_id,
            )

    result = await run_in_threadpool(learn)
    if ObjectId.is_valid(deal_id):
        database = await get_database()
        await database["deals"].update_one(
            {"_id": ObjectId(deal_id)},
            {
                "$set": {
                    "status": payload.outcome.value,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
    return result


@router.post("/autopsy")
def deal_autopsy(deal_id: str, payload: AutopsyRequest) -> Any:
    with _managed_memory_client() as client:
        return DealAutopsyAnalyzer(memory_client=client).analyze(deal_id, payload.outcome)
