import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.deal import Deal
from models.extraction import Extraction
from routers.auth import get_current_user
from models.user import User
from services.llm_service import llm
import prompts.ai_search as search_prompt

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/search")
async def ai_search(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    # Build deals context
    result = await db.execute(select(Deal).limit(200))
    deals = result.scalars().all()

    deals_context = [
        {
            "id": str(d.id),
            "name": d.name,
            "address": d.address,
            "city": d.city,
            "state": d.state,
            "zip_code": d.zip_code,
            "total_units": d.total_units,
            "status": d.status,
        }
        for d in deals
    ]

    try:
        search_result = await llm.complete_json(
            search_prompt.SYSTEM,
            search_prompt.build_prompt(query, deals_context),
        )
        ranked_ids = search_result.get("ranked_deal_ids", [])
        explanation = search_result.get("explanation", "")
        interpretation = search_result.get("search_interpretation", "")

        # Return ranked deals
        deal_map = {str(d.id): d for d in deals}
        ranked_deals = []
        for did in ranked_ids:
            if did in deal_map:
                d = deal_map[did]
                ranked_deals.append({
                    "id": str(d.id),
                    "name": d.name,
                    "city": d.city,
                    "state": d.state,
                    "total_units": d.total_units,
                    "status": d.status,
                })

        return {
            "query": query,
            "interpretation": interpretation,
            "results": ranked_deals,
            "explanation": explanation,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI search failed: {str(e)}")


@router.post("/chat")
async def ai_chat(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message = body.get("message", "")
    deal_id = body.get("deal_id")
    history = body.get("history", [])

    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    # Build context
    system_parts = [
        "You are an expert multifamily real estate analyst assistant. "
        "Help analysts understand and underwrite deals. Be specific, data-driven, and concise."
    ]

    if deal_id:
        try:
            deal = await db.get(Deal, uuid.UUID(deal_id))
            if deal:
                system_parts.append(f"\nCurrent deal context: {deal.name} at {deal.address}, {deal.city}, {deal.state}")
                # Get extractions for context
                ex_result = await db.execute(select(Extraction).where(Extraction.deal_id == deal.id))
                extractions = ex_result.scalars().all()
                if extractions:
                    import json
                    for ext in extractions[:3]:
                        system_parts.append(f"\n{ext.document_type.upper()} data: {json.dumps(ext.extracted_data, indent=2)[:2000]}")
        except Exception:
            pass

    system_prompt = "\n".join(system_parts)

    # Build messages
    messages = []
    for h in history[-10:]:  # Last 10 turns
        role = h.get("role", "user")
        content = h.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    try:
        import anthropic
        from config import settings
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        )
        reply = response.content[0].text
        return {"reply": reply, "role": "assistant"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI chat failed: {str(e)}")
