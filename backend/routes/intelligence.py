"""Compatibility routes backed by the shared Hindsight intelligence services."""

from typing import Any

from fastapi import APIRouter, Depends

from Hindsight.ai.deal_changes import DealChangeAnalyzer
from backend.memory.hindsight_client import HindsightMemoryClient, HindsightMemoryClientError
from ..auth import get_current_user


router = APIRouter(
    prefix="/api/deals/{deal_id}",
    tags=["intelligence"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/what-changed")
def what_changed(deal_id: str) -> Any:
    """Retain the original endpoint while using the evidence-backed analyzer."""
    client = HindsightMemoryClient()
    try:
        return DealChangeAnalyzer(memory_client=client).analyze(deal_id)
    finally:
        try:
            client.close()
        except HindsightMemoryClientError:
            pass
