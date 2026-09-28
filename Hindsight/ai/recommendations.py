"""Explain a recommendation with deal-specific Hindsight evidence."""

import json

from groq import APIError, Groq
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.memory.hindsight_client import (
	HindsightMemoryClient,
	HindsightMemoryClientError,
)
from Hindsight.ai.deal_brief import (
	BriefEvidence,
	memory_belongs_to_deal,
	memory_to_brief_evidence,
)
from Hindsight.ai.prompts import RECOMMENDATION_WHY_PROMPT
from Hindsight.config import get_settings


class RecommendationError(RuntimeError):
	"""A recommendation explanation could not be generated safely."""


class RecommendationConfigurationError(RecommendationError):
	"""Groq configuration required for explanation is missing."""


class RecommendationWhyDraft(BaseModel):
	"""Groq's explanation referencing IDs in the supplied evidence only."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	reason: str | None = Field(default=None, min_length=1)
	supporting_memory_ids: list[str] = Field(default_factory=list)
	conflicting_memory_ids: list[str] = Field(default_factory=list)
	insufficient_evidence: bool = False


class RecommendationExplanation(BaseModel):
	"""Recommendation, rationale, and verbatim supporting/conflicting memories."""

	model_config = ConfigDict(extra="forbid")

	deal_id: str
	recommended_action: str
	reason: str
	supporting_memories: list[BriefEvidence] = Field(default_factory=list)
	conflicting_memories: list[BriefEvidence] = Field(default_factory=list)
	insufficient_evidence: bool = False


class RecommendationExplainer:
	"""Explain a provided recommendation using only one deal's recalled memories."""

	def __init__(
		self,
		memory_client: HindsightMemoryClient | None = None,
		groq_client: Groq | None = None,
		model: str | None = None,
	) -> None:
		settings = get_settings()
		self._memory_client = memory_client or HindsightMemoryClient()
		self._groq_client = groq_client
		self._groq_api_key = settings.groq_api_key
		self._model = model or settings.groq_model

	def explain(self, deal_id: str, recommended_action: str) -> RecommendationExplanation:
		"""Return a short reason with exact recalled memories for the deal."""
		deal_id = deal_id.strip()
		recommended_action = recommended_action.strip()
		if not deal_id:
			raise ValueError("deal_id must not be empty.")
		if not recommended_action:
			raise ValueError("recommended_action must not be empty.")

		query = (
			f"Find facts that support or conflict with this recommendation for deal "
			f"{deal_id}: {recommended_action}"
		)
		try:
			recall = self._memory_client.recall_memory(
				query,
				tags=[f"deal:{deal_id}"],
				max_tokens=4096,
			)
		except HindsightMemoryClientError as exc:
			raise RecommendationError("Hindsight evidence recall failed.") from exc

		evidence = [
			memory_to_brief_evidence(memory)
			for memory in recall.results
			if memory_belongs_to_deal(memory, deal_id)
		]
		if not evidence:
			return self._insufficient_explanation(deal_id, recommended_action)

		draft = self._generate_why(deal_id, recommended_action, evidence)
		available = {item.memory_id: item for item in evidence}
		cited_ids = set(draft.supporting_memory_ids + draft.conflicting_memory_ids)
		if not cited_ids.issubset(available):
			raise RecommendationError(
				"Groq cited memory IDs that were not returned by Hindsight."
			)

		supporting = self._select_memories(draft.supporting_memory_ids, available)
		conflicting = self._select_memories(draft.conflicting_memory_ids, available)
		if draft.insufficient_evidence or not draft.supporting_memory_ids or not draft.reason:
			return RecommendationExplanation(
				deal_id=deal_id,
				recommended_action=recommended_action,
				reason=(
					draft.reason
					or "There is not enough deal-specific evidence to explain this recommendation."
				),
				supporting_memories=supporting,
				conflicting_memories=conflicting,
				insufficient_evidence=True,
			)

		return RecommendationExplanation(
			deal_id=deal_id,
			recommended_action=recommended_action,
			reason=draft.reason,
			supporting_memories=supporting,
			conflicting_memories=conflicting,
			insufficient_evidence=False,
		)

	@staticmethod
	def _insufficient_explanation(
		deal_id: str,
		recommended_action: str,
	) -> RecommendationExplanation:
		return RecommendationExplanation(
			deal_id=deal_id,
			recommended_action=recommended_action,
			reason="There is not enough deal-specific evidence to explain this recommendation.",
			insufficient_evidence=True,
		)

	def _generate_why(
		self,
		deal_id: str,
		recommended_action: str,
		evidence: list[BriefEvidence],
	) -> RecommendationWhyDraft:
		client = self._get_groq_client()
		try:
			response = client.chat.completions.create(
				model=self._model,
				messages=[
					{"role": "system", "content": RECOMMENDATION_WHY_PROMPT},
					{
						"role": "user",
						"content": json.dumps(
							{
								"deal_id": deal_id,
								"recommended_action": recommended_action,
								"available_memories": [
									item.model_dump(mode="json") for item in evidence
								],
							},
							ensure_ascii=False,
						),
					},
				],
				response_format={
					"type": "json_schema",
					"json_schema": {
						"name": "recommendation_why",
						"strict": False,
						"schema": RecommendationWhyDraft.model_json_schema(),
					},
				},
			)
		except APIError as exc:
			raise RecommendationError("Groq recommendation explanation failed.") from exc

		if not response.choices:
			raise RecommendationError("Groq returned no recommendation explanation.")
		message = response.choices[0].message
		if message.refusal:
			raise RecommendationError("Groq refused to explain the recommendation.")
		if not message.content:
			raise RecommendationError("Groq returned an empty recommendation explanation.")
		try:
			return RecommendationWhyDraft.model_validate_json(message.content)
		except ValidationError as exc:
			raise RecommendationError(
				"Groq returned an explanation that did not match the response schema."
			) from exc

	def _get_groq_client(self) -> Groq:
		if self._groq_client is None:
			if not self._groq_api_key:
				raise RecommendationConfigurationError(
					"GROQ_API_KEY is required to explain recommendations."
				)
			self._groq_client = Groq(api_key=self._groq_api_key)
		return self._groq_client

	@staticmethod
	def _select_memories(
		memory_ids: list[str],
		available: dict[str, BriefEvidence],
	) -> list[BriefEvidence]:
		return [available[memory_id] for memory_id in dict.fromkeys(memory_ids)]