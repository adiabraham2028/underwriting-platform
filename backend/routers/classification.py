import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.classification import ClassificationSession, ClassificationSessionItem
from models.user import User
from routers.auth import get_current_user, get_tenant_id
from schemas.classification import (
    ClassificationSessionOut,
    ClassificationSessionItemOut,
    UpdateItemCategoryRequest,
)
from services.classification_service import (
    apply_session_to_knowledge_base,
    get_auto_accept_threshold,
)
from services.model_populator import repopulate_model

logger = logging.getLogger(__name__)
router = APIRouter(tags=["classification"])


@router.get("/deals/{deal_id}/classification-session", response_model=ClassificationSessionOut)
async def get_classification_session(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the latest classification session for a deal."""
    result = await db.execute(
        select(ClassificationSession)
        .where(ClassificationSession.deal_id == deal_id)
        .order_by(ClassificationSession.created_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="No classification session found for this deal")

    # Load items
    items_result = await db.execute(
        select(ClassificationSessionItem)
        .where(ClassificationSessionItem.session_id == session.id)
        .order_by(ClassificationSessionItem.display_order)
    )
    items = items_result.scalars().all()

    out = ClassificationSessionOut.model_validate(session)
    out.items = [ClassificationSessionItemOut.model_validate(i) for i in items]
    return out


@router.patch("/deals/{deal_id}/classification-session/items/{item_id}")
async def patch_item_category(
    deal_id: uuid.UUID,
    item_id: uuid.UUID,
    body: UpdateItemCategoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a single item's category without requiring session_id in the path."""
    item = await db.get(ClassificationSessionItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Verify item belongs to a session for this deal
    session_obj = await db.get(ClassificationSession, item.session_id)
    if not session_obj or session_obj.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Item not found for this deal")

    item.final_category = body.final_category
    item.match_type = "human_override"
    item.was_corrected = (body.final_category != item.ai_suggested_category)
    if item.was_corrected:
        session_obj.human_corrected = (session_obj.human_corrected or 0) + 1

    # Save learned mapping for future documents
    from models.classification import LineItemClassification
    from services.seed_classifications import normalize
    from datetime import datetime, timezone
    tenant_id = get_tenant_id(current_user)
    norm = normalize(item.line_item_name)
    existing = await db.execute(
        select(LineItemClassification).where(
            LineItemClassification.tenant_id == tenant_id,
            LineItemClassification.normalized_line_item == norm,
        ).limit(1)
    )
    existing_row = existing.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing_row:
        existing_row.assigned_category = body.final_category
        existing_row.confidence = 1.0
        existing_row.classification_source = "human"
        existing_row.confirmed_by = current_user.id
        existing_row.confirmed_at = now
    else:
        db.add(LineItemClassification(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            original_line_item=item.line_item_name,
            normalized_line_item=norm,
            source_format="broker",
            account_code=item.account_code,
            assigned_category=body.final_category,
            confidence=1.0,
            classification_source="human",
            confirmed_by=current_user.id,
            confirmed_at=now,
            deal_id=deal_id,
            created_at=now,
        ))

    await db.commit()
    return {"ok": True, "item_id": str(item_id), "final_category": item.final_category}


@router.post("/deals/{deal_id}/classification-session/{session_id}/items/{item_id}")
async def update_item_category(
    deal_id: uuid.UUID,
    session_id: uuid.UUID,
    item_id: uuid.UUID,
    body: UpdateItemCategoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a single item's final category (human override)."""
    item = await db.get(ClassificationSessionItem, item_id)
    if not item or item.session_id != session_id:
        raise HTTPException(status_code=404, detail="Item not found")

    old_category = item.final_category
    item.final_category = body.final_category
    item.match_type = "human_override"
    item.was_corrected = (body.final_category != item.ai_suggested_category)

    # Increment human_corrected counter on session
    session_obj = await db.get(ClassificationSession, session_id)
    if session_obj and item.was_corrected:
        session_obj.human_corrected = (session_obj.human_corrected or 0) + 1

    await db.commit()
    return {"ok": True, "item_id": str(item_id), "final_category": item.final_category}


@router.post("/deals/{deal_id}/classification-session/{session_id}/approve")
async def approve_session(
    deal_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve the classification session and apply it to the knowledge base."""
    session_obj = await db.get(ClassificationSession, session_id)
    if not session_obj or session_obj.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Session not found")

    if session_obj.status == "applied":
        raise HTTPException(status_code=400, detail="Session already applied")

    tenant_id = get_tenant_id(current_user)
    now = datetime.now(timezone.utc)

    session_obj.status = "approved"
    session_obj.approved_at = now
    session_obj.approved_by = current_user.id
    await db.flush()

    # Apply human corrections to knowledge base
    await apply_session_to_knowledge_base(session_obj, tenant_id, current_user.id, db)

    session_obj.status = "applied"
    await db.flush()

    # Rebuild model snapshot from approved session items
    await repopulate_model(deal_id, db, current_user.id)

    await db.commit()

    return {"ok": True, "session_id": str(session_id), "status": "applied"}


@router.post("/deals/{deal_id}/classification-session/{session_id}/bulk-approve")
async def bulk_approve_high_confidence(
    deal_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk-accept all items that are high-confidence or exact_known."""
    session_obj = await db.get(ClassificationSession, session_id)
    if not session_obj or session_obj.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Session not found")

    tenant_id = get_tenant_id(current_user)
    threshold = await get_auto_accept_threshold(tenant_id, db)

    items_result = await db.execute(
        select(ClassificationSessionItem).where(
            ClassificationSessionItem.session_id == session_id,
            ClassificationSessionItem.match_type.in_(["exact_known", "ai_high"]),
        )
    )
    items = items_result.scalars().all()

    accepted_count = 0
    for item in items:
        if item.ai_confidence >= threshold or item.match_type == "exact_known":
            # Confirm the AI suggestion as final
            if item.final_category != item.ai_suggested_category:
                item.final_category = item.ai_suggested_category
                item.was_corrected = False
            accepted_count += 1

    # Recount needs_review
    all_items_result = await db.execute(
        select(ClassificationSessionItem).where(
            ClassificationSessionItem.session_id == session_id
        )
    )
    all_items = all_items_result.scalars().all()
    pending = sum(
        1 for i in all_items
        if i.match_type == "ai_low" and i.ai_confidence < threshold
    )
    session_obj.needs_review = pending
    session_obj.auto_accepted = len(all_items) - pending

    await db.commit()
    return {"ok": True, "accepted_count": accepted_count, "remaining_review": pending}
