"""Compare chronological, deal-scoped Hindsight memories for meaningful changes."""

import json
from datetime import datetime, timezone
from enum import Enum

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
from Hindsight.ai.prompts import WHAT_CHANGED_PROMPT
from Hindsight.config import get_settings


class DealChangeError(RuntimeError):
	"""A deal change analysis could not be safely completed."""


class DealChangeConfigurationError(DealChangeError):
	"""Groq configuration required for change analysis is missing."""


class ChangeType(str, Enum):
	"""Timeline transition identified between deal memories."""

	NEW = "new"
	RESOLVED = "resolved"
	CONTINUING = "continuing"
	CHANGED = "changed"
	COMPLETED = "completed"
	UNRESOLVED = "unresolved"


class ChangeCategory(str, Enum):
	"""Sales intelligence areas that can change during a deal."""

	OBJECTION = "objection"
	STAKEHOLDER = "stakeholder"
	STAKEHOLDER_CONCERN = "stakeholder_concern"
	COMPETITOR = "competitor"
	PRICING = "pricing"
	CUSTOMER_REQUIREMENT = "customer_requirement"
	BUYING_SIGNAL = "buying_signal"
	RISK = "risk"
	COMMITMENT = "commitment"
	UNRESOLVED_ISSUE = "unresolved_issue"


class EvidenceBasis(str, Enum):
	"""Whether a change is stated directly or derived from the timeline."""

	OBSERVED = "observed"
	INFERRED = "inferred"


class DealChange(BaseModel):
	"""One evidence-backed deal change with older and newer source references."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	change_type: ChangeType
	category: ChangeCategory
	summary: str = Field(min_length=1)
	evidence_basis: EvidenceBasis
	earlier_memory_ids: list[str] = Field(default_factory=list)
	later_memory_ids: list[str] = Field(default_factory=list)


class DealChangeDraft(BaseModel):
	"""Structured Groq result before validating its memory references."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	changes: list[DealChange] = Field(default_factory=list)
	insufficient_history: bool = False
	insufficient_reason: str | None = Field(default=None, min_length=1)


class DealChangeAnalysis(BaseModel):
	"""Deal changes plus the exact chronological evidence used for comparison."""

	model_config = ConfigDict(extra="forbid")

	deal_id: str
	changes: list[DealChange] = Field(default_factory=list)
	evidence: list[BriefEvidence] = Field(default_factory=list)
	insufficient_history: bool = False
	insufficient_reason: str | None = None


class DealChangeAnalyzer:
	"""Find evidence-backed deal changes using Hindsight recall and Groq."""

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

	def analyze(self, deal_id: str) -> DealChangeAnalysis:
		"""Compare a deal's older and newer memories without using other deals."""
		deal_id = deal_id.strip()
		if not deal_id:
			raise ValueError("deal_id must not be empty.")

		try:
			recall = self._memory_client.recall_memory(
				f"Retrieve historical interactions, objections, stakeholders, "
				f"competitors, pricing, requirements, buying signals, risks, and "
			f"commitment status over time for deal {deal_id}.",
				tags=[f"deal:{deal_id}"],
				max_tokens=4096,
			)
		except HindsightMemoryClientError as exc:
			raise DealChangeError("Hindsight memory recall failed.") from exc

		deal_memories = [
			memory
			for memory in recall.results
			if memory_belongs_to_deal(memory, deal_id)
		]
		evidence = [memory_to_brief_evidence(memory) for memory in deal_memories]
		chronological = self._chronological_evidence(evidence)
		if len({self._parse_date(item.interaction_date) for item in chronological}) < 2:
			return DealChangeAnalysis(
				deal_id=deal_id,
				evidence=evidence,
				insufficient_history=True,
				insufficient_reason=(
					"At least two memories with distinct interaction dates are needed "
					"to determine what changed over time."
				),
			)

		draft = self._generate_draft(deal_id, chronological)
		if draft.insufficient_history:
			return DealChangeAnalysis(
				deal_id=deal_id,
				evidence=chronological,
				insufficient_history=True,
				insufficient_reason=(
					draft.insufficient_reason
					or "The available history does not support a reliable change analysis."
				),
			)

		self._validate_changes(draft.changes, chronological)
		cited_ids = {
			memory_id
			for change in draft.changes
			for memory_id in change.earlier_memory_ids + change.later_memory_ids
		}
		cited_evidence = [item for item in chronological if item.memory_id in cited_ids]
		return DealChangeAnalysis(
			deal_id=deal_id,
			changes=draft.changes,
			evidence=cited_evidence,
			insufficient_history=False,
		)

	@staticmethod
	def _parse_date(value: str | None) -> datetime | None:
		if not value:
			return None
		try:
			parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
		except ValueError:
			return None
		return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed

	@classmethod
	def _chronological_evidence(
		cls,
		evidence: list[BriefEvidence],
	) -> list[BriefEvidence]:
		return sorted(
			(item for item in evidence if cls._parse_date(item.interaction_date)),
			key=lambda item: (
				cls._parse_date(item.interaction_date),
				item.memory_id,
			),
		)

	def _generate_draft(
		self,
		deal_id: str,
		evidence: list[BriefEvidence],
	) -> DealChangeDraft:
		client = self._get_groq_client()
		try:
			response = client.chat.completions.create(
				model=self._model,
				messages=[
					{"role": "system", "content": WHAT_CHANGED_PROMPT},
					{
						"role": "user",
						"content": json.dumps(
							{
								"deal_id": deal_id,
								"chronological_memories": [
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
						"name": "deal_change_analysis",
						"strict": False,
						"schema": DealChangeDraft.model_json_schema(),
					},
				},
			)
		except APIError as exc:
			raise DealChangeError("Groq deal change analysis failed.") from exc

		if not response.choices:
			raise DealChangeError("Groq returned no deal change analysis.")
		message = response.choices[0].message
		if message.refusal:
			raise DealChangeError("Groq refused to analyze deal changes.")
		if not message.content:
			raise DealChangeError("Groq returned an empty deal change analysis.")
		try:
			return DealChangeDraft.model_validate_json(message.content)
		except ValidationError as exc:
			raise DealChangeError(
				"Groq returned changes that did not match the response schema."
			) from exc

	def _get_groq_client(self) -> Groq:
		if self._groq_client is None:
			if not self._groq_api_key:
				raise DealChangeConfigurationError(
					"GROQ_API_KEY is required to analyze deal changes."
				)
			self._groq_client = Groq(api_key=self._groq_api_key)
		return self._groq_client

	@classmethod
	def _validate_changes(
		cls,
		changes: list[DealChange],
		evidence: list[BriefEvidence],
	) -> None:
		by_id = {item.memory_id: item for item in evidence}
		paired_transitions = {
			ChangeType.RESOLVED,
			ChangeType.CONTINUING,
			ChangeType.CHANGED,
			ChangeType.COMPLETED,
		}
		for change in changes:
			all_ids = change.earlier_memory_ids + change.later_memory_ids
			if not all_ids:
				raise DealChangeError("Every reported change must cite supporting memories.")
			if any(memory_id not in by_id for memory_id in all_ids):
				raise DealChangeError(
					"Groq cited memory IDs that were not returned for this deal."
				)
			if change.change_type in paired_transitions and (
				not change.earlier_memory_ids or not change.later_memory_ids
			):
				raise DealChangeError(
					f"{change.change_type.value} changes need both earlier and later evidence."
				)
			if change.change_type in {ChangeType.NEW, ChangeType.UNRESOLVED} and not change.later_memory_ids:
				raise DealChangeError(
					f"{change.change_type.value} changes need later evidence."
				)
			if change.earlier_memory_ids and change.later_memory_ids:
				earlier_dates = [
					cls._parse_date(by_id[memory_id].interaction_date)
					for memory_id in change.earlier_memory_ids
				]
				later_dates = [
					cls._parse_date(by_id[memory_id].interaction_date)
					for memory_id in change.later_memory_ids
				]
				if max(earlier_dates) >= min(later_dates):
					raise DealChangeError(
					"Change evidence must cite earlier memories before later memories."
				)