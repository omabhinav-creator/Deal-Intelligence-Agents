"""Find evidence-backed historical deals similar to a current deal."""

import json
from collections import defaultdict
from datetime import datetime, timezone

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
from Hindsight.ai.deal_changes import EvidenceBasis
from Hindsight.ai.prompts import SIMILAR_DEALS_PROMPT
from Hindsight.config import get_settings


class SimilarDealsError(RuntimeError):
    """Similar-deal retrieval or comparison could not be completed safely."""


class SimilarDealsConfigurationError(SimilarDealsError):
    """Groq configuration required for deal comparison is missing."""


class MatchingCharacteristic(BaseModel):
    """One shared characteristic with evidence from both deals."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    characteristic: str = Field(min_length=1)
    evidence_basis: EvidenceBasis
    current_memory_ids: list[str] = Field(min_length=1)
    historical_memory_ids: list[str] = Field(min_length=1)


class HistoricalDealFact(BaseModel):
    """An outcome or lesson supported by historical deal memories."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    statement: str = Field(min_length=1)
    memory_ids: list[str] = Field(min_length=1)


class SimilarDealDraft(BaseModel):
    """Structured Groq comparison before validating source-memory references."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    historical_deal_id: str = Field(min_length=1)
    is_similar: bool
    similarity_reason: str | None = Field(default=None, min_length=1)
    reason_memory_ids: list[str] = Field(default_factory=list)
    matching_characteristics: list[MatchingCharacteristic] = Field(default_factory=list)
    historical_outcome: HistoricalDealFact | None = None
    useful_lesson: HistoricalDealFact | None = None


class SimilarDealsDraft(BaseModel):
    """Groq's collection of historical deal comparison results."""

    model_config = ConfigDict(extra="forbid")

    deals: list[SimilarDealDraft] = Field(default_factory=list)


class SimilarDeal(BaseModel):
    """One similar historical deal with the memories that substantiate it."""

    model_config = ConfigDict(extra="forbid")

    historical_deal_id: str
    company_name: str | None = None
    similarity_reason: str
    reason_memory_ids: list[str]
    matching_characteristics: list[MatchingCharacteristic]
    historical_outcome: HistoricalDealFact | None = None
    useful_lesson: HistoricalDealFact | None = None
    current_evidence: list[BriefEvidence]
    historical_evidence: list[BriefEvidence]


class SimilarDealsAnalysis(BaseModel):
    """Similar historical deals, or a clear insufficient-data response."""

    model_config = ConfigDict(extra="forbid")

    current_deal_id: str
    similar_deals: list[SimilarDeal] = Field(default_factory=list)
    insufficient_data: bool = False
    message: str | None = None


class SimilarDealsFinder:
    """Use one existing Hindsight client and Groq to compare deal evidence."""

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

    def find_similar_deals(self, current_deal_id: str) -> SimilarDealsAnalysis:
        """Compare one deal's memories with recalled memories from other deals."""
        current_deal_id = current_deal_id.strip()
        if not current_deal_id:
            raise ValueError("current_deal_id must not be empty.")

        current_memories = self._recall(
            f"Retrieve deal facts useful for comparing deal {current_deal_id} "
            "with historical sales deals.",
            tags=[f"deal:{current_deal_id}"],
        )
        current_memories = [
            item
            for item in current_memories
            if memory_belongs_to_deal(item, current_deal_id)
        ]
        if not current_memories:
            return SimilarDealsAnalysis(
                current_deal_id=current_deal_id,
                insufficient_data=True,
                message="No current-deal memories are available for comparison.",
            )

        current_evidence = self._sort_evidence(
            [memory_to_brief_evidence(item) for item in current_memories]
        )
        historical_query = self._build_historical_query(
            current_deal_id, current_evidence
        )
        historical_memories = self._recall(historical_query, tags=None)
        grouped = self._group_historical_memories(
            historical_memories, current_deal_id
        )
        historical_evidence = {
            deal_id: self._sort_evidence(
                [memory_to_brief_evidence(item) for item in items]
            )
            for deal_id, items in grouped.items()
        }
        if not historical_evidence:
            return SimilarDealsAnalysis(
                current_deal_id=current_deal_id,
                insufficient_data=True,
                message="No other historical deal memories were found.",
            )

        draft = self._compare(
            current_deal_id, current_evidence, historical_evidence
        )
        similar_deals = self._validate_and_build(
            draft, current_deal_id, current_evidence, historical_evidence
        )
        if not similar_deals:
            return SimilarDealsAnalysis(
                current_deal_id=current_deal_id,
                insufficient_data=True,
                message="No historical deals had enough evidence-backed similarities.",
            )
        return SimilarDealsAnalysis(
            current_deal_id=current_deal_id,
            similar_deals=similar_deals,
        )

    def _recall(self, query: str, *, tags: list[str] | None) -> list[object]:
        try:
            response = self._memory_client.recall_memory(
                query,
                tags=tags,
                max_tokens=4096,
            )
        except HindsightMemoryClientError as exc:
            raise SimilarDealsError("Hindsight memory recall failed.") from exc
        return list(response.results)

    @staticmethod
    def _build_historical_query(
        current_deal_id: str,
        evidence: list[BriefEvidence],
    ) -> str:
        facts = "\n".join(
            f"- {item.memory_type or 'fact'}: {item.content}" for item in evidence
        )
        return (
            f"Find historical deal memories similar to current deal {current_deal_id}. "
            "Search for overlap in objections, requirements, stakeholder concerns, "
            "competitors, pricing, buying signals, risks, outcomes, and lessons. "
            f"Current deal facts:\n{facts}"
        )

    @staticmethod
    def _group_historical_memories(
        memories: list[object], current_deal_id: str
    ) -> dict[str, list[object]]:
        grouped: dict[str, list[object]] = defaultdict(list)
        for memory in memories:
            metadata = getattr(memory, "metadata", None) or {}
            deal_id = metadata.get("deal_id")
            if deal_id is None:
                for tag in getattr(memory, "tags", None) or []:
                    if tag.startswith("deal:"):
                        deal_id = tag.removeprefix("deal:")
                        break
            if not deal_id or deal_id == current_deal_id:
                continue
            grouped[deal_id].append(memory)
        return dict(grouped)

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
    def _sort_evidence(cls, evidence: list[BriefEvidence]) -> list[BriefEvidence]:
        return sorted(
            evidence,
            key=lambda item: (
                cls._parse_date(item.interaction_date) is None,
                cls._parse_date(item.interaction_date)
                or datetime.max.replace(tzinfo=timezone.utc),
                item.memory_id,
            ),
        )

    def _compare(
        self,
        current_deal_id: str,
        current_evidence: list[BriefEvidence],
        historical_evidence: dict[str, list[BriefEvidence]],
    ) -> SimilarDealsDraft:
        client = self._get_groq_client()
        payload = {
            "current_deal_id": current_deal_id,
            "current_deal_memories": [
                item.model_dump(mode="json") for item in current_evidence
            ],
            "historical_deals": {
                deal_id: [item.model_dump(mode="json") for item in evidence]
                for deal_id, evidence in historical_evidence.items()
            },
        }
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SIMILAR_DEALS_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "similar_deals",
                        "strict": False,
                        "schema": SimilarDealsDraft.model_json_schema(),
                    },
                },
            )
        except APIError as exc:
            raise SimilarDealsError("Groq similar-deal comparison failed.") from exc

        if not response.choices:
            raise SimilarDealsError("Groq returned no similar-deal comparison.")
        message = response.choices[0].message
        if message.refusal:
            raise SimilarDealsError("Groq refused to compare historical deals.")
        if not message.content:
            raise SimilarDealsError("Groq returned an empty similar-deal comparison.")
        try:
            return SimilarDealsDraft.model_validate_json(message.content)
        except ValidationError as exc:
            raise SimilarDealsError(
                "Groq returned comparisons that did not match the response schema."
            ) from exc

    def _validate_and_build(
        self,
        draft: SimilarDealsDraft,
        current_deal_id: str,
        current_evidence: list[BriefEvidence],
        historical_evidence: dict[str, list[BriefEvidence]],
    ) -> list[SimilarDeal]:
        current_by_id = {item.memory_id: item for item in current_evidence}
        matches: list[SimilarDeal] = []
        returned_deal_ids: set[str] = set()
        for candidate in draft.deals:
            if not candidate.is_similar:
                continue
            deal_id = candidate.historical_deal_id
            if deal_id == current_deal_id:
                raise SimilarDealsError("The current deal cannot be a historical match.")
            if deal_id in returned_deal_ids:
                raise SimilarDealsError("Groq returned a historical deal more than once.")
            returned_deal_ids.add(deal_id)
            deal_memory = historical_evidence.get(deal_id)
            if not deal_memory:
                raise SimilarDealsError(
                    "Groq returned a historical deal that was not recalled."
                )
            historical_by_id = {item.memory_id: item for item in deal_memory}
            historical_ids = set(historical_by_id)
            current_ids = set(current_by_id)
            reason_ids = set(candidate.reason_memory_ids)
            if (
                not reason_ids
                or not reason_ids.issubset(current_ids | historical_ids)
                or not reason_ids.intersection(current_ids)
                or not reason_ids.intersection(historical_ids)
            ):
                raise SimilarDealsError(
                    "A similarity reason must cite recalled memories from both deals."
                )
            if not candidate.similarity_reason or not candidate.matching_characteristics:
                raise SimilarDealsError(
                    "A similar deal needs a reason and matching characteristics."
                )
            for match in candidate.matching_characteristics:
                if not set(match.current_memory_ids).issubset(current_ids):
                    raise SimilarDealsError(
                        "A similarity cites current-deal memory IDs that were not recalled."
                    )
                if not set(match.historical_memory_ids).issubset(historical_ids):
                    raise SimilarDealsError(
                        "A similarity cites historical memory IDs from another deal."
                    )
            if candidate.historical_outcome and any(
                historical_by_id[memory_id].memory_type != "deal_outcome"
                for memory_id in candidate.historical_outcome.memory_ids
                if memory_id in historical_ids
            ):
                raise SimilarDealsError(
                    "A historical outcome must cite deal-outcome memories."
                )
            if candidate.historical_outcome and not set(
                candidate.historical_outcome.memory_ids
            ).issubset(historical_ids):
                raise SimilarDealsError("A historical outcome cites unknown memory IDs.")
            if candidate.useful_lesson and any(
                historical_by_id[memory_id].memory_type != "lesson_learned"
                for memory_id in candidate.useful_lesson.memory_ids
                if memory_id in historical_ids
            ):
                raise SimilarDealsError("A useful lesson must cite lesson memories.")
            if candidate.useful_lesson and not set(
                candidate.useful_lesson.memory_ids
            ).issubset(historical_ids):
                raise SimilarDealsError("A useful lesson cites unknown memory IDs.")

            cited_current = list(reason_ids.intersection(current_ids))
            cited_historical = list(reason_ids.intersection(historical_ids))
            for match in candidate.matching_characteristics:
                cited_current.extend(match.current_memory_ids)
                cited_historical.extend(match.historical_memory_ids)
            if candidate.historical_outcome:
                cited_historical.extend(candidate.historical_outcome.memory_ids)
            if candidate.useful_lesson:
                cited_historical.extend(candidate.useful_lesson.memory_ids)

            company_names = {
                item.customer_company
                for item in deal_memory
                if item.customer_company
            }
            matches.append(
                SimilarDeal(
                    historical_deal_id=deal_id,
                    company_name=next(iter(company_names))
                    if len(company_names) == 1
                    else None,
                    similarity_reason=candidate.similarity_reason,
                    reason_memory_ids=candidate.reason_memory_ids,
                    matching_characteristics=candidate.matching_characteristics,
                    historical_outcome=candidate.historical_outcome,
                    useful_lesson=candidate.useful_lesson,
                    current_evidence=self._select_evidence(
                        cited_current, current_by_id
                    ),
                    historical_evidence=self._select_evidence(
                        cited_historical, historical_by_id
                    ),
                )
            )
        return matches

    @staticmethod
    def _select_evidence(
        memory_ids: list[str], available: dict[str, BriefEvidence]
    ) -> list[BriefEvidence]:
        return [available[memory_id] for memory_id in dict.fromkeys(memory_ids)]

    def _get_groq_client(self) -> Groq:
        if self._groq_client is None:
            if not self._groq_api_key:
                raise SimilarDealsConfigurationError(
                    "GROQ_API_KEY is required to compare similar deals."
                )
            self._groq_client = Groq(api_key=self._groq_api_key)
        return self._groq_client
