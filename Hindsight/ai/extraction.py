"""Extract structured sales intelligence from notes using Groq."""

from datetime import datetime

from groq import APIError, Groq
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from Hindsight.ai.prompts import SALES_INTELLIGENCE_EXTRACTION_PROMPT
from Hindsight.config import get_settings
from Hindsight.memory.memory_schema import DealMemory, MemoryType


class ExtractionError(RuntimeError):
	"""Groq could not return a valid sales intelligence extraction."""


class ExtractionConfigurationError(ExtractionError):
	"""Groq configuration is missing or invalid."""


class ExtractedFact(BaseModel):
	"""One fact explicitly present in the sales notes."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	content: str = Field(min_length=1)
	stakeholder_name: str | None = Field(default=None, min_length=1)
	status: str | None = Field(default=None, min_length=1)


class ExtractedStakeholder(BaseModel):
	"""A person and role explicitly identified in the notes."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	name: str = Field(min_length=1)
	role: str | None = Field(default=None, min_length=1)


class SalesIntelligenceExtraction(BaseModel):
	"""Structured facts extracted from one sales interaction."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	customer_company: str | None = Field(default=None, min_length=1)
	deal_id: str | None = Field(default=None, min_length=1)
	stakeholders: list[ExtractedStakeholder] = Field(default_factory=list)
	stakeholder_concerns: list[ExtractedFact] = Field(default_factory=list)
	objections: list[ExtractedFact] = Field(default_factory=list)
	competitors: list[ExtractedFact] = Field(default_factory=list)
	pricing_information: list[ExtractedFact] = Field(default_factory=list)
	customer_requirements: list[ExtractedFact] = Field(default_factory=list)
	customer_requests: list[ExtractedFact] = Field(default_factory=list)
	commitments: list[ExtractedFact] = Field(default_factory=list)
	follow_up_actions: list[ExtractedFact] = Field(default_factory=list)
	important_facts: list[ExtractedFact] = Field(default_factory=list)
	risks: list[ExtractedFact] = Field(default_factory=list)
	buying_signals: list[ExtractedFact] = Field(default_factory=list)
	unresolved_questions: list[ExtractedFact] = Field(default_factory=list)

	def to_deal_memories(
		self,
		*,
		deal_id: str | None = None,
		customer_name: str | None = None,
		interaction_date: datetime | None = None,
		interaction_id: str | None = None,
		interaction_source: str | None = None,
	) -> list[DealMemory]:
		"""Convert extracted facts to records accepted by the Hindsight retain workflow."""
		resolved_deal_id = (deal_id or self.deal_id or "").strip()
		if not resolved_deal_id:
			raise ValueError(
				"A deal_id is required from the meeting notes or caller context "
				"before extracted memories can be retained."
			)

		resolved_customer = (customer_name or self.customer_company or "").strip() or None
		memories: list[DealMemory] = []

		def add_memory(
			memory_type: MemoryType,
			content: str,
			*,
			stakeholder_name: str | None = None,
			status: str | None = None,
		) -> None:
			qualified_content = content
			if resolved_customer and resolved_customer.casefold() not in content.casefold():
				qualified_content = f"{resolved_customer}: {qualified_content}"
			if stakeholder_name and stakeholder_name.casefold() not in content.casefold():
				qualified_content += f" (stakeholder: {stakeholder_name})"
			memories.append(
				DealMemory(
					deal_id=resolved_deal_id,
					memory_type=memory_type,
					content=qualified_content,
					customer_name=resolved_customer,
					interaction_id=interaction_id,
					interaction_date=interaction_date,
					interaction_source=interaction_source,
					stakeholder_name=stakeholder_name,
					status=status,
				)
			)

		for stakeholder in self.stakeholders:
			content = f"Stakeholder: {stakeholder.name}"
			if stakeholder.role:
				content += f" ({stakeholder.role})"
			add_memory(MemoryType.STAKEHOLDER, content)

		fact_categories = (
			(self.stakeholder_concerns, MemoryType.STAKEHOLDER_CONCERN),
			(self.objections, MemoryType.OBJECTION),
			(self.competitors, MemoryType.COMPETITOR),
			(self.pricing_information, MemoryType.PRICING_DISCUSSION),
			(self.customer_requirements, MemoryType.CUSTOMER_REQUIREMENT),
			(self.customer_requests, MemoryType.CUSTOMER_REQUEST),
			(self.commitments, MemoryType.COMMITMENT),
			(self.follow_up_actions, MemoryType.SALES_ACTION),
			(self.important_facts, MemoryType.IMPORTANT_FACT),
			(self.risks, MemoryType.RISK),
			(self.buying_signals, MemoryType.BUYING_SIGNAL),
			(self.unresolved_questions, MemoryType.UNRESOLVED_QUESTION),
		)
		for facts, memory_type in fact_categories:
			for fact in facts:
				add_memory(
					memory_type,
					fact.content,
					stakeholder_name=fact.stakeholder_name,
					status=fact.status,
				)
		return memories


class SalesIntelligenceExtractor:
	"""Call Groq structured outputs and validate the result with Pydantic."""

	def __init__(self, client: Groq | None = None, model: str | None = None) -> None:
		settings = get_settings()
		self._model = model or settings.groq_model
		if client is None:
			if not settings.groq_api_key:
				raise ExtractionConfigurationError(
					"GROQ_API_KEY is required to extract sales intelligence."
				)
			self._client = Groq(api_key=settings.groq_api_key)
		else:
			self._client = client

	def extract(self, meeting_notes: str) -> SalesIntelligenceExtraction:
		"""Extract only facts present in the provided meeting notes."""
		if not meeting_notes.strip():
			raise ValueError("meeting_notes must not be empty.")

		try:
			response = self._client.chat.completions.create(
				model=self._model,
				messages=[
					{
						"role": "system",
						"content": SALES_INTELLIGENCE_EXTRACTION_PROMPT,
					},
					{"role": "user", "content": meeting_notes.strip()},
				],
				response_format={
					"type": "json_schema",
					"json_schema": {
						"name": "sales_intelligence_extraction",
						"strict": False,
						"schema": SalesIntelligenceExtraction.model_json_schema(),
					},
				},
			)
		except APIError as exc:
			raise ExtractionError("Groq extraction request failed.") from exc

		choices = response.choices
		if not choices:
			raise ExtractionError("Groq returned no extraction choices.")
		message = choices[0].message
		if getattr(message, "refusal", None):
			raise ExtractionError("Groq refused to extract the meeting notes.")
		if not message.content:
			raise ExtractionError("Groq returned an empty extraction.")

		try:
			return SalesIntelligenceExtraction.model_validate_json(message.content)
		except ValidationError as exc:
			raise ExtractionError(
				"Groq returned structured data that did not match the extraction schema."
			) from exc
