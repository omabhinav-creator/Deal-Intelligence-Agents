"""Typed result contracts for evidence-backed deal intelligence."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from Hindsight.memory.memory_schema import MemoryType


class Evidence(BaseModel):
	"""A source memory used to support an intelligence result."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	memory_id: str = Field(min_length=1)
	deal_id: str = Field(min_length=1)
	memory_type: MemoryType
	content: str = Field(min_length=1)
	timestamp: datetime | None = None


class ClaimKind(str, Enum):
	"""Whether a claim reports evidence or interprets it."""

	OBSERVED_FACT = "observed_fact"
	INTERPRETATION = "interpretation"


class Insight(BaseModel):
	"""An evidence-linked observation or explicitly labeled interpretation."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	statement: str = Field(min_length=1)
	kind: ClaimKind
	evidence: list[Evidence] = Field(default_factory=list)
	confidence: float | None = Field(default=None, ge=0, le=1)
	uncertainty: str | None = Field(default=None, min_length=1)


class Recommendation(BaseModel):
	"""A proposed action with its rationale, evidence, and limitations."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	action: str = Field(min_length=1)
	reason: str = Field(min_length=1)
	unresolved_issue_or_opportunity: str | None = Field(default=None, min_length=1)
	evidence: list[Evidence] = Field(default_factory=list)
	uncertainty: str | None = Field(default=None, min_length=1)
	limitations: list[str] = Field(default_factory=list)


class WhatChangedResult(BaseModel):
	"""Evidence-backed changes observed across a deal's interactions."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	deal_id: str = Field(min_length=1)
	insights: list[Insight] = Field(default_factory=list)
	insufficient_evidence: bool = False
	limitations: list[str] = Field(default_factory=list)


class NextBestActionResult(BaseModel):
	"""Recommended actions for a deal, with evidence and uncertainty."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	deal_id: str = Field(min_length=1)
	recommendations: list[Recommendation] = Field(default_factory=list)
	insufficient_evidence: bool = False
	limitations: list[str] = Field(default_factory=list)


class DealOutcome(str, Enum):
	"""Known high-level deal outcome; unknown remains explicitly representable."""

	WON = "won"
	LOST = "lost"
	OPEN = "open"
	STALLED = "stalled"
	UNKNOWN = "unknown"


class SimilarDeal(BaseModel):
	"""A candidate comparable deal and the evidence for its relevance."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	deal_id: str = Field(min_length=1)
	similarity_explanation: str = Field(min_length=1)
	matching_characteristics: list[str] = Field(default_factory=list)
	outcome: DealOutcome | None = None
	lesson: Insight | None = None
	reference_evidence: list[Evidence] = Field(default_factory=list)
	evidence: list[Evidence] = Field(default_factory=list)
	uncertainty: str | None = Field(default=None, min_length=1)


class SimilarDealsResult(BaseModel):
	"""Comparable deals returned for a target deal."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	deal_id: str = Field(min_length=1)
	similar_deals: list[SimilarDeal] = Field(default_factory=list)
	insufficient_evidence: bool = False
	limitations: list[str] = Field(default_factory=list)


class ObjectionState(str, Enum):
	"""Recognized state or direction of an objection over time."""

	NEWLY_APPEARING = "newly_appearing"
	RECURRING = "recurring"
	INCREASING = "increasing"
	DECREASING = "decreasing"
	RESOLVED = "resolved"
	UNRESOLVED = "unresolved"


class ObjectionTransition(BaseModel):
	"""A state change with source memories for both its context and support."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	from_state: ObjectionState | None = None
	to_state: ObjectionState
	date: datetime | None = None
	evidence: list[Evidence] = Field(default_factory=list)
	uncertainty: str | None = Field(default=None, min_length=1)


class ObjectionEvolution(BaseModel):
	"""The observed history and transitions of one objection."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	objection: str = Field(min_length=1)
	stakeholder: str | None = Field(default=None, min_length=1)
	transitions: list[ObjectionTransition] = Field(default_factory=list)
	insufficient_evidence: bool = False
	limitations: list[str] = Field(default_factory=list)


class ObjectionEvolutionResult(BaseModel):
	"""Objection histories for a deal."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	deal_id: str = Field(min_length=1)
	objections: list[ObjectionEvolution] = Field(default_factory=list)
	insufficient_evidence: bool = False
	limitations: list[str] = Field(default_factory=list)


class Pattern(BaseModel):
	"""A pattern claim that keeps observations separate from interpretation."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	description: str = Field(min_length=1)
	observations: list[Insight] = Field(default_factory=list)
	observed_outcomes: list[DealOutcome] = Field(default_factory=list)
	supporting_deal_ids: list[str] = Field(default_factory=list)
	evidence: list[Evidence] = Field(default_factory=list)
	interpretation: str | None = Field(default=None, min_length=1)
	hypothesis: str | None = Field(default=None, min_length=1)
	interpretation_evidence: list[Evidence] = Field(default_factory=list)
	other_outcome_evidence: list[Evidence] = Field(default_factory=list)
	uncertainty: str | None = Field(default=None, min_length=1)
	insufficient_evidence: bool = False


class WinningLossPatternsResult(BaseModel):
	"""Observed patterns among deals with known outcomes."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	patterns: list[Pattern] = Field(default_factory=list)
	insufficient_evidence: bool = False
	limitations: list[str] = Field(default_factory=list)


class DealAutopsy(BaseModel):
	"""Evidence-backed post-outcome review with facts, interpretations, lessons."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	deal_id: str = Field(min_length=1)
	outcome: DealOutcome
	timeline: list[Insight] = Field(default_factory=list)
	objections: list[Insight] = Field(default_factory=list)
	stakeholders: list[Insight] = Field(default_factory=list)
	competitors: list[Insight] = Field(default_factory=list)
	pricing: list[Insight] = Field(default_factory=list)
	requirements: list[Insight] = Field(default_factory=list)
	turning_points: list[Insight] = Field(default_factory=list)
	actions: list[Insight] = Field(default_factory=list)
	resolved_issues: list[Insight] = Field(default_factory=list)
	unresolved_issues: list[Insight] = Field(default_factory=list)
	observed_factors: list[Insight] = Field(default_factory=list)
	interpretations: list[Insight] = Field(default_factory=list)
	lessons: list[Insight] = Field(default_factory=list)
	evidence: list[Evidence] = Field(default_factory=list)
	insufficient_evidence: bool = False
	limitations: list[str] = Field(default_factory=list)
