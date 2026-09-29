"""MongoDB-backed copilot endpoints that use the backend Groq credential."""

from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from groq import APIStatusError, AsyncGroq
from motor.motor_asyncio import AsyncIOMotorDatabase

from Hindsight.config import get_settings

from ..auth import get_current_user
from ..database import get_database


router = APIRouter(
    prefix="/api/deals/{deal_id}",
    tags=["AI copilot"],
    dependencies=[Depends(get_current_user)],
)
DatabaseDependency = Annotated[AsyncIOMotorDatabase, Depends(get_database)]


@router.post("/brief")
async def generate_deal_brief(
    deal_id: str,
    db: DatabaseDependency,
) -> dict[str, str]:
    """Generate the original MongoDB interaction-timeline brief."""
    if not ObjectId.is_valid(deal_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid deal ID")

    deal = await db["deals"].find_one({"_id": ObjectId(deal_id)})
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    cursor = db["interactions"].find({"deal_id": deal_id}).sort(
        [("meeting_date", 1), ("_id", 1)]
    )
    interactions = await cursor.to_list(length=None)
    interaction_notes = "\n".join(
        f"- {interaction.get('meeting_date', 'Unknown date')}: "
        f"{interaction.get('content', '')} "
        f"Key takeaway: {interaction.get('key_takeaway', '')}"
        for interaction in interactions
    ) or "No interaction notes have been recorded."

    api_key = get_settings().backend_groq_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI brief generation is not configured",
        )

    prompt = (
        "Create a concise sales deal brief based only on the information below. "
        "Summarize deal status, meaningful developments, risks, and recommended next steps.\n\n"
        f"Company: {deal.get('company_name', 'Unknown')}\n"
        f"Value: {deal.get('value', 'Unknown')}\n"
        f"Stage: {deal.get('stage', 'Unknown')}\n"
        f"Risk level: {deal.get('risk_level', 'Unknown')}\n"
        f"Status: {deal.get('status', 'Unknown')}\n\n"
        f"Interaction timeline:\n{interaction_notes}"
    )

    groq_client = AsyncGroq(api_key=api_key, max_retries=0)
    try:
        completion = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are DealMind, a precise and practical sales copilot.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=700,
        )
    except APIStatusError as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            retry_after = exc.response.headers.get("retry-after")
            headers = {"Retry-After": retry_after} if retry_after else None
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Groq is rate-limited (HTTP 429): {exc.message}",
                headers=headers,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"The AI provider could not generate a deal brief (HTTP {exc.status_code}): {exc.message}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider could not generate a deal brief",
        ) from exc
    finally:
        await groq_client.close()

    brief = completion.choices[0].message.content
    if not brief:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider returned an empty brief",
        )
    return {"status": "success", "brief": brief}
