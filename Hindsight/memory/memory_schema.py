"""Validated DealMind memory records and their Hindsight metadata."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MemoryType(str, Enum):
	"""Categories that distinguish the kinds of facts stored for a deal."""

	DEAL = "deal"
	CUSTOMER = "customer"
	CUSTOMER_REQUIREMENT = "customer_requirement"
	INTERACTION = "interaction"
	OBJECTION = "objection"
	STAKEHOLDER = "stakeholder"
	STAKEHOLDER_CONCERN = "stakeholder_concern"
	COMPETITOR = "competitor"
	PRICING_DISCUSSION = "pricing_discussion"
	CUSTOMER_REQUEST = "customer_request"
	COMMITMENT = "commitment"
	SALES_ACTION = "sales_action"
	IMPORTANT_FACT = "important_fact"
	RISK = "risk"
	BUYING_SIGNAL = "buying_signal"
	UNRESOLVED_QUESTION = "unresolved_question"
	DEAL_OUTCOME = "deal_outcome"
	LESSON_LEARNED = "lesson_learned"


class DealMemory(BaseModel):
	"""One fact or event associated with a DealMind sales deal."""

	model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

	deal_id: str = Field(min_length=1)
	memory_type: MemoryType
	content: str = Field(min_length=1)
	customer_name: str | None = Field(default=None, min_length=1)
	interaction_id: str | None = Field(default=None, min_length=1)
	interaction_date: datetime | None = None
	interaction_source: str | None = Field(default=None, min_length=1)
	stakeholder_name: str | None = Field(default=None, min_length=1)
	status: str | None = Field(default=None, min_length=1)

	def to_hindsight_metadata(self) -> dict[str, str]:
		"""Return string metadata suitable for the Hindsight retain API."""
		metadata = {
			"deal_id": self.deal_id,
			"memory_type": self.memory_type.value,
		}
		optional_metadata = {
			"customer_name": self.customer_name,
			"interaction_id": self.interaction_id,
			"interaction_date": (
				self.interaction_date.isoformat() if self.interaction_date else None
			),
			"interaction_source": self.interaction_source,
			"stakeholder_name": self.stakeholder_name,
			"status": self.status,
		}
		metadata.update(
			{key: value for key, value in optional_metadata.items() if value is not None}
		)
		return metadata

	def to_hindsight_tags(self) -> list[str]:
		"""Build the two common Hindsight filters for deal and memory category."""
		return [f"deal:{self.deal_id}", f"type:{self.memory_type.value}"]