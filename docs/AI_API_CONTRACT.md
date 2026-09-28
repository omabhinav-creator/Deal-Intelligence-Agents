# DealMind AI API Contract

This document describes the current FastAPI surface and maps it to the requested
logical `/ai` operations. It is an integration contract for the API as it exists;
it does not add routes. JSON property names use the current Python model names
(snake_case). Enum values are lowercase strings.

Base URL for local development: `http://127.0.0.1:8000`.

## Route mapping

| Logical operation | Current HTTP interface | Status |
| --- | --- | --- |
| `POST /ai/process-interaction` | `POST /api/deals/{deal_id}/interactions` | Implemented under current path |
| `POST /ai/deal-brief` | `GET /api/deals/{deal_id}/brief` | Implemented under current path; read-only GET |
| `POST /ai/ask` | No equivalent route | Not implemented. `HindsightMemoryClient.reflect_memory()` exists, but no question-answer service or API route uses it. |
| `GET /ai/what-changed/{deal_id}` | `GET /api/deals/{deal_id}/changes` | Implemented under current path |
| `GET /ai/similar-deals/{deal_id}` | `GET /api/deals/{deal_id}/similar` | Implemented under current path |
| `POST /ai/recommendation` | `POST /api/deals/{deal_id}/why` | Implemented for explaining a caller-supplied action, not generating an action |
| `POST /ai/outcome` | `POST /api/deals/{deal_id}/outcome` | Implemented; writes outcome and supported lesson memories |
| `GET /ai/deal-autopsy/{deal_id}` | `POST /api/deals/{deal_id}/autopsy` | Implemented under current path; POST body supplies the outcome |

`GET /health` is also available and returns `{"status":"ok"}`.

## Common behavior

- Path parameter `deal_id` is the caller's stable identifier for one deal. Ingestion
  tags each retained record with that deal ID; read operations filter recalled
  records to the requested deal.
- Pydantic validation errors return HTTP 422 with FastAPI's `detail` array.
- Empty/invalid service arguments raised as `ValueError` return HTTP 400:
  `{"detail":"<validation message>"}`.
- Expected service/integration failures return HTTP 502:
  `{"detail":"<safe service message>"}`. A Hindsight/Groq outage or invalid
  generated response can produce this status.
- Unexpected failures return HTTP 500:
  `{"detail":"The DealMind service could not complete the request."}`.
- Unknown paths return HTTP 404 using FastAPI's standard error shape.
- JSON examples below are representative. Results can have empty arrays, `null`
  optional values, or explicit insufficient-evidence flags when source history is
  missing or does not support an answer.

## 1. Process interaction

**Logical name:** `POST /ai/process-interaction`  
**Current route:** `POST /api/deals/{deal_id}/interactions`

Extracts facts from caller-provided meeting notes, converts them to DealMind
memories, and retains each through Hindsight. The response contains extraction,
normalized memory records, and the number successfully retained.

Path: `deal_id` (required, non-empty string). Request body:

```json
{
  "notes": "string, required, non-empty",
  "interaction_date": "string|null, ISO-8601 datetime, optional",
  "source": "string|null, optional; defaults to meeting_notes",
  "interaction_id": "string|null, optional",
  "company": "string|null, optional",
  "stakeholder": "string|null, accepted optional context"
}
```

`stakeholder` is accepted by the HTTP model but is not passed separately to the
existing processing function; stakeholder facts are extracted from `notes`.
Required field: `notes`. All other body fields are optional.

Success response (`200`):

```json
{
  "deal_id": "deal-123",
  "extraction": {
    "customer_company": "Acme",
    "deal_id": null,
    "stakeholders": [{"name": "Jordan Lee", "role": "CTO"}],
    "stakeholder_concerns": [],
    "objections": [{"content": "Needs SSO", "stakeholder_name": "Jordan Lee", "status": null}],
    "competitors": [],
    "pricing_information": [],
    "customer_requirements": [],
    "customer_requests": [],
    "commitments": [],
    "follow_up_actions": [],
    "important_facts": [],
    "risks": [],
    "buying_signals": [],
    "unresolved_questions": []
  },
  "memories": [
    {
      "deal_id": "deal-123",
      "memory_type": "objection",
      "content": "Acme: Needs SSO (stakeholder: Jordan Lee)",
      "customer_name": "Acme",
      "interaction_id": "meeting-456",
      "interaction_date": "2026-09-29T10:00:00Z",
      "interaction_source": "meeting_notes",
      "stakeholder_name": "Jordan Lee",
      "status": null,
      "evidence_basis": null,
      "supporting_memory_ids": []
    }
  ],
  "retained_memory_count": 1
}
```

Representative error (`502`):

```json
{"detail":"Hindsight retain failed after 0 of 1 memories were stored (failed at item 1)."}
```

## 2. Deal Brief

**Logical name:** `POST /ai/deal-brief`  
**Current route:** `GET /api/deals/{deal_id}/brief`

Recalls only this deal's Hindsight evidence and generates a preparation brief.
The current route has no request body; `deal_id` is a required, non-empty path
parameter.

Success response (`200`) has these fields:

```json
{
  "deal_id": "deal-123",
  "customer_company": "Acme",
  "customer_summary": {"statement": "Acme is evaluating the product.", "evidence_ids": ["mem-1"]},
  "current_deal_status": null,
  "key_stakeholders": [],
  "stakeholder_concerns": [],
  "main_objections": [{"statement": "Acme needs SSO.", "evidence_ids": ["mem-1"]}],
  "competitors": [],
  "pricing_discussions": [],
  "customer_requirements": [],
  "previous_commitments": [],
  "recent_developments": [],
  "recommended_preparation": [{"action": "Prepare SSO details.", "rationale": "The buyer raised an SSO objection.", "evidence_ids": ["mem-1"]}],
  "insufficient_information": false,
  "supporting_evidence": [
    {"memory_id":"mem-1","content":"Acme needs SSO.","memory_type":"objection","customer_company":"Acme","interaction_date":"2026-09-29T10:00:00Z","interaction_source":"meeting_notes","interaction_id":"meeting-456","stakeholder_name":"Jordan Lee"}
  ]
}
```

Each factual statement/recommendation cites evidence IDs. With no matching
memories, the route returns `200` with `insufficient_information: true` and empty
evidence. Service failures return `502`; an unsupported citation or response
shape is treated as a service failure.

Example error (`502`): `{"detail":"Groq deal brief request failed."}`.

## 3. Ask a question

**Logical name:** `POST /ai/ask`  
**Current route:** none (HTTP `404`)

There is no caller-facing question-answer operation in `app.py` or an equivalent
question service. The shared Hindsight adapter has a `reflect_memory()` method,
but it is not wired into a product-level service. Therefore this document does
not promise a request or response schema for `/ai/ask`. A caller can currently use
the specific Brief, Changes, Similar Deals, Recommendation Why, Outcome, and
Autopsy operations documented here.

Example error (`404`): `{"detail":"Not Found"}`.

## 4. What Changed

**Logical name:** `GET /ai/what-changed/{deal_id}`  
**Current route:** `GET /api/deals/{deal_id}/changes`

Compares dated memories for the deal and reports evidence-backed transitions.
No request body; `deal_id` is required. At least two distinct dated memories are
needed for a supported comparison.

Success response (`200`):

```json
{
  "deal_id": "deal-123",
  "changes": [
    {
      "change_type": "resolved",
      "category": "objection",
      "summary": "The SSO objection was addressed.",
      "evidence_basis": "observed",
      "earlier_memory_ids": ["mem-1"],
      "later_memory_ids": ["mem-2"]
    }
  ],
  "evidence": [
    {"memory_id":"mem-1","content":"SSO was required.","memory_type":"objection","customer_company":"Acme","interaction_date":"2026-09-20T10:00:00Z","interaction_source":"meeting_notes","interaction_id":"meeting-1","stakeholder_name":"Jordan Lee"},
    {"memory_id":"mem-2","content":"SSO was addressed.","memory_type":"objection","customer_company":"Acme","interaction_date":"2026-09-29T10:00:00Z","interaction_source":"meeting_notes","interaction_id":"meeting-2","stakeholder_name":"Jordan Lee"}
  ],
  "insufficient_history": false,
  "insufficient_reason": null
}
```

When evidence is insufficient, the route returns `200`, sets
`insufficient_history: true`, and includes a reason. Recall/generation failures
return `502`.

Example error (`502`): `{"detail":"Groq deal change analysis failed."}`.

## 5. Similar Deals

**Logical name:** `GET /ai/similar-deals/{deal_id}`  
**Current route:** `GET /api/deals/{deal_id}/similar`

Compares this deal's evidence with memories from other deals. No request body;
`deal_id` is required. Current-deal memories and historical candidates must exist
for a comparison.

Success response (`200`):

```json
{
  "current_deal_id": "deal-123",
  "similar_deals": [
    {
      "historical_deal_id": "deal-087",
      "company_name": "Example Co",
      "similarity_reason": "Both deals required SSO before procurement approval.",
      "reason_memory_ids": ["mem-current", "mem-historical"],
      "matching_characteristics": [
        {"characteristic":"SSO required","evidence_basis":"observed","current_memory_ids":["mem-current"],"historical_memory_ids":["mem-historical"]}
      ],
      "historical_outcome": {"statement":"The deal was won.","memory_ids":["mem-outcome"]},
      "useful_lesson": null,
      "current_evidence": [
        {"memory_id":"mem-current","content":"Acme requires SSO.","memory_type":"customer_requirement","customer_company":"Acme","interaction_date":"2026-09-29T10:00:00Z","interaction_source":"meeting_notes","interaction_id":"meeting-current","stakeholder_name":null}
      ],
      "historical_evidence": [
        {"memory_id":"mem-historical","content":"Example Co required SSO.","memory_type":"customer_requirement","customer_company":"Example Co","interaction_date":"2026-08-10T10:00:00Z","interaction_source":"meeting_notes","interaction_id":"meeting-historical","stakeholder_name":null},
        {"memory_id":"mem-outcome","content":"Deal outcome recorded as won.","memory_type":"deal_outcome","customer_company":"Example Co","interaction_date":"2026-08-20T10:00:00Z","interaction_source":"deal_outcome","interaction_id":"close-review","stakeholder_name":null}
      ]
    }
  ],
  "insufficient_data": false,
  "message": null
}
```

With no usable comparison data, the service returns `200` with
`insufficient_data: true` and a message. Recall/comparison failures return `502`.

Example error (`502`): `{"detail":"Hindsight memory recall failed."}`.

## 6. Recommendation Why / evidence

**Logical name:** `POST /ai/recommendation`  
**Current route:** `POST /api/deals/{deal_id}/why`

Explains whether a caller-provided action is supported by this deal's recalled
memories. It does not generate the action. Path `deal_id` is required. Request:

```json
{"action":"Send the SSO security documentation"}
```

`action` is required and non-empty.

Success response (`200`):

```json
{
  "deal_id": "deal-123",
  "recommended_action": "Send the SSO security documentation",
  "reason": "The CTO's recorded SSO concern supports sending the documentation.",
  "supporting_memories": [
    {"memory_id":"mem-1","content":"The CTO needs SSO documentation.","memory_type":"stakeholder_concern","customer_company":"Acme","interaction_date":"2026-09-29T10:00:00Z","interaction_source":"meeting_notes","interaction_id":"meeting-456","stakeholder_name":"Jordan Lee"}
  ],
  "conflicting_memories": [],
  "insufficient_evidence": false
}
```

No evidence returns `200` with `insufficient_evidence: true`. Unknown cited memory
IDs or service failures return `502`; missing/empty `action` returns `422`.

Example error (`422`): `{"detail":[{"loc":["body","action"],"msg":"Field required","type":"missing"}]}`.

## 7. Outcome Learning

**Logical name:** `POST /ai/outcome`  
**Current route:** `POST /api/deals/{deal_id}/outcome`

Records the outcome in Hindsight, recalls the deal history, and derives supported
facts and lessons. It may retain lesson memories when evidence supports them.
Path `deal_id` is required. Request:

```json
{
  "outcome": "lost",
  "company": "Acme",
  "outcome_date": "2026-09-29T10:00:00Z",
  "interaction_id": "close-review-1"
}
```

Required: `outcome` (`won`, `lost`, or `stalled`). Optional: `company`,
`outcome_date`, `interaction_id`.

Success response (`200`):

```json
{
  "deal_id": "deal-123",
  "outcome": "lost",
  "observed_facts": [{"statement":"The security review remained open.","supporting_memory_ids":["mem-1"]}],
  "lessons": [{"content":"Confirm the security review owner early.","evidence_basis":"inferred","supporting_memory_ids":["mem-1"],"causal_claim":false,"causal_memory_ids":[]}],
  "supporting_evidence": [
    {"memory_id":"mem-1","content":"The security review remained open.","memory_type":"stakeholder_concern","customer_company":"Acme","interaction_date":"2026-09-20T10:00:00Z","interaction_source":"meeting_notes","interaction_id":"meeting-1","stakeholder_name":"Jordan Lee"}
  ],
  "retained_memories": [],
  "insufficient_evidence": false,
  "message": null
}
```

An outcome with no history still records the outcome and returns
`insufficient_evidence: true`. Invalid enum values return `422`; service/retain
failures return `502`.

Example error (`422`): `{"detail":[{"loc":["body","outcome"],"msg":"Field required","type":"missing"}]}`.

## 8. Deal Autopsy

**Logical name:** `GET /ai/deal-autopsy/{deal_id}`  
**Current route:** `POST /api/deals/{deal_id}/autopsy`

Creates a deal retrospective from its recalled history. The current route is POST
because the caller must provide the outcome. Path `deal_id` is required. Request:

```json
{"outcome":"stalled"}
```

Required: `outcome` (`won`, `lost`, or `stalled`).

Success response (`200`):

```json
{
  "deal_id": "deal-123",
  "outcome": "stalled",
  "customer_company": "Acme",
  "timeline": [],
  "major_objections": [],
  "stakeholder_concerns": [],
  "competitors": [],
  "pricing_discussions": [],
  "customer_requirements": [],
  "turning_points": [],
  "actions_taken": [],
  "resolved_issues": [],
  "unresolved_issues": [],
  "observed_factors": [{"statement":"Security approval is pending.","supporting_memory_ids":["mem-1"]}],
  "interpretations": [],
  "lessons_learned": [],
  "insufficient_evidence": false,
  "insufficient_reason": null,
  "supporting_evidence": [
    {"memory_id":"mem-1","content":"Security approval is pending.","memory_type":"stakeholder_concern","customer_company":"Acme","interaction_date":"2026-09-20T10:00:00Z","interaction_source":"meeting_notes","interaction_id":"meeting-1","stakeholder_name":"Jordan Lee"}
  ]
}
```

With no deal memories, the route returns `200` with empty sections,
`insufficient_evidence: true`, and a reason. Invalid outcomes return `422`;
recall/generation failures return `502`.

Example error (`422`): `{"detail":[{"loc":["body","outcome"],"msg":"Field required","type":"missing"}]}`.

## Integration Notes

- **Caller supplied data:** interaction notes and optional interaction metadata;
  a recommendation action; and an explicit outcome for Outcome Learning or
  Autopsy. Deal Brief, Changes, and Similar Deals take only a deal ID.
- **Hindsight retrieved data:** matching deal memories provide source text,
  metadata, tags, dates, and memory IDs. Services scope results to the requested
  deal. Similar Deals also retrieves other deal memories for comparison.
- **Generated intelligence:** extraction output, brief fields, change summaries,
  comparison rationale, recommendation explanation, outcome lessons, and
  autopsy interpretation are generated/derived from the supplied or recalled
  context. They are not themselves source evidence unless separately retained.
- **Evidence IDs:** `memory_id` is assigned by Hindsight. Response citation arrays
  reference these IDs; evidence objects include the corresponding memory text and
  available metadata. Preserve IDs when displaying, storing, or passing citations
  back to another service. IDs are not caller-generated deal IDs.
- **Previous interactions:** Deal Brief, Changes, Similar Deals, Why, and Autopsy
  rely on previously retained interaction memories for useful output. They return
  explicit insufficient-data results when relevant evidence is absent. Outcome
  Learning can record an outcome without prior memories, but cannot learn a
  supported lesson without them. Interaction processing starts the memory history.
- **Read/write behavior:** interaction processing writes extracted memories;
  Outcome Learning writes the outcome and may write lessons. Brief, Changes,
  Similar Deals, Why, and Autopsy only recall memories and generate a response.
  No existing HTTP route performs general-purpose `/ai/ask` reflection.
- **Other service-only functions:** `get_next_best_action()` and the deterministic
  `what_changed()` implementation exist in `Hindsight/ai/intelligence.py`; the
  current FastAPI routes do not call them. The `/changes` route calls
  `DealChangeAnalyzer`, while `/why` explains a caller-supplied action.
- **Errors:** handle 422 as a caller payload/schema error, 400 as a rejected service
  argument, 502 as an expected upstream/service failure, 500 as an unexpected
  server failure, and 404 as an unavailable route. Do not retry memory-writing
  requests blindly after a timeout because the caller may not know whether the
  upstream write completed.
