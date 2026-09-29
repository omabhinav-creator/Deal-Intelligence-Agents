"""Deterministic, evidence-backed deal intelligence services."""

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from backend.memory.hindsight_client import HindsightMemoryClient
from Hindsight.ai.intelligence_schemas import (
	ClaimKind,
	DealOutcome,
	Evidence,
	Insight,
	NextBestActionResult,
	ObjectionEvolution,
	ObjectionEvolutionResult,
	ObjectionState,
	ObjectionTransition,
	Pattern,
	Recommendation,
	SimilarDeal,
	SimilarDealsResult,
	WhatChangedResult,
	WinningLossPatternsResult,
)
from Hindsight.memory.memory_schema import MemoryType


_STOP_WORDS = {
	"about", "after", "also", "and", "are", "asked", "been", "before",
	"buyer", "customer", "deal", "from", "have", "into", "mentioned",
	"needs", "their", "they", "this", "with", "would",
	"concern", "concerns", "objection", "objections", "issue", "issues",
	"discussion", "discussed", "risk", "risks",
	"pricing", "requirement", "requirements", "competitor", "competitors",
	"requested", "request", "evaluation", "evaluated", "mentioned",
	"product", "software", "solution", "platform", "service", "services",
	"being", "remain", "remains", "still", "evaluating", "evaluation",
	"meeting", "call", "review", "discuss", "team", "business", "need",
	"considered", "similar", "comparing", "compare", "compared",
}

_CATEGORY_LABELS = {
	MemoryType.OBJECTION: "objection",
	MemoryType.STAKEHOLDER_CONCERN: "concern",
	MemoryType.STAKEHOLDER: "stakeholder",
	MemoryType.COMPETITOR: "competitor",
	MemoryType.PRICING_DISCUSSION: "pricing discussion",
	MemoryType.CUSTOMER_REQUIREMENT: "requirement",
	MemoryType.BUYING_SIGNAL: "buying signal",
	MemoryType.RISK: "risk",
	MemoryType.COMMITMENT: "commitment",
	MemoryType.UNRESOLVED_QUESTION: "unresolved issue",
	MemoryType.CUSTOMER_REQUEST: "customer request",
	MemoryType.IMPORTANT_FACT: "important change",
}

_NEXT_ACTIONS = {
	MemoryType.OBJECTION: (
		"Clarify and address the documented objection",
		"Confirm what would resolve the recorded objection.",
	),
	MemoryType.STAKEHOLDER_CONCERN: (
		"Discuss the documented stakeholder concern",
		"Clarify the concern and what evidence or response would address it.",
	),
	MemoryType.PRICING_DISCUSSION: (
		"Follow up on the documented pricing discussion",
		"Clarify the commercial question or information recorded in the discussion.",
	),
	MemoryType.COMPETITOR: (
		"Clarify the documented competitive evaluation",
		"Ask which evaluation criteria matter and address only the comparison recorded in the memory.",
	),
	MemoryType.CUSTOMER_REQUEST: (
		"Respond to the documented customer request",
		"Confirm the requested deliverable and any details still needed to fulfill it.",
	),
	MemoryType.BUYING_SIGNAL: (
		"Follow up on the documented buying signal",
		"Confirm the customer's intended next step and decision process.",
	),
	MemoryType.RISK: (
		"Investigate and reduce the documented deal risk",
		"Clarify the risk's current status and the information needed to address it.",
	),
	MemoryType.UNRESOLVED_QUESTION: (
		"Resolve the documented open question",
		"Provide or obtain an answer to the question recorded in the memory.",
	),
	MemoryType.COMMITMENT: (
		"Follow through on the documented commitment",
		"Confirm completion or communicate the current status of the recorded commitment.",
	),
	MemoryType.SALES_ACTION: (
		"Complete or update the documented follow-up action",
		"Check the recorded action's status and close the loop with the relevant party.",
	),
	MemoryType.CUSTOMER_REQUIREMENT: (
		"Validate the documented customer requirement",
		"Confirm how the recorded requirement will be met and identify any remaining gap.",
	),
}

_POSITIVE_STATES = {"resolved", "closed", "addressed", "complete", "completed", "approved"}
_OPEN_STATES = {"open", "unresolved", "active", "pending", "blocked", "rejected"}

_SIMILARITY_TYPES = {
	MemoryType.OBJECTION,
	MemoryType.STAKEHOLDER_CONCERN,
	MemoryType.COMPETITOR,
	MemoryType.CUSTOMER_REQUIREMENT,
	MemoryType.CUSTOMER_REQUEST,
	MemoryType.PRICING_DISCUSSION,
	MemoryType.BUYING_SIGNAL,
	MemoryType.RISK,
	MemoryType.UNRESOLVED_QUESTION,
}

_SIMILARITY_LABELS = {
	MemoryType.OBJECTION: "objection",
	MemoryType.STAKEHOLDER_CONCERN: "stakeholder concern",
	MemoryType.COMPETITOR: "competitor mention",
	MemoryType.CUSTOMER_REQUIREMENT: "customer requirement",
	MemoryType.CUSTOMER_REQUEST: "customer request",
	MemoryType.PRICING_DISCUSSION: "pricing discussion",
	MemoryType.BUYING_SIGNAL: "buying signal",
	MemoryType.RISK: "risk",
	MemoryType.UNRESOLVED_QUESTION: "unresolved question",
}


def what_changed(
	deal_id: str,
	memory_client: HindsightMemoryClient | None = None,
) -> WhatChangedResult:
	"""Compare dated memories for a deal and report changes with source evidence.

	The service is deterministic and makes no LLM calls. A change is reported only
	when the recall response contains dated memories with usable source IDs and a
	recognized DealMind memory type.
	"""
	deal_id = deal_id.strip() if isinstance(deal_id, str) else ""
	if not deal_id:
		raise ValueError("deal_id must not be empty.")

	client = memory_client or HindsightMemoryClient()
	query = (
		f"What changed over time for deal {deal_id}? Identify earlier and recent "
		"objections, concerns, stakeholders, competitors, pricing, requirements, "
		"buying signals, risks, commitments, unresolved issues, and important facts."
	)

	recall_response = client.recall_memory(query, tags=[f"deal:{deal_id}"], max_tokens=4096)
	memory_objects = getattr(recall_response, "results", None) or []

	memories: list[tuple[datetime, Evidence]] = []
	limitations: list[str] = []
	for memory in memory_objects:
		if not _memory_belongs_to_deal(memory, deal_id):
			continue
		evidence = _to_evidence(memory, deal_id)
		if evidence is None:
			limitations.append("Some matching memories lacked a usable ID, type, or content.")
			continue
		timestamp = _memory_timestamp(memory)
		if timestamp is None:
			limitations.append("Some matching memories had no usable interaction timestamp.")
			continue
		memories.append((timestamp, evidence))

	if len(memories) < 2 or len({timestamp for timestamp, _ in memories}) < 2:
		limitations.append("At least two dated memory times are required to identify change.")
		return WhatChangedResult(
			deal_id=deal_id,
			insufficient_evidence=True,
			limitations=list(dict.fromkeys(limitations)),
		)

	latest_timestamp = max(timestamp for timestamp, _ in memories)
	older = [item for timestamp, item in memories if timestamp < latest_timestamp]
	recent = [item for timestamp, item in memories if timestamp == latest_timestamp]
	if not older or not recent:
		limitations.append("Older and most recent dated memories could not be separated.")
		return WhatChangedResult(
			deal_id=deal_id,
			insufficient_evidence=True,
			limitations=list(dict.fromkeys(limitations)),
		)

	insights: list[Insight] = []
	for current in recent:
		category = current.memory_type
		if category not in _CATEGORY_LABELS:
			continue
		status = _status_for_memory(memory_objects, current.memory_id)
		if category in {MemoryType.OBJECTION, MemoryType.STAKEHOLDER_CONCERN} and status in {
			"resolved", "closed", "addressed"
		}:
			insights.append(
				Insight(
					statement="The concern is explicitly marked resolved in the most recent memory.",
					kind=ClaimKind.OBSERVED_FACT,
					evidence=[current],
					confidence=0.95,
				)
			)
			continue
		if category in {MemoryType.OBJECTION, MemoryType.STAKEHOLDER_CONCERN} and status in {
			"decreasing", "reduced", "less severe"
		}:
			insights.append(
				Insight(
					statement="The concern is explicitly marked as decreasing in the most recent memory.",
					kind=ClaimKind.OBSERVED_FACT,
					evidence=[current],
					confidence=0.9,
				)
			)
			continue
		matching_older = [
			item
			for item in older
			if _same_topic(current, item)
		]
		label = _CATEGORY_LABELS[category]
		if matching_older:
			if category in {MemoryType.OBJECTION, MemoryType.STAKEHOLDER_CONCERN}:
				statement = f"The {label} continues in the most recent dated memory."
			else:
				statement = f"The {label} recurs in the most recent dated memory."
			evidence = [matching_older[-1], current]
		else:
			statement = f"A new {label} appears in the most recent dated memory."
			evidence = [current]
		insights.append(
			Insight(
				statement=statement,
				kind=ClaimKind.OBSERVED_FACT,
				evidence=evidence,
				confidence=0.75 if matching_older else 0.9,
				uncertainty=(
					"Topic matching uses memory category and shared content terms."
					if matching_older
					else None
				),
			)
		)

	if not insights:
		limitations.append("No supported change was identified in the recognized memory categories.")
	return WhatChangedResult(
		deal_id=deal_id,
		insights=insights,
		insufficient_evidence=not bool(insights),
		limitations=list(dict.fromkeys(limitations)),
	)


def get_next_best_action(
	deal_id: str,
	memory_client: HindsightMemoryClient | None = None,
) -> NextBestActionResult:
	"""Recommend evidence-grounded next steps from one deal's recalled memories."""
	deal_id = deal_id.strip() if isinstance(deal_id, str) else ""
	if not deal_id:
		raise ValueError("deal_id must not be empty.")

	client = memory_client or HindsightMemoryClient()
	query = (
		f"Based on recorded evidence, what should the sales representative consider "
		f"doing next for deal {deal_id}? Review open objections, concerns, requests, "
		"commitments, risks, questions, requirements, buying signals, pricing, and competitors."
	)
	try:
		recall_response = client.recall_memory(
			query,
			tags=[f"deal:{deal_id}"],
			max_tokens=4096,
		)
	except Exception:
		return NextBestActionResult(
			deal_id=deal_id,
			insufficient_evidence=True,
			limitations=["Deal memory recall failed; no recommendation was generated."],
		)

	memory_objects = getattr(recall_response, "results", None) or []
	usable: list[tuple[Any, Evidence]] = []
	limitations: list[str] = []
	for memory in memory_objects:
		if not _memory_belongs_to_deal(memory, deal_id):
			continue
		evidence = _to_evidence(memory, deal_id)
		if evidence is None:
			limitations.append("Some deal memories lacked a usable ID, type, or content and were omitted.")
			continue
		if evidence.memory_type in _NEXT_ACTIONS:
			usable.append((memory, evidence))

	if not usable:
		limitations.append("No relevant, usable memories support a meaningful next action.")
		return NextBestActionResult(
			deal_id=deal_id,
			insufficient_evidence=True,
			limitations=list(dict.fromkeys(limitations)),
		)

	usable.sort(key=lambda pair: _memory_timestamp(pair[0]) or datetime.min.replace(tzinfo=timezone.utc))
	conflicts, conflicted_ids = _find_conflicts(usable)
	recommendations = list(conflicts)

	for memory, evidence in reversed(usable):
		if evidence.memory_id in conflicted_ids:
			continue
		if (
			evidence.memory_type
			in {
				MemoryType.OBJECTION,
				MemoryType.STAKEHOLDER_CONCERN,
				MemoryType.RISK,
				MemoryType.UNRESOLVED_QUESTION,
				MemoryType.COMMITMENT,
				MemoryType.SALES_ACTION,
			}
			and _status_polarity(memory) == 1
		):
			limitations.append(
				f"A { _CATEGORY_LABELS.get(evidence.memory_type, 'deal issue') } memory is marked complete or resolved and was not recommended again."
			)
			continue
		action_template = _NEXT_ACTIONS.get(evidence.memory_type)
		if action_template is None:
			continue
		action_prefix, reason = action_template
		stakeholder = (_value(memory, "metadata") or {}).get("stakeholder_name")
		stakeholder_context = f" for {stakeholder}" if isinstance(stakeholder, str) and stakeholder.strip() else ""
		recommendations.append(
			Recommendation(
				action=f"{action_prefix}{stakeholder_context}: {evidence.content}",
				reason=f"The recalled memory records: {evidence.content}",
				unresolved_issue_or_opportunity=evidence.content,
				evidence=[evidence],
				limitations=[reason],
			)
		)
		if len(recommendations) >= 3:
			break

	if not recommendations:
		limitations.append("The available memories were conflicting and require status confirmation.")
		return NextBestActionResult(
			deal_id=deal_id,
			insufficient_evidence=True,
			limitations=list(dict.fromkeys(limitations)),
		)

	return NextBestActionResult(
		deal_id=deal_id,
		recommendations=recommendations,
		limitations=list(dict.fromkeys(limitations)),
	)


def _find_conflicts(
	memories: list[tuple[Any, Evidence]],
) -> tuple[list[Recommendation], set[str]]:
	"""Retain explicit opposing statuses as a single reconcile-first action."""
	recommendations: list[Recommendation] = []
	conflicted_ids: set[str] = set()
	for index, (first_memory, first) in enumerate(memories):
		first_polarity = _status_polarity(first_memory)
		if first_polarity is None:
			continue
		for second_memory, second in memories[index + 1 :]:
			if second.memory_id in conflicted_ids or first.memory_id in conflicted_ids:
				continue
			if not _same_topic(first, second):
				continue
			if _status_polarity(second_memory) != -first_polarity:
				continue
			label = _CATEGORY_LABELS.get(first.memory_type, "deal issue")
			recommendations.append(
				Recommendation(
					action=f"Verify the current status of the recorded {label} before deciding how to proceed.",
					reason=(
					f"The memories disagree: one records \"{first.content}\" and another records "
					f"\"{second.content}\"."
					),
					unresolved_issue_or_opportunity=(
					f"Whether this {label} is currently resolved remains unclear."
					),
					evidence=[first, second],
					uncertainty="The recorded statuses conflict; confirm the current state with the deal team or customer.",
					limitations=["No side of the conflicting evidence was selected as authoritative."],
				)
			)
			conflicted_ids.update({first.memory_id, second.memory_id})
	return recommendations, conflicted_ids


def find_similar_deals(
	deal_id: str,
	memory_client: HindsightMemoryClient | None = None,
) -> SimilarDealsResult:
	"""Find historical deals with multiple evidence-backed shared characteristics."""
	deal_id = deal_id.strip() if isinstance(deal_id, str) else ""
	if not deal_id:
		raise ValueError("deal_id must not be empty.")

	client = memory_client or HindsightMemoryClient()
	current_query = (
		f"Retrieve deal facts and characteristics for {deal_id}, including objections, "
		"concerns, competitors, requirements, requests, pricing, buying signals, risks, and questions."
	)
	historical_query = (
		"Find memories from historical deals with overlapping sales characteristics, "
		"including objections, concerns, competitors, requirements, requests, pricing, "
		"buying signals, risks, outcomes, and lessons learned."
	)
	try:
		current_response = client.recall_memory(
			current_query,
			tags=[f"deal:{deal_id}"],
			max_tokens=4096,
		)
		historical_response = client.recall_memory(historical_query, max_tokens=4096)
	except Exception:
		return SimilarDealsResult(
			deal_id=deal_id,
			insufficient_evidence=True,
			limitations=["Deal memory recall failed; no similar deals were returned."],
		)

	limitations: list[str] = []
	current_memories: list[Evidence] = []	
	for memory in getattr(current_response, "results", None) or []:
		if not _memory_belongs_to_deal(memory, deal_id):
			continue
		evidence = _to_evidence(memory, deal_id)
		if evidence is None:
			limitations.append("Some reference deal memories lacked a usable ID, type, or content.")
		elif evidence.memory_type in _SIMILARITY_TYPES:
			current_memories.append(evidence)

	candidates: dict[str, list[Evidence]] = {}
	for memory in getattr(historical_response, "results", None) or []:
		candidate_id = _deal_id_for_memory(memory)
		if candidate_id is None:
			limitations.append("Some historical memories lacked an identifiable deal ID and were omitted.")
			continue
		if candidate_id == deal_id:
			continue
		if not _memory_belongs_to_deal(memory, candidate_id):
			continue
		evidence = _to_evidence(memory, candidate_id)
		if evidence is None:
			limitations.append("Some historical memories lacked a usable ID, type, or content.")
			continue
		candidates.setdefault(candidate_id, []).append(evidence)

	if not current_memories:
		limitations.append("The reference deal has no usable similarity characteristics.")
	if not candidates:
		limitations.append("No identifiable historical deal memories were returned.")
		return SimilarDealsResult(
			deal_id=deal_id,
			insufficient_evidence=True,
			limitations=list(dict.fromkeys(limitations)),
		)

	results: list[SimilarDeal] = []
	for candidate_id, candidate_memories in candidates.items():
		characteristics: list[str] = []
		reference_evidence: list[Evidence] = []
		historical_evidence: list[Evidence] = []
		matched_types: set[MemoryType] = set()
		for current in current_memories:
			for historical in candidate_memories:
				if current.memory_type != historical.memory_type:
					continue
				shared_terms = _shared_characteristic_terms(current, historical)
				if not shared_terms:
					continue
				label = _SIMILARITY_LABELS[current.memory_type]
				characteristic = f"Shared {label} references: {', '.join(shared_terms)}."
				if characteristic not in characteristics:
					characteristics.append(characteristic)
					matched_types.add(current.memory_type)
					reference_evidence.append(current)
					historical_evidence.append(historical)
		if len(matched_types) < 2:
			continue

		outcome, outcome_evidence = _known_outcome(candidate_memories)
		lesson, lesson_evidence = _recorded_lesson(candidate_memories)
		all_historical_evidence = _unique_evidence(
			historical_evidence + outcome_evidence + lesson_evidence
		)
		results.append(
			SimilarDeal(
				deal_id=candidate_id,
				similarity_explanation=(
					f"{candidate_id} shares {len(matched_types)} supported characteristics "
					f"with {deal_id}: {'; '.join(characteristics)}"
				),
				matching_characteristics=characteristics,
				outcome=outcome,
				lesson=lesson,
				reference_evidence=_unique_evidence(reference_evidence),
				evidence=all_historical_evidence,
			)
		)

	results.sort(key=lambda candidate: (-len(candidate.matching_characteristics), candidate.deal_id.casefold()))
	if not results:
		limitations.append("No historical deal met the minimum of two distinct supported characteristics.")
	return SimilarDealsResult(
		deal_id=deal_id,
		similar_deals=results,
		insufficient_evidence=not bool(results),
		limitations=list(dict.fromkeys(limitations)),
	)


def get_objection_evolution(
	deal_id: str,
	memory_client: HindsightMemoryClient | None = None,
) -> ObjectionEvolutionResult:
	"""Track dated objection and concern memories without inferring resolution."""
	deal_id = deal_id.strip() if isinstance(deal_id, str) else ""
	if not deal_id:
		raise ValueError("deal_id must not be empty.")

	client = memory_client or HindsightMemoryClient()
	query = (
		f"How have objections and concerns changed over time for deal {deal_id}? "
		"Retrieve objections, stakeholder concerns, risks, unresolved questions, "
		"their dates, statuses, and any explicit evidence that they were addressed."
	)
	try:
		recall_response = client.recall_memory(
			query,
			tags=[f"deal:{deal_id}"],
			max_tokens=4096,
		)
	except Exception:
		return ObjectionEvolutionResult(
			deal_id=deal_id,
			insufficient_evidence=True,
			limitations=["Deal memory recall failed; objection evolution could not be assessed."],
		)

	issue_types = {
		MemoryType.OBJECTION,
		MemoryType.STAKEHOLDER_CONCERN,
		MemoryType.RISK,
		MemoryType.UNRESOLVED_QUESTION,
	}
	observations: list[tuple[datetime, Any, Evidence]] = []
	limitations: list[str] = []
	for memory in getattr(recall_response, "results", None) or []:
		if not _memory_belongs_to_deal(memory, deal_id):
			continue
		evidence = _to_evidence(memory, deal_id)
		if evidence is None:
			limitations.append("Some deal memories lacked a usable ID, type, or content and were omitted.")
			continue
		if evidence.memory_type not in issue_types:
			continue
		timestamp = _memory_timestamp(memory)
		if timestamp is None:
			limitations.append("Some objection or concern memories had no usable timestamp and were omitted.")
			continue
		observations.append((timestamp, memory, evidence))

	if not observations:
		limitations.append("No dated objection or concern memories were available.")
		return ObjectionEvolutionResult(
			deal_id=deal_id,
			insufficient_evidence=True,
			limitations=list(dict.fromkeys(limitations)),
		)

	observations.sort(key=lambda item: item[0])
	clusters: list[list[tuple[datetime, Any, Evidence]]] = []
	for observation in observations:
		for cluster in clusters:
			if any(_same_objection_topic(observation[2], previous[2]) for previous in cluster):
				cluster.append(observation)
				break
		else:
			clusters.append([observation])

	evolutions: list[ObjectionEvolution] = []
	for cluster in clusters:
		cluster.sort(key=lambda item: item[0])
		first_timestamp, first_memory, first_evidence = cluster[0]
		stakeholder = (_value(first_memory, "metadata") or {}).get("stakeholder_name")
		transitions: list[ObjectionTransition] = []
		first_explicit_state = _explicit_objection_state(first_memory)
		first_state = first_explicit_state or ObjectionState.NEWLY_APPEARING
		transitions.append(
			ObjectionTransition(
				from_state=None,
				to_state=first_state,
				date=first_timestamp,
				evidence=[first_evidence],
				uncertainty=(
					"This is the first matching mention in returned memories; earlier history may be missing."
					if first_explicit_state is None
					else None
				),
			)
		)
		previous_timestamp = first_timestamp
		previous_evidence = first_evidence
		previous_state = first_state
		meaningful_evolution = False
		for timestamp, memory, evidence in cluster[1:]:
			if timestamp <= previous_timestamp:
				continue
			explicit_state = _explicit_objection_state(memory)
			if explicit_state == ObjectionState.RESOLVED:
				target_state = ObjectionState.RESOLVED
				transition_evidence = [previous_evidence, evidence]
				uncertainty = None
				meaningful_evolution = True
			elif (
				previous_state == ObjectionState.RESOLVED
				and explicit_state is not None
				and explicit_state != ObjectionState.RESOLVED
			):
				target_state = ObjectionState.UNRESOLVED
				transition_evidence = [previous_evidence, evidence]
				uncertainty = "Earlier evidence marks the issue resolved, while later evidence indicates it may remain active."
				meaningful_evolution = True
			elif explicit_state in {ObjectionState.INCREASING, ObjectionState.DECREASING}:
				target_state = explicit_state
				transition_evidence = [previous_evidence, evidence]
				uncertainty = None
				meaningful_evolution = True
			else:
				target_state = ObjectionState.RECURRING
				transition_evidence = [previous_evidence, evidence]
				uncertainty = (
					"The issue recurs, but the memories do not establish whether its severity changed."
					if explicit_state is None
					else None
				)
				meaningful_evolution = True
			transitions.append(
				ObjectionTransition(
					from_state=previous_state,
					to_state=target_state,
					date=timestamp,
					evidence=_unique_evidence(transition_evidence),
					uncertainty=uncertainty,
				)
			)
			previous_timestamp = timestamp
			previous_evidence = evidence
			previous_state = target_state

		if not meaningful_evolution:
			limitations.append(
				f"The {first_evidence.memory_type.value} history has no later distinct timestamp to establish evolution."
			)
		evolutions.append(
			ObjectionEvolution(
				objection=first_evidence.content,
				stakeholder=stakeholder,
				transitions=transitions,
				insufficient_evidence=not meaningful_evolution,
				limitations=(
					["No later distinct timestamp can establish an evolution."]
					if not meaningful_evolution
					else []
				),
			)
		)

	return ObjectionEvolutionResult(
		deal_id=deal_id,
		objections=evolutions,
		insufficient_evidence=not any(not item.insufficient_evidence for item in evolutions),
		limitations=list(dict.fromkeys(limitations)),
	)


def _same_objection_topic(first: Evidence, second: Evidence) -> bool:
	"""Match related issue types by substantive normalized content terms."""
	issue_types = {
		MemoryType.OBJECTION,
		MemoryType.STAKEHOLDER_CONCERN,
		MemoryType.RISK,
		MemoryType.UNRESOLVED_QUESTION,
	}
	if first.memory_type not in issue_types or second.memory_type not in issue_types:
		return False
	category_words = {"concern", "concerns", "objection", "objections", "risk", "risks", "issue", "issues"}
	first_terms = _objection_terms(first.content, category_words)
	second_terms = _objection_terms(second.content, category_words)
	if not first_terms or not second_terms:
		return first.content.casefold().strip() == second.content.casefold().strip()
	shared = first_terms & second_terms
	return bool(shared) and len(shared) / min(len(first_terms), len(second_terms)) >= 0.5


def _objection_terms(content: str, category_words: set[str]) -> set[str]:
	terms = {
		{"pricing": "price", "prices": "price"}.get(word, word)
		for word in re.findall(r"[a-z0-9]+", content.casefold())
		if len(word) > 2 and word not in (_STOP_WORDS - {"pricing"}) and word not in category_words
	}
	return terms


def _explicit_objection_state(memory: Any) -> ObjectionState | None:
	metadata = _value(memory, "metadata") or {}
	status = metadata.get("status")
	text = _value(memory, "text")
	value = status.casefold().strip() if isinstance(status, str) else ""
	if not value and isinstance(text, str):
		value = text.casefold()
	if re.search(r"\b(not resolved|unresolved|remains open|still open|still a concern|remains a concern|not addressed|continues unresolved)\b", value):
		return ObjectionState.UNRESOLVED
	if re.search(r"\b(resolved|closed|addressed|successfully handled|no longer an issue)\b", value):
		return ObjectionState.RESOLVED
	if re.search(r"\b(decreasing|reduced|less severe|easing|improving)\b", value):
		return ObjectionState.DECREASING
	if re.search(r"\b(increasing|worsening|more severe|escalating)\b", value):
		return ObjectionState.INCREASING
	return None


def _deal_id_for_memory(memory: Any) -> str | None:
	metadata = _value(memory, "metadata") or {}
	deal_id = metadata.get("deal_id")
	if isinstance(deal_id, str) and deal_id.strip():
		return deal_id.strip()
	for tag in _value(memory, "tags") or []:
		if isinstance(tag, str) and tag.startswith("deal:") and tag[5:].strip():
			return tag[5:].strip()
	return None


def _shared_characteristic_terms(first: Evidence, second: Evidence) -> list[str]:
	first_terms = _topic_terms(first.content)
	second_terms = _topic_terms(second.content)
	shared = first_terms & second_terms
	if not shared:
		return []
	return sorted(shared)


def _known_outcome(memories: list[Evidence]) -> tuple[DealOutcome | None, list[Evidence]]:
	for evidence in memories:
		if evidence.memory_type != MemoryType.DEAL_OUTCOME:
			continue
		text = evidence.content.casefold()
		if re.search(r"\b(won't|not won|did not win|didn't win|unwon|not lost|did not lose|not stalled)\b", text):
			continue
		if re.search(r"\b(stalled|stalled out)\b", text):
			return DealOutcome.STALLED, [evidence]
		if re.search(r"\b(won|closed won)\b", text):
			return DealOutcome.WON, [evidence]
		if re.search(r"\b(lost|closed lost)\b", text):
			return DealOutcome.LOST, [evidence]
		if re.search(r"\b(open|in progress|ongoing)\b", text):
			return DealOutcome.OPEN, [evidence]
	return None, []


def _recorded_lesson(memories: list[Evidence]) -> tuple[Insight | None, list[Evidence]]:
	for evidence in memories:
		if evidence.memory_type == MemoryType.LESSON_LEARNED:
			lesson = Insight(
				statement=f"Recorded lesson: {evidence.content}",
				kind=ClaimKind.OBSERVED_FACT,
				evidence=[evidence],
			)
			return lesson, [evidence]
	return None, []


def analyze_patterns(
	memory_client: HindsightMemoryClient | None = None,
) -> WinningLossPatternsResult:
	"""Summarize recurring memory characteristics by explicit deal outcome.

	Patterns are descriptive co-occurrences. This function does not infer that a
	characteristic caused a deal outcome.
	"""
	client = memory_client or HindsightMemoryClient()
	query = (
		"Retrieve historical deal memories with explicit outcomes and related "
		"objections, stakeholder concerns, competitors, pricing, requirements, "
		"customer requests, buying signals, risks, unresolved questions, sales actions, "
		"and lessons learned. Include deal IDs and outcome records."
	)
	try:
		recall_response = client.recall_memory(query, max_tokens=4096)
	except Exception:
		return WinningLossPatternsResult(
			insufficient_evidence=True,
			limitations=["Historical deal recall failed; no outcome patterns were analyzed."],
		)

	limitations: list[str] = []
	deals: dict[str, list[Evidence]] = {}
	for memory in getattr(recall_response, "results", None) or []:
		deal_id = _deal_id_for_memory(memory)
		if deal_id is None:
			limitations.append("Some memories lacked an identifiable deal ID and were omitted.")
			continue
		if not _memory_belongs_to_deal(memory, deal_id):
			continue
		evidence = _to_evidence(memory, deal_id)
		if evidence is None:
			limitations.append("Some deal memories lacked a usable ID, type, or content and were omitted.")
			continue
		deals.setdefault(deal_id, []).append(evidence)

	deal_outcomes: dict[str, DealOutcome] = {}
	for deal_id, memories in deals.items():
		outcomes: list[tuple[DealOutcome, Evidence]] = []
		for evidence in memories:
			if evidence.memory_type != MemoryType.DEAL_OUTCOME:
				continue
			matching_memory = next(
				(
					item
					for item in getattr(recall_response, "results", None) or []
					if _value(item, "id") == evidence.memory_id
				),
				None,
			)
			status = (_value(matching_memory, "metadata") or {}).get("status") if matching_memory else None
			for outcome in {
				_parse_explicit_outcome(evidence.content),
				_parse_explicit_outcome(status) if isinstance(status, str) else None,
			}:
				if outcome is not None:
					outcomes.append((outcome, evidence))
		if not outcomes:
			continue
		unique_outcomes = {outcome for outcome, _ in outcomes}
		if len(unique_outcomes) != 1:
			limitations.append(f"Conflicting explicit outcomes for {deal_id}; deal excluded from outcome groups.")
			continue
		deal_outcomes[deal_id] = outcomes[0][0]

	if len(deal_outcomes) < 2:
		limitations.append("Fewer than two deals have consistent, explicit outcomes.")
		return WinningLossPatternsResult(
			insufficient_evidence=True,
			limitations=list(dict.fromkeys(limitations)),
		)

	feature_types = {
		MemoryType.OBJECTION,
		MemoryType.STAKEHOLDER_CONCERN,
		MemoryType.COMPETITOR,
		MemoryType.PRICING_DISCUSSION,
		MemoryType.CUSTOMER_REQUIREMENT,
		MemoryType.CUSTOMER_REQUEST,
		MemoryType.BUYING_SIGNAL,
		MemoryType.RISK,
		MemoryType.UNRESOLVED_QUESTION,
		MemoryType.SALES_ACTION,
		MemoryType.LESSON_LEARNED,
	}
	# Group source memories by memory type and conservative local semantic similarity.
	# Each group retains every original evidence record and its canonical deal ID.
	feature_groups: list[dict[str, Any]] = []
	for deal_id, outcome in deal_outcomes.items():
		for evidence in deals[deal_id]:
			if evidence.memory_type not in feature_types:
				continue
			tokens = _semantic_pattern_tokens(evidence.content)
			if not tokens:
				continue
			group = next(
				(
					candidate
					for candidate in feature_groups
					if candidate["memory_type"] == evidence.memory_type
					and _pattern_similarity(tokens, candidate["tokens"]) >= 0.75
				),
				None,
			)
			if group is None:
				group = {"memory_type": evidence.memory_type, "tokens": tokens, "deals": {}}
				feature_groups.append(group)
			group["deals"].setdefault(outcome, {}).setdefault(deal_id, []).append(evidence)

	# Index where each characteristic also appears under other known outcomes.
	patterns: list[Pattern] = []
	for group in feature_groups:
		memory_type = group["memory_type"]
		for outcome, supporting_deals in group["deals"].items():
			if len(supporting_deals) < 2:
				continue
			label = _SIMILARITY_LABELS.get(memory_type, _CATEGORY_LABELS.get(memory_type, memory_type.value.replace("_", " ")))
			support_evidence = _unique_evidence(
				[evidence for records in supporting_deals.values() for evidence in records]
			)
			deal_ids = sorted(supporting_deals, key=str.casefold)
			observations = [
				Insight(
					statement=f"{supported_deal} has a {label} memory supporting this recurring pattern.",
					kind=ClaimKind.OBSERVED_FACT,
					evidence=_unique_evidence(records),
				)
				for supported_deal, records in supporting_deals.items()
			]
			other_support: list[Evidence] = []
			other_outcomes: list[str] = []
			for other_outcome, other_deals in group["deals"].items():
				if other_outcome == outcome or not other_deals:
					continue
				other_outcomes.append(other_outcome.value.upper())
				other_support.extend(
					evidence for records in other_deals.values() for evidence in records
				)
			uncertainty = None
			if other_outcomes:
				uncertainty = (
					f"The characteristic also appears in explicit {' and '.join(sorted(other_outcomes))} "
					"outcome deals; it is not exclusive to this outcome."
				)
			patterns.append(
				Pattern(
					description=f"Among explicit {outcome.value.upper()} deals, recurring {label} pattern: {support_evidence[0].content}",
					occurrence_count=len(support_evidence),
					observations=observations,
					observed_outcomes=[outcome],
					supporting_deal_ids=deal_ids,
					evidence=support_evidence,
					interpretation=(
						"This is a descriptive co-occurrence in the recalled sample; it does not establish that the characteristic caused the outcome."
					),
					hypothesis=None,
					interpretation_evidence=support_evidence,
					other_outcome_evidence=_unique_evidence(other_support),
					uncertainty=uncertainty,
				)
			)

	patterns.sort(
		key=lambda item: (
			item.observed_outcomes[0].value if item.observed_outcomes else "",
			item.description.casefold(),
		)
	)
	patterns = _deduplicate_patterns(patterns)
	if not patterns:
		limitations.append("No characteristic recurred across at least two deals with the same explicit outcome.")
	return WinningLossPatternsResult(
		patterns=patterns,
		insufficient_evidence=not bool(patterns),
		limitations=list(dict.fromkeys(limitations)),
	)


def _normalized_pattern_text(text: str) -> str:
	"""Normalize typography and spacing while preserving the complete wording."""
	text = unicodedata.normalize("NFKC", text).casefold()
	return " ".join(re.findall(r"[a-z0-9]+", text))


def _semantic_pattern_tokens(text: str) -> set[str]:
	"""Return conservative, synonym-normalized content words for pattern grouping."""
	synonyms = {
		"stakeholders": "stakeholder",
		"engage": "alignment", "engaged": "alignment", "engaging": "alignment",
		"engagement": "alignment", "align": "alignment", "aligned": "alignment",
		"improves": "improve", "improved": "improve", "improving": "improve",
		"progression": "progress", "progressed": "progress", "advances": "progress",
		"advance": "progress", "advancing": "progress", "moves": "progress",
		"move": "progress", "forward": "progress",
		"deals": "deal", "helps": "help",
	}
	ignored = _STOP_WORDS | {
		"deal", "deals", "memory", "memories", "pattern", "patterns", "among",
		"explicit", "appear", "appears", "appeared", "across", "recurring",
		"containing", "contains", "supporting", "support", "supports",
		"winning", "won", "lost", "stalled",
		"open", "outcome", "outcomes", "sales", "team", "teams", "business",
		"help",
	}
	result = set()
	for word in re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", text).casefold()):
		canonical = synonyms.get(word, word)
		if len(canonical) >= 4 and canonical not in ignored:
			result.add(canonical)
	return result


def _pattern_similarity(first: set[str], second: set[str]) -> float:
	if not first or not second:
		return 0.0
	return len(first & second) / len(first | second)


def _deduplicate_patterns(patterns: list[Pattern]) -> list[Pattern]:
	"""Merge exact normalized duplicates without clustering partially similar claims."""
	unique: dict[tuple[tuple[str, ...], str], Pattern] = {}
	for pattern in patterns:
		key = (tuple(sorted(outcome.value for outcome in pattern.observed_outcomes)), _normalized_pattern_text(pattern.description))
		current = unique.get(key)
		if current is None:
			unique[key] = pattern
			continue
		current.occurrence_count += pattern.occurrence_count
		current.supporting_deal_ids = list(dict.fromkeys(current.supporting_deal_ids + pattern.supporting_deal_ids))
		current.evidence = _unique_evidence(current.evidence + pattern.evidence)
		current.interpretation_evidence = _unique_evidence(current.interpretation_evidence + pattern.interpretation_evidence)
		current.other_outcome_evidence = _unique_evidence(current.other_outcome_evidence + pattern.other_outcome_evidence)
		for observation in pattern.observations:
			match = next((existing for existing in current.observations if _normalized_pattern_text(existing.statement) == _normalized_pattern_text(observation.statement)), None)
			if match is None:
				current.observations.append(observation)
			else:
				match.evidence = _unique_evidence(match.evidence + observation.evidence)
		current.observed_outcomes = list(dict.fromkeys(current.observed_outcomes + pattern.observed_outcomes))
	return list(unique.values())


def _parse_explicit_outcome(content: str) -> DealOutcome | None:
	text = content.casefold()
	if re.search(r"\b(won't|not won|did not win|didn't win|unwon|not lost|did not lose|not stalled)\b", text):
		return None
	if re.search(r"\b(stalled|stalled out)\b", text):
		return DealOutcome.STALLED
	if re.search(r"\b(lost|closed lost)\b", text):
		return DealOutcome.LOST
	if re.search(r"\b(won|closed won)\b", text):
		return DealOutcome.WON
	return None


def _unique_evidence(evidence: list[Evidence]) -> list[Evidence]:
	seen: set[tuple[str, str]] = set()
	unique: list[Evidence] = []
	for item in evidence:
		key = (item.deal_id, item.memory_id)
		if key not in seen:
			seen.add(key)
			unique.append(item)
	return unique


def _status_polarity(memory: Any) -> int | None:
	metadata = _value(memory, "metadata") or {}
	status = metadata.get("status")
	if isinstance(status, str):
		words = set(re.findall(r"[a-z]+", status.casefold()))
		if words & _POSITIVE_STATES:
			return 1
		if words & _OPEN_STATES:
			return -1
	content = _value(memory, "text")
	if not isinstance(content, str):
		return None
	text = content.casefold()
	if re.search(r"\b(not resolved|unresolved|still open|remains open|not addressed)\b", text):
		return -1
	if re.search(r"\b(resolved|closed|addressed|completed|approved)\b", text):
		return 1
	if re.search(r"\b(open|pending|blocked|rejected)\b", text):
		return -1
	return None
def _memory_belongs_to_deal(memory: Any, deal_id: str) -> bool:
	"""Apply the brief generator's metadata-first, tag-fallback deal guard."""
	metadata = _value(memory, "metadata") or {}
	metadata_deal_id = metadata.get("deal_id")
	if metadata_deal_id is not None:
		return metadata_deal_id == deal_id
	return f"deal:{deal_id}" in (_value(memory, "tags") or [])


def _to_evidence(memory: Any, requested_deal_id: str) -> Evidence | None:
	metadata = _value(memory, "metadata") or {}
	memory_id = _value(memory, "id")
	content = _value(memory, "text")
	if not isinstance(memory_id, str) or not memory_id.strip():
		memory_id = metadata.get("interaction_id")
	if not isinstance(memory_id, str) or not memory_id.strip():
		return None
	if not isinstance(content, str) or not content.strip():
		return None
	deal_id = metadata.get("deal_id") or requested_deal_id
	if not isinstance(deal_id, str) or not deal_id.strip():
		return None
	raw_type = metadata.get("memory_type") or _value(memory, "type")
	try:
		memory_type = MemoryType(raw_type)
	except (TypeError, ValueError):
		return None
	return Evidence(
		memory_id=memory_id,
		deal_id=deal_id,
		memory_type=memory_type,
		content=content,
		timestamp=_memory_timestamp(memory),
	)


def _memory_timestamp(memory: Any) -> datetime | None:
	metadata = _value(memory, "metadata") or {}
	for candidate in (
		metadata.get("interaction_date"),
		_value(memory, "occurred_start"),
		_value(memory, "mentioned_at"),
	):
		if isinstance(candidate, datetime):
			return candidate if candidate.tzinfo else candidate.replace(tzinfo=timezone.utc)
		if isinstance(candidate, str) and candidate.strip():
			try:
				parsed = datetime.fromisoformat(candidate.strip().replace("Z", "+00:00"))
				return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
			except ValueError:
				continue
	return None


def _status_for_memory(memories: list[Any], memory_id: str) -> str | None:
	for memory in memories:
		metadata = _value(memory, "metadata") or {}
		candidate_id = _value(memory, "id") or metadata.get("interaction_id")
		if candidate_id == memory_id:
			status = metadata.get("status")
			return status.casefold().strip() if isinstance(status, str) else None
	return None


def _same_topic(first: Evidence, second: Evidence) -> bool:
	if first.memory_type != second.memory_type:
		return False
	first_terms = _topic_terms(first.content)
	second_terms = _topic_terms(second.content)
	if not first_terms or not second_terms:
		return first.content.casefold().strip() == second.content.casefold().strip()
	shared = first_terms & second_terms
	return bool(shared) and len(shared) / min(len(first_terms), len(second_terms)) >= 0.5


def _topic_terms(content: str) -> set[str]:
	return {
		word
		for word in re.findall(r"[a-z0-9]+", content.casefold())
		if len(word) > 2 and word not in _STOP_WORDS
	}


def _value(item: Any, key: str) -> Any:
	if isinstance(item, dict):
		return item.get(key)
	return getattr(item, key, None)
