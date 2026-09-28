"""Retain validated deal memories through the shared Hindsight client."""

from hindsight_client_api.models.retain_response import RetainResponse

from backend.memory.hindsight_client import HindsightMemoryClient
from Hindsight.memory.memory_schema import DealMemory


def retain_deal_memory(
	memory: DealMemory,
	client: HindsightMemoryClient,
) -> RetainResponse:
	"""Convert a deal memory to Hindsight fields and retain it in its bank."""
	return client.retain_memory(
		memory.content,
		timestamp=memory.interaction_date,
		context=memory.interaction_source or memory.memory_type.value,
		document_id=memory.interaction_id,
		metadata=memory.to_hindsight_metadata(),
		tags=memory.to_hindsight_tags(),
	)