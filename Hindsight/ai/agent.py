"""Process sales interactions into persistent Hindsight deal memories."""

from dataclasses import dataclass
from datetime import datetime

from hindsight_client_api.models.retain_response import RetainResponse

from backend.memory.hindsight_client import (
	HindsightMemoryClient,
	HindsightMemoryClientError,
)
from Hindsight.ai.extraction import (
	ExtractionError,
	SalesIntelligenceExtraction,
	SalesIntelligenceExtractor,
)
from Hindsight.memory.memory_schema import DealMemory
from Hindsight.memory.retain import retain_deal_memory


class InteractionProcessingError(RuntimeError):
	"""A sales interaction could not be fully processed and retained."""


@dataclass(frozen=True)
class InteractionProcessingResult:
	"""Extraction, normalized memories, and Hindsight retain responses."""

	extraction: SalesIntelligenceExtraction
	memories: tuple[DealMemory, ...]
	retain_responses: tuple[RetainResponse, ...]


def process_sales_interaction(
	*,
	deal_id: str,
	meeting_notes: str,
	customer_company: str | None = None,
	interaction_date: datetime | None = None,
	interaction_id: str | None = None,
	interaction_source: str | None = "meeting_notes",
	extractor: SalesIntelligenceExtractor | None = None,
	memory_client: HindsightMemoryClient | None = None,
) -> InteractionProcessingResult:
	"""Extract a meeting's facts, convert them, and retain each in Hindsight."""
	if not isinstance(deal_id, str) or not deal_id.strip():
		raise ValueError("deal_id must not be empty.")
	if not isinstance(meeting_notes, str):
		raise TypeError("meeting_notes must be a string.")
	if not meeting_notes.strip():
		raise ValueError("meeting_notes must not be empty.")

	try:
		active_extractor = extractor or SalesIntelligenceExtractor()
		extraction = active_extractor.extract(meeting_notes)
	except ExtractionError as exc:
		raise InteractionProcessingError("Sales intelligence extraction failed.") from exc
	except Exception as exc:
		raise InteractionProcessingError("Sales intelligence extraction failed.") from exc

	try:
		memories = extraction.to_deal_memories(
			deal_id=deal_id,
			customer_name=customer_company,
			interaction_date=interaction_date,
			interaction_id=interaction_id,
			interaction_source=interaction_source,
		)
	except (TypeError, ValueError) as exc:
		raise InteractionProcessingError(
			"Could not convert extracted intelligence into deal memories."
		) from exc

	if not memories:
		return InteractionProcessingResult(extraction, (), ())

	try:
		active_memory_client = memory_client or HindsightMemoryClient()
	except HindsightMemoryClientError as exc:
		raise InteractionProcessingError("Hindsight client configuration failed.") from exc

	retain_responses: list[RetainResponse] = []
	for index, memory in enumerate(memories, start=1):
		try:
			retain_responses.append(retain_deal_memory(memory, active_memory_client))
		except HindsightMemoryClientError as exc:
			raise InteractionProcessingError(
				f"Hindsight retain failed after {len(retain_responses)} of "
				f"{len(memories)} memories were stored (failed at item {index})."
			) from exc
		except Exception as exc:
			raise InteractionProcessingError(
				f"Hindsight retain failed after {len(retain_responses)} of "
				f"{len(memories)} memories were stored (failed at item {index})."
			) from exc

	return InteractionProcessingResult(
		extraction=extraction,
		memories=tuple(memories),
		retain_responses=tuple(retain_responses),
	)