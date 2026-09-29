"""Build an evidence-backed retrospective for one sales deal."""

import json
from groq import APIError, Groq
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.memory.hindsight_client import (
    HindsightMemoryClient,
    HindsightMemoryClientError,
)
from Hindsight.ai.deal_brief import (
    BriefEvidence,
    BriefFact,
    memory_belongs_to_deal,
    memory_to_brief_evidence,
)
from Hindsight.ai.prompts import DEAL_AUTOPSY_PROMPT
from Hindsight.config import get_settings
from Hindsight.memory.learning import (
    DealOutcome,
    ObservedOutcomeFact,
    OutcomeLesson,
    OutcomeLearningError,
    OutcomeLearningDraft,
    validate_outcome_learning_draft,
)


class DealAutopsyError(RuntimeError):
    """A deal autopsy could not be safely generated."""


class DealAutopsyConfigurationError(DealAutopsyError):
    """Groq configuration required for an autopsy is missing."""


class DealAutopsyRateLimitError(DealAutopsyError):
    """Groq rate-limited an autopsy request; callers must not retry automatically."""

    def __init__(self, provider_message: str, retry_after: str | None = None) -> None:
        self.provider_message = provider_message
        self.retry_after = retry_after
        message = (
            "Deal Autopsy is temporarily unavailable because the AI provider rate limit "
            "has been reached. Please try again later."
        )
        if retry_after:
            message += f" Retry after: {retry_after}."
        super().__init__(message)


class DealAutopsyDraft(BaseModel):
    """Structured model output before evidence references are validated."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    customer_company: str | None = Field(default=None, min_length=1)
    timeline: list[BriefFact] = Field(default_factory=list)
    major_objections: list[BriefFact] = Field(default_factory=list)
    stakeholder_concerns: list[BriefFact] = Field(default_factory=list)
    competitors: list[BriefFact] = Field(default_factory=list)
    pricing_discussions: list[BriefFact] = Field(default_factory=list)
    customer_requirements: list[BriefFact] = Field(default_factory=list)
    turning_points: list[BriefFact] = Field(default_factory=list)
    actions_taken: list[BriefFact] = Field(default_factory=list)
    resolved_issues: list[BriefFact] = Field(default_factory=list)
    unresolved_issues: list[BriefFact] = Field(default_factory=list)
    observed_factors: list[ObservedOutcomeFact] = Field(default_factory=list)
    interpretations: list[OutcomeLesson] = Field(default_factory=list)
    lessons_learned: list[OutcomeLesson] = Field(default_factory=list)
    insufficient_evidence: bool = False
    insufficient_reason: str | None = Field(default=None, min_length=1)


class DealAutopsy(DealAutopsyDraft):
    """A retrospective plus the exact Hindsight evidence used to make it."""

    deal_id: str
    outcome: DealOutcome
    supporting_evidence: list[BriefEvidence] = Field(default_factory=list)


_FACT_FIELDS = (
    "timeline",
    "major_objections",
    "stakeholder_concerns",
    "competitors",
    "pricing_discussions",
    "customer_requirements",
    "turning_points",
    "actions_taken",
    "resolved_issues",
    "unresolved_issues",
)


class DealAutopsyAnalyzer:
    """Analyze only the requested deal using shared memory and safety models."""

    def __init__(
        self,
        memory_client: HindsightMemoryClient | None = None,
        groq_client: Groq | None = None,
        model: str | None = None,
    ) -> None:
        settings = get_settings()
        self._memory_client = memory_client or HindsightMemoryClient()
        self._groq_client = groq_client
        self._groq_api_key = settings.ai_groq_api_key
        self._model = model or settings.groq_model

    def analyze(self, deal_id: str, outcome: DealOutcome | str) -> DealAutopsy:
        deal_id = deal_id.strip()
        if not deal_id:
            raise ValueError("deal_id must not be empty.")
        try:
            outcome = DealOutcome(outcome)
        except ValueError as exc:
            raise ValueError("outcome must be won, lost, or stalled.") from exc

        try:
            recall = self._memory_client.recall_memory(
                f"Retrieve the complete history and outcome evidence for deal {deal_id}, "
                "including timeline, objections, stakeholders, competitors, pricing, "
                "requirements, actions, resolved and unresolved issues.",
                tags=[f"deal:{deal_id}"],
                max_tokens=8192,
            )
        except HindsightMemoryClientError as exc:
            raise DealAutopsyError("Hindsight deal-history recall failed.") from exc

        evidence = [
            memory_to_brief_evidence(memory)
            for memory in recall.results
            if memory_belongs_to_deal(memory, deal_id)
        ]
        if not evidence:
            return DealAutopsy(
                deal_id=deal_id,
                outcome=outcome,
                insufficient_evidence=True,
                insufficient_reason="No Hindsight memories were available for this deal.",
            )

        draft = self._generate_draft(deal_id, outcome, evidence)
        try:
            self._validate_draft(draft, evidence)
        except OutcomeLearningError as exc:
            raise DealAutopsyError(str(exc)) from exc
        return DealAutopsy(
            **draft.model_dump(), deal_id=deal_id, outcome=outcome,
            supporting_evidence=evidence,
        )

    def _generate_draft(
        self, deal_id: str, outcome: DealOutcome, evidence: list[BriefEvidence]
    ) -> DealAutopsyDraft:
        client = self._get_groq_client()
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": DEAL_AUTOPSY_PROMPT},
                    {"role": "user", "content": json.dumps({
                        "deal_id": deal_id,
                        "outcome": outcome.value,
                        "deal_memories": [item.model_dump(mode="json") for item in evidence],
                    }, ensure_ascii=False)},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "deal_autopsy",
                        "strict": False,
                        "schema": DealAutopsyDraft.model_json_schema(),
                    },
                },
            )
        except APIError as exc:
            status_code = getattr(exc, "status_code", None)
            provider_message = getattr(exc, "message", None) or str(exc)
            if status_code == 429:
                response_headers = getattr(getattr(exc, "response", None), "headers", {})
                raise DealAutopsyRateLimitError(
                    provider_message, response_headers.get("retry-after")
                ) from exc
            status = f" (HTTP {status_code})" if status_code is not None else ""
            raise DealAutopsyError(
                f"Groq deal-autopsy analysis failed{status}: {provider_message}"
            ) from exc
        if not response.choices:
            raise DealAutopsyError("Groq returned no deal-autopsy analysis.")
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise DealAutopsyError("Groq refused to analyze the deal.")
        if not message.content:
            raise DealAutopsyError("Groq returned an empty deal-autopsy analysis.")
        try:
            return DealAutopsyDraft.model_validate_json(message.content)
        except ValidationError as exc:
            raise DealAutopsyError(
                "Groq returned deal-autopsy data that did not match the schema."
            ) from exc

    @classmethod
    def _validate_draft(
        cls, draft: DealAutopsyDraft, evidence: list[BriefEvidence]
    ) -> None:
        available = {item.memory_id for item in evidence}
        for field_name in _FACT_FIELDS:
            for fact in getattr(draft, field_name):
                if not fact.evidence_ids:
                    raise DealAutopsyError(
                        f"Every {field_name} item must cite supporting memory IDs."
                    )
                if not set(fact.evidence_ids).issubset(available):
                    raise DealAutopsyError(
                        "A deal-autopsy fact cites memories not returned for this deal."
                    )
        if draft.customer_company and not any(
            draft.customer_company.casefold() in source.casefold()
            for item in evidence
            for source in (item.customer_company or "", item.content)
        ):
            raise DealAutopsyError(
                "Groq returned a customer/company name not found in Hindsight evidence."
            )
        # The outcome-learning validator is the single source of truth for
        # observed facts, interpretations, lessons, and causal language.
        validate_outcome_learning_draft(
            OutcomeLearningDraft(
                observed_facts=draft.observed_factors,
                lessons=[*draft.interpretations, *draft.lessons_learned],
                insufficient_evidence=draft.insufficient_evidence,
                insufficient_reason=draft.insufficient_reason,
            ),
            evidence,
        )

    def _get_groq_client(self) -> Groq:
        if self._groq_client is None:
            if not self._groq_api_key:
                raise DealAutopsyConfigurationError(
                    "GROQ_API_KEY_AI is required to generate a deal autopsy."
                )
            self._groq_client = Groq(api_key=self._groq_api_key, max_retries=0)
        return self._groq_client


# A short alias keeps the capability convenient to discover in callers.
DealAutopsyService = DealAutopsyAnalyzer
DealAutopsyGenerator = DealAutopsyAnalyzer
