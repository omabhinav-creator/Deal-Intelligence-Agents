"""Learn evidence-backed lessons from won, lost, or stalled deal outcomes."""

import json
import re
from datetime import datetime
from enum import Enum
from typing import Literal

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
from Hindsight.ai.prompts import OUTCOME_LEARNING_PROMPT
from Hindsight.config import get_settings
from Hindsight.memory.memory_schema import DealMemory, MemoryType
from Hindsight.memory.retain import retain_deal_memory


class OutcomeLearningError(RuntimeError):
	"""Outcome analysis or lesson retention could not be completed safely."""


class OutcomeLearningConfigurationError(OutcomeLearningError):
	"""Groq configuration required for outcome analysis is missing."""


class DealOutcome(str, Enum):
	"""Supported completed deal states that can produce learning."""

	WON = "won"
	LOST = "lost"
	STALLED = "stalled"


class ObservedOutcomeFact(BaseModel):
	"""A directly stated deal fact cited by original Hindsight memories."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	statement: str = Field(min_length=1)
	supporting_memory_ids: list[str] = Field(min_length=1)


class OutcomeLesson(BaseModel):
	"""A lesson with explicit evidence basis and optional causal support."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	content: str = Field(min_length=1)
	evidence_basis: Literal["observed", "inferred"]
	supporting_memory_ids: list[str] = Field(min_length=1)
	causal_claim: bool = False
	causal_memory_ids: list[str] = Field(default_factory=list)


class OutcomeLearningDraft(BaseModel):
	"""Structured Groq output before its memory references are validated."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	observed_facts: list[ObservedOutcomeFact] = Field(default_factory=list)
	lessons: list[OutcomeLesson] = Field(default_factory=list)
	insufficient_evidence: bool = False
	insufficient_reason: str | None = Field(default=None, min_length=1)


class OutcomeLearningResult(BaseModel):
	"""Outcome, analysis, original evidence, and memories retained for future use."""

	model_config = ConfigDict(extra="forbid")

	deal_id: str
	outcome: DealOutcome
	observed_facts: list[ObservedOutcomeFact] = Field(default_factory=list)
	lessons: list[OutcomeLesson] = Field(default_factory=list)
	supporting_evidence: list[BriefEvidence] = Field(default_factory=list)
	retained_memories: list[DealMemory] = Field(default_factory=list)
	insufficient_evidence: bool = False
	message: str | None = None


_CAUSAL_LANGUAGE = re.compile(
	r"\b(?:cause[sd]?|because|due to|led to|resulted in|as a result|"
	r"reason for|contributed to)\b",
	re.IGNORECASE,
)


def validate_outcome_learning_draft(
	draft: OutcomeLearningDraft,
	evidence: list[BriefEvidence],
) -> None:
	"""Validate outcome facts, lessons, and any explicit causal attribution."""
	by_id = {item.memory_id: item for item in evidence}
	for fact in draft.observed_facts:
		if not set(fact.supporting_memory_ids).issubset(by_id):
			raise OutcomeLearningError(
				"An observed fact cites memories not recalled for this deal."
			)
	for lesson in draft.lessons:
		supporting_ids = set(lesson.supporting_memory_ids)
		if not supporting_ids.issubset(by_id):
			raise OutcomeLearningError(
				"A lesson cites memories not recalled for this deal."
			)
		causal_ids = set(lesson.causal_memory_ids)
		if not causal_ids.issubset(supporting_ids):
			raise OutcomeLearningError(
				"Causal evidence must be included among lesson supporting memories."
			)
		claims_causation = lesson.causal_claim or bool(
			_CAUSAL_LANGUAGE.search(lesson.content)
		)
		if claims_causation:
			if not causal_ids:
				raise OutcomeLearningError(
					"A causal lesson must cite explicit causal evidence."
				)
			if not any(
				_CAUSAL_LANGUAGE.search(by_id[memory_id].content)
				for memory_id in causal_ids
			):
				raise OutcomeLearningError(
					"Cited memories do not explicitly establish the causal claim."
				)


class OutcomeLearningService:
	"""Analyze one deal's Hindsight history and retain the resulting lesson."""

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

	def learn_from_outcome(
		self,
		*,
		deal_id: str,
		outcome: DealOutcome | str,
		customer_name: str | None = None,
		outcome_date: datetime | None = None,
		interaction_id: str | None = None,
	) -> OutcomeLearningResult:
		"""Record the outcome, analyze same-deal facts, and retain safe lessons."""
		deal_id = deal_id.strip()
		if not deal_id:
			raise ValueError("deal_id must not be empty.")
		try:
			outcome = DealOutcome(outcome)
		except ValueError as exc:
			raise ValueError("outcome must be won, lost, or stalled.") from exc

		try:
			recall = self._memory_client.recall_memory(
				f"Retrieve the interaction history, objections, stakeholders, "
				f"competitors, pricing, requirements, risks, commitments, and outcomes "
				f"for deal {deal_id} before its {outcome.value} outcome.",
				tags=[f"deal:{deal_id}"],
				max_tokens=8192,
			)
		except HindsightMemoryClientError as exc:
			raise OutcomeLearningError("Hindsight deal-history recall failed.") from exc

		deal_memories = [
			item
			for item in recall.results
			if memory_belongs_to_deal(item, deal_id)
		]
		evidence = [memory_to_brief_evidence(item) for item in deal_memories]
		resolved_customer = customer_name or self._customer_from_evidence(evidence)
		supporting_ids = [item.memory_id for item in evidence]
		outcome_memory = DealMemory(
			deal_id=deal_id,
			memory_type=MemoryType.DEAL_OUTCOME,
			content=f"Deal outcome recorded as {outcome.value}.",
			customer_name=resolved_customer,
			interaction_id=interaction_id,
			interaction_date=outcome_date,
			interaction_source="deal_outcome",
			status=outcome.value,
			evidence_basis="observed",
			supporting_memory_ids=supporting_ids,
		)
		self._retain(outcome_memory)

		if not evidence:
			return OutcomeLearningResult(
				deal_id=deal_id,
				outcome=outcome,
				retained_memories=[outcome_memory],
				insufficient_evidence=True,
				message=(
					"The outcome was recorded, but no deal history was available "
					"to derive a lesson."
				),
			)

		draft = self._analyze(deal_id, outcome, evidence)
		self._validate_draft(draft, evidence)
		if draft.insufficient_evidence or not draft.lessons:
			return OutcomeLearningResult(
				deal_id=deal_id,
				outcome=outcome,
				observed_facts=draft.observed_facts,
				supporting_evidence=evidence,
				retained_memories=[outcome_memory],
				insufficient_evidence=True,
				message=(
					draft.insufficient_reason
					or "The available memories do not support a useful lesson."
				),
			)

		learned_memories = [
			self._lesson_memory(
				deal_id=deal_id,
				outcome=outcome,
				lesson=lesson,
				observed_facts=draft.observed_facts,
				customer_name=resolved_customer,
				outcome_date=outcome_date,
				interaction_id=interaction_id,
			)
			for lesson in draft.lessons
		]
		for lesson_memory in learned_memories:
			self._retain(lesson_memory)
		return OutcomeLearningResult(
			deal_id=deal_id,
			outcome=outcome,
			observed_facts=draft.observed_facts,
			lessons=draft.lessons,
			supporting_evidence=evidence,
			retained_memories=[outcome_memory, *learned_memories],
			insufficient_evidence=False,
		)

	@staticmethod
	def _customer_from_evidence(evidence: list[BriefEvidence]) -> str | None:
		customers = {item.customer_company for item in evidence if item.customer_company}
		return next(iter(customers)) if len(customers) == 1 else None

	def _retain(self, memory: DealMemory) -> None:
		try:
			retain_deal_memory(memory, self._memory_client)
		except HindsightMemoryClientError as exc:
			raise OutcomeLearningError("Hindsight outcome/lesson retain failed.") from exc

	def _analyze(
		self,
		deal_id: str,
		outcome: DealOutcome,
		evidence: list[BriefEvidence],
	) -> OutcomeLearningDraft:
		client = self._get_groq_client()
		try:
			response = client.chat.completions.create(
				model=self._model,
				messages=[
					{"role": "system", "content": OUTCOME_LEARNING_PROMPT},
					{
						"role": "user",
						"content": json.dumps(
							{
								"deal_id": deal_id,
								"outcome": outcome.value,
								"deal_memories": [
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
						"name": "outcome_learning",
						"strict": False,
						"schema": OutcomeLearningDraft.model_json_schema(),
					},
				},
			)
		except APIError as exc:
			raise OutcomeLearningError("Groq outcome-learning analysis failed.") from exc

		if not response.choices:
			raise OutcomeLearningError("Groq returned no outcome-learning analysis.")
		message = response.choices[0].message
		if message.refusal:
			raise OutcomeLearningError("Groq refused to analyze the deal outcome.")
		if not message.content:
			raise OutcomeLearningError("Groq returned an empty outcome-learning analysis.")
		try:
			return OutcomeLearningDraft.model_validate_json(message.content)
		except ValidationError as exc:
			raise OutcomeLearningError(
				"Groq returned outcome-learning data that did not match the schema."
			) from exc

	@staticmethod
	def _validate_draft(
		draft: OutcomeLearningDraft,
		evidence: list[BriefEvidence],
	) -> None:
		validate_outcome_learning_draft(draft, evidence)

	@staticmethod
	def _lesson_memory(
		*,
		deal_id: str,
		outcome: DealOutcome,
		lesson: OutcomeLesson,
		observed_facts: list[ObservedOutcomeFact],
		customer_name: str | None,
		outcome_date,
		interaction_id: str | None,
	) -> DealMemory:
		relevant_facts = [
			fact
			for fact in observed_facts
			if set(fact.supporting_memory_ids).intersection(lesson.supporting_memory_ids)
		]
		supporting_ids = list(
			dict.fromkeys(
				lesson.supporting_memory_ids
				+ [memory_id for fact in relevant_facts for memory_id in fact.supporting_memory_ids]
			)
		)
		fact_text = "\n".join(
			f"- {fact.statement} [memory IDs: {', '.join(fact.supporting_memory_ids)}]"
			for fact in relevant_facts
		)
		content = (
			f"Deal outcome: {outcome.value}.\n"
			f"Lesson ({lesson.evidence_basis}): {lesson.content}"
		)
		if fact_text:
			content += f"\nObserved facts:\n{fact_text}"
		return DealMemory(
			deal_id=deal_id,
			memory_type=MemoryType.LESSON_LEARNED,
			content=content,
			customer_name=customer_name,
			interaction_id=interaction_id,
			interaction_date=outcome_date,
			interaction_source="deal_outcome_learning",
			status=outcome.value,
			evidence_basis=lesson.evidence_basis,
			supporting_memory_ids=supporting_ids,
		)

	def _get_groq_client(self) -> Groq:
		if self._groq_client is None:
			if not self._groq_api_key:
				raise OutcomeLearningConfigurationError(
					"GROQ_API_KEY is required to learn from deal outcomes."
				)
			self._groq_client = Groq(api_key=self._groq_api_key)
		return self._groq_client