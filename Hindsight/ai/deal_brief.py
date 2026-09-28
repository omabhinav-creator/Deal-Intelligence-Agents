"""Retrieve deal-scoped Hindsight evidence and generate a concise Groq brief."""

import json
from typing import Any

from groq import APIError, Groq
from hindsight_client_api.models.recall_result import RecallResult
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.memory.hindsight_client import (
	HindsightMemoryClient,
	HindsightMemoryClientError,
)
from Hindsight.ai.prompts import DEAL_BRIEF_PROMPT
from Hindsight.config import get_settings


class DealBriefError(RuntimeError):
	"""A deal brief could not be safely retrieved or generated."""


class DealBriefConfigurationError(DealBriefError):
	"""Required Groq configuration is missing."""


class BriefFact(BaseModel):
	"""One known fact in the brief, with links to its supporting memories."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	statement: str = Field(min_length=1)
	evidence_ids: list[str] = Field(default_factory=list)


class BriefRecommendation(BaseModel):
	"""A preparation action, separate from factual deal history."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	action: str = Field(min_length=1)
	rationale: str = Field(min_length=1)
	evidence_ids: list[str] = Field(default_factory=list)


class DealBriefDraft(BaseModel):
	"""Structured Groq output before trusted source memories are attached."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	customer_company: str | None = Field(default=None, min_length=1)
	customer_summary: BriefFact | None = None
	current_deal_status: BriefFact | None = None
	key_stakeholders: list[BriefFact] = Field(default_factory=list)
	stakeholder_concerns: list[BriefFact] = Field(default_factory=list)
	main_objections: list[BriefFact] = Field(default_factory=list)
	competitors: list[BriefFact] = Field(default_factory=list)
	pricing_discussions: list[BriefFact] = Field(default_factory=list)
	customer_requirements: list[BriefFact] = Field(default_factory=list)
	previous_commitments: list[BriefFact] = Field(default_factory=list)
	recent_developments: list[BriefFact] = Field(default_factory=list)
	recommended_preparation: list[BriefRecommendation] = Field(default_factory=list)
	insufficient_information: bool = False


class BriefEvidence(BaseModel):
	"""A source memory returned by Hindsight, kept verbatim in the final brief."""

	model_config = ConfigDict(extra="forbid")

	memory_id: str
	content: str
	memory_type: str | None = None
	customer_company: str | None = None
	interaction_date: str | None = None
	interaction_source: str | None = None
	stakeholder_name: str | None = None


class DealBrief(DealBriefDraft):
	"""A structured brief plus the exact Hindsight memories used as evidence."""

	deal_id: str
	supporting_evidence: list[BriefEvidence] = Field(default_factory=list)


class DealBriefGenerator:
	"""Build deal briefs using only memories tagged for the requested deal."""

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

	def generate(self, deal_id: str) -> DealBrief:
		"""Recall one deal's evidence and produce its pre-interaction briefing."""
		deal_id = deal_id.strip()
		if not deal_id:
			raise ValueError("deal_id must not be empty.")

		query = (
			f"Prepare for the next customer interaction for deal {deal_id}. "
			"Summarize the customer, current status, stakeholders and concerns, "
			"objections, competitors, pricing, requirements, commitments, recent "
			"developments, and evidence-based preparation."
		)
		try:
			recall_response = self._memory_client.recall_memory(
				query,
				tags=[f"deal:{deal_id}"],
				max_tokens=4096,
			)
		except HindsightMemoryClientError as exc:
			raise DealBriefError("Hindsight memory recall failed.") from exc

		evidence = [
			memory_to_brief_evidence(memory)
			for memory in recall_response.results
			if memory_belongs_to_deal(memory, deal_id)
		]
		if not evidence:
			return DealBrief(deal_id=deal_id, insufficient_information=True)

		draft = self._generate_draft(deal_id, evidence)
		self._validate_citations(draft, evidence)
		return DealBrief(
			**draft.model_dump(),
			deal_id=deal_id,
			supporting_evidence=evidence,
		)

	def _generate_draft(
		self,
		deal_id: str,
		evidence: list[BriefEvidence],
	) -> DealBriefDraft:
		client = self._get_groq_client()
		try:
			response = client.chat.completions.create(
				model=self._model,
				messages=[
					{"role": "system", "content": DEAL_BRIEF_PROMPT},
					{
						"role": "user",
						"content": json.dumps(
							{
								"deal_id": deal_id,
								"supporting_memories": [
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
						"name": "deal_brief",
						"strict": False,
						"schema": DealBriefDraft.model_json_schema(),
					},
				},
			)
		except APIError as exc:
			raise DealBriefError("Groq deal brief request failed.") from exc

		if not response.choices:
			raise DealBriefError("Groq returned no deal brief choices.")
		message = response.choices[0].message
		if message.refusal:
			raise DealBriefError("Groq refused to generate the deal brief.")
		if not message.content:
			raise DealBriefError("Groq returned an empty deal brief.")
		try:
			return DealBriefDraft.model_validate_json(message.content)
		except ValidationError as exc:
			raise DealBriefError(
				"Groq returned a deal brief that did not match the response schema."
			) from exc

	def _get_groq_client(self) -> Groq:
		if self._groq_client is None:
			if not self._groq_api_key:
				raise DealBriefConfigurationError(
					"GROQ_API_KEY is required to generate a deal brief."
				)
			self._groq_client = Groq(api_key=self._groq_api_key)
		return self._groq_client

	@staticmethod
	def _validate_citations(
		draft: DealBriefDraft,
		evidence: list[BriefEvidence],
	) -> None:
		facts: list[BriefFact] = []
		for field_name in (
			"customer_summary",
			"current_deal_status",
			"key_stakeholders",
			"stakeholder_concerns",
			"main_objections",
			"competitors",
			"pricing_discussions",
			"customer_requirements",
			"previous_commitments",
			"recent_developments",
		):
			value = getattr(draft, field_name)
			if value is None:
				continue
			facts.extend(value if isinstance(value, list) else [value])

		cited_ids = {
			memory_id
			for item in facts
			for memory_id in item.evidence_ids
		}
		cited_ids.update(
			memory_id
			for item in draft.recommended_preparation
			for memory_id in item.evidence_ids
		)
		if any(not item.evidence_ids for item in facts) or any(
			not item.evidence_ids for item in draft.recommended_preparation
		):
			raise DealBriefError("Every brief statement must cite supporting memory IDs.")
		available_memory_ids = {item.memory_id for item in evidence}
		if not cited_ids.issubset(available_memory_ids):
			raise DealBriefError(
				"Groq cited memory IDs that were not returned by Hindsight."
			)

		if draft.customer_company:
			company_is_supported = any(
				draft.customer_company.casefold() in source.casefold()
				for item in evidence
				for source in (item.customer_company or "", item.content)
			)
			if not company_is_supported:
				raise DealBriefError(
					"Groq returned a customer/company name not found in Hindsight evidence."
				)


def memory_belongs_to_deal(memory: RecallResult, deal_id: str) -> bool:
	"""Reject recall results explicitly associated with another deal."""
	metadata = memory.metadata or {}
	metadata_deal_id = metadata.get("deal_id")
	if metadata_deal_id is not None:
		return metadata_deal_id == deal_id
	return f"deal:{deal_id}" in (memory.tags or [])


def memory_to_brief_evidence(memory: RecallResult) -> BriefEvidence:
	"""Convert a Hindsight result into the shared evidence representation."""
	metadata = memory.metadata or {}
	return BriefEvidence(
		memory_id=memory.id,
		content=memory.text,
		memory_type=metadata.get("memory_type") or memory.type,
		customer_company=metadata.get("customer_name"),
		interaction_date=(
			metadata.get("interaction_date")
			or memory.occurred_start
			or memory.mentioned_at
		),
		interaction_source=metadata.get("interaction_source"),
		stakeholder_name=metadata.get("stakeholder_name"),
	)