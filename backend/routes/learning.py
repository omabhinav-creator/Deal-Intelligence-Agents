"""Authenticated historical learning data backed by Hindsight recall."""

from typing import Any

from fastapi import APIRouter, Depends

from backend.auth import get_current_user
from backend.memory.hindsight_client import HindsightMemoryClient, HindsightMemoryClientError
from Hindsight.ai.intelligence import analyze_patterns


router = APIRouter(
    prefix="/api/learning",
    tags=["learning"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
def learning_summary() -> dict[str, Any]:
    client = HindsightMemoryClient()
    try:
        patterns = analyze_patterns(client)
        recall = client.recall_memory(
            "Retrieve explicit deal outcomes and retained lessons learned across historical deals.",
            max_tokens=4096,
        )
        history = []
        for memory in recall.results:
            metadata = memory.metadata or {}
            memory_type = metadata.get("memory_type") or memory.type
            if memory_type not in {"deal_outcome", "lesson_learned"}:
                continue
            deal_id = metadata.get("deal_id") or next(
                (tag[5:] for tag in (memory.tags or []) if tag.startswith("deal:")),
                None,
            )
            if not deal_id:
                continue
            history.append({
                "memory_id": memory.id,
                "deal_id": deal_id,
                "memory_type": memory_type,
                "content": memory.text,
                "outcome": metadata.get("status"),
                "interaction_date": metadata.get("interaction_date") or memory.occurred_start or memory.mentioned_at,
            })
        return {
            "patterns": patterns,
            "history": history,
            "insufficient_evidence": patterns.insufficient_evidence and not history,
            "empty": not history and not patterns.patterns,
        }
    finally:
        try:
            client.close()
        except HindsightMemoryClientError:
            pass