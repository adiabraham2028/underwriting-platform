import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from typing import Optional

from database import get_db
from models.deal import Deal
from models.flag import Flag
from models.snapshot import ModelSnapshot
from models.template import Template
from models.extraction import Extraction
from schemas.deal import DealCreate, DealOut, DealUpdate
from routers.auth import get_current_user, require_admin
from models.user import User
from services.geocoding_service import geocode_address

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("", response_model=list[DealOut])
async def list_deals(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    state: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Deal)
    if state:
        q = q.where(Deal.state == state.upper())
    if status:
        q = q.where(Deal.status == status)
    q = q.offset(skip).limit(limit).order_by(Deal.last_updated.desc())
    result = await db.execute(q)
    deals = result.scalars().all()

    # Get flag counts
    flag_counts_result = await db.execute(
        select(Flag.deal_id, func.count(Flag.id))
        .where(Flag.resolved == False)
        .group_by(Flag.deal_id)
    )
    flag_counts = {row[0]: row[1] for row in flag_counts_result}

    deal_outs = []
    for deal in deals:
        d = DealOut.model_validate(deal)
        d.flag_count = flag_counts.get(deal.id, 0)
        deal_outs.append(d)
    return deal_outs


@router.post("", response_model=DealOut, status_code=status.HTTP_201_CREATED)
async def create_deal(
    deal_data: DealCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate template exists
    template = await db.get(Template, deal_data.template_id)
    if not template or not template.is_active:
        raise HTTPException(status_code=422, detail="Template not found or inactive")

    lat, lng = await geocode_address(deal_data.address, deal_data.city, deal_data.state, deal_data.zip_code)

    deal = Deal(
        id=uuid.uuid4(),
        name=deal_data.name,
        address=deal_data.address,
        city=deal_data.city,
        state=deal_data.state.upper(),
        zip_code=deal_data.zip_code,
        total_units=deal_data.total_units,
        lat=lat,
        lng=lng,
        active_template_id=deal_data.template_id,
        created_by=current_user.id,
    )
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    d = DealOut.model_validate(deal)
    d.flag_count = 0
    return d


@router.get("/{deal_id}", response_model=DealOut)
async def get_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    flag_count_result = await db.execute(
        select(func.count(Flag.id)).where(Flag.deal_id == deal_id, Flag.resolved == False)
    )
    flag_count = flag_count_result.scalar() or 0

    d = DealOut.model_validate(deal)
    d.flag_count = flag_count
    return d


@router.patch("/{deal_id}", response_model=DealOut)
async def update_deal(
    deal_id: uuid.UUID,
    deal_update: DealUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    update_data = deal_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(deal, field, value)
    deal.last_updated = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(deal)
    d = DealOut.model_validate(deal)
    d.flag_count = 0
    return d


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    await db.delete(deal)
    await db.commit()


@router.get("/{deal_id}/flags")
async def get_deal_flags(
    deal_id: uuid.UUID,
    resolved: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    q = select(Flag).where(Flag.deal_id == deal_id)
    if resolved is not None:
        q = q.where(Flag.resolved == resolved)
    q = q.order_by(Flag.severity, Flag.created_at.desc())
    result = await db.execute(q)
    flags = result.scalars().all()
    return [
        {
            "id": str(f.id),
            "deal_id": str(f.deal_id),
            "document_id": str(f.document_id) if f.document_id else None,
            "tab_name": f.tab_name,
            "cell_address": f.cell_address,
            "field_name": f.field_name,
            "flag_type": f.flag_type,
            "description": f.description,
            "severity": f.severity,
            "source_a_label": f.source_a_label,
            "source_a_value": f.source_a_value,
            "source_b_label": f.source_b_label,
            "source_b_value": f.source_b_value,
            "resolved": f.resolved,
            "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
            "created_at": f.created_at.isoformat(),
        }
        for f in flags
    ]


@router.patch("/{deal_id}/flags/{flag_id}")
async def resolve_flag(
    deal_id: uuid.UUID,
    flag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    flag = await db.get(Flag, flag_id)
    if not flag or flag.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Flag not found")
    flag.resolved = True
    flag.resolved_by = current_user.id
    flag.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": str(flag.id), "resolved": True}


@router.get("/{deal_id}/snapshots")
async def get_deal_snapshots(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    result = await db.execute(
        select(ModelSnapshot)
        .where(ModelSnapshot.deal_id == deal_id)
        .order_by(ModelSnapshot.created_at.desc())
    )
    snapshots = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "deal_id": str(s.deal_id),
            "snapshot_name": s.snapshot_name,
            "template_id": str(s.template_id) if s.template_id else None,
            "template_version": s.template_version,
            "created_at": s.created_at.isoformat(),
            "created_by": str(s.created_by),
            "is_active": s.is_active,
        }
        for s in snapshots
    ]


@router.post("/{deal_id}/migrate-template")
async def migrate_template(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from models.template import Template
    from models.extraction import Extraction
    from services.model_populator import build_luckysheet_json, DEFAULT_CELL_MAPPING

    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Get default template
    result = await db.execute(select(Template).where(Template.is_default == True, Template.is_active == True))
    template = result.scalar_one_or_none()

    # Get latest extractions
    extractions_result = await db.execute(select(Extraction).where(Extraction.deal_id == deal_id))
    extractions = extractions_result.scalars().all()

    rr_data = next((e.extracted_data for e in extractions if e.document_type == "rent_roll"), None)
    t12_data = next((e.extracted_data for e in extractions if e.document_type == "t12"), None)
    om_data = next((e.extracted_data for e in extractions if e.document_type == "om"), None)

    cell_mapping = template.cell_mapping if template else DEFAULT_CELL_MAPPING
    luckysheet_json = build_luckysheet_json(rr_data, t12_data, om_data, cell_mapping)

    await db.execute(
        update(ModelSnapshot)
        .where(ModelSnapshot.deal_id == deal_id, ModelSnapshot.is_active == True)
        .values(is_active=False)
    )

    snapshot = ModelSnapshot(
        id=uuid.uuid4(),
        deal_id=deal_id,
        snapshot_name=f"Template Migration {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        luckysheet_json=luckysheet_json,
        template_id=template.id if template else None,
        template_version=template.version if template else None,
        created_at=datetime.now(timezone.utc),
        created_by=current_user.id,
        is_active=True,
    )
    db.add(snapshot)

    deal.active_template_id = template.id if template else None
    deal.template_outdated = False
    deal.last_updated = datetime.now(timezone.utc)

    await db.commit()
    return {"message": "Template migration complete", "snapshot_id": str(snapshot.id)}


@router.get("/{deal_id}/extractions/rent_roll")
async def get_rent_roll_extraction(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return extracted_data from the most recent rent_roll extraction for this deal."""
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    result = await db.execute(
        select(Extraction)
        .where(Extraction.deal_id == deal_id, Extraction.document_type == "rent_roll")
        .order_by(Extraction.created_at.desc())
        .limit(1)
    )
    extraction = result.scalar_one_or_none()
    if not extraction:
        raise HTTPException(status_code=404, detail="No rent roll extraction found")

    return extraction.extracted_data
