import uuid
import io
import zipfile
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database import get_db
from models.snapshot import ModelSnapshot
from models.deal import Deal
from models.template import Template
from models.extraction import Extraction
from models.classification import ClassificationSession, ClassificationSessionItem
from routers.auth import get_current_user
from models.user import User
from services.excel_exporter import export_populated_model
from services.model_populator import DEFAULT_CELL_MAPPING

router = APIRouter(tags=["models"])


@router.get("/deals/{deal_id}/model")
async def get_model(
    deal_id: uuid.UUID,
    snapshot_id: uuid.UUID = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    if snapshot_id:
        snapshot = await db.get(ModelSnapshot, snapshot_id)
        if not snapshot or snapshot.deal_id != deal_id:
            raise HTTPException(status_code=404, detail="Snapshot not found")
    else:
        result = await db.execute(
            select(ModelSnapshot)
            .where(ModelSnapshot.deal_id == deal_id, ModelSnapshot.is_active == True)
            .order_by(ModelSnapshot.created_at.desc())
        )
        snapshot = result.scalar_one_or_none()

    if not snapshot:
        return {"luckysheet_json": None, "snapshot_id": None}

    return {
        "luckysheet_json": snapshot.luckysheet_json,
        "snapshot_id": str(snapshot.id),
        "snapshot_name": snapshot.snapshot_name,
        "created_at": snapshot.created_at.isoformat(),
    }


@router.put("/deals/{deal_id}/model")
async def save_model(
    deal_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    luckysheet_json = body.get("luckysheet_json")
    snapshot_name = body.get("snapshot_name", f"Manual Save {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}")

    if not luckysheet_json:
        raise HTTPException(status_code=400, detail="luckysheet_json is required")

    # Deactivate current active snapshot
    await db.execute(
        update(ModelSnapshot)
        .where(ModelSnapshot.deal_id == deal_id, ModelSnapshot.is_active == True)
        .values(is_active=False)
    )

    snapshot = ModelSnapshot(
        id=uuid.uuid4(),
        deal_id=deal_id,
        snapshot_name=snapshot_name,
        luckysheet_json=luckysheet_json,
        template_id=deal.active_template_id,
        created_at=datetime.now(timezone.utc),
        created_by=current_user.id,
        is_active=True,
    )
    db.add(snapshot)
    deal.last_updated = datetime.now(timezone.utc)
    await db.commit()

    return {"snapshot_id": str(snapshot.id), "snapshot_name": snapshot.snapshot_name}


@router.get("/deals/{deal_id}/model/export")
async def export_model(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Template is required for export
    if not deal.active_template_id:
        raise HTTPException(
            status_code=400,
            detail="No template assigned to this deal. Please assign a template before exporting.",
        )
    template = await db.get(Template, deal.active_template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template_bytes = template.file_data

    # Get latest classification session
    sess_result = await db.execute(
        select(ClassificationSession)
        .where(ClassificationSession.deal_id == deal_id)
        .order_by(ClassificationSession.created_at.desc())
        .limit(1)
    )
    cls_session = sess_result.scalar_one_or_none()
    if not cls_session:
        raise HTTPException(status_code=400, detail="No classification data found. Upload and process a T12 first.")

    # Get session items
    items_result = await db.execute(
        select(ClassificationSessionItem)
        .where(ClassificationSessionItem.session_id == cls_session.id)
        .order_by(ClassificationSessionItem.display_order)
    )
    session_items = items_result.scalars().all()

    # Get rent roll extraction
    rr_result = await db.execute(
        select(Extraction)
        .where(Extraction.deal_id == deal_id, Extraction.document_type == "rent_roll")
        .order_by(Extraction.created_at.desc())
        .limit(1)
    )
    rr_ext = rr_result.scalar_one_or_none()
    rr_data = rr_ext.extracted_data if rr_ext else {}

    # Get OM extraction
    om_result = await db.execute(
        select(Extraction)
        .where(Extraction.deal_id == deal_id, Extraction.document_type == "om")
        .order_by(Extraction.created_at.desc())
        .limit(1)
    )
    om_ext = om_result.scalar_one_or_none()
    om_data = om_ext.extracted_data if om_ext else {}

    # Get T12 period_start from the T12 extraction data
    t12_result = await db.execute(
        select(Extraction)
        .where(Extraction.deal_id == deal_id, Extraction.document_type == "t12")
        .order_by(Extraction.created_at.desc())
        .limit(1)
    )
    t12_ext = t12_result.scalar_one_or_none()
    period_start = t12_ext.extracted_data.get('period_start') if t12_ext else None

    # Write directly from session items to template
    export_bytes = export_populated_model(
        template_bytes=template_bytes,
        session_items=session_items,
        rent_roll_data=rr_data,
        om_data=om_data,
        unit_type_mapping=deal.unit_type_mapping,  # cached from rent roll upload
        period_start=period_start,                 # e.g. "2025-06-01"
    )

    # Detect .xlsm via VBA bin presence
    try:
        with zipfile.ZipFile(io.BytesIO(template_bytes)) as zf:
            is_xlsm = 'xl/vbaProject.bin' in zf.namelist()
    except Exception:
        is_xlsm = False

    ext = '.xlsm' if is_xlsm else '.xlsx'
    mime = ('application/vnd.ms-excel.sheet.macroEnabled.12' if is_xlsm
            else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    safe_name = deal.name.replace(' ', '_')

    return Response(
        content=export_bytes,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}{ext}"'},
    )


@router.get("/deals/{deal_id}/model/diff")
async def diff_snapshots(
    deal_id: uuid.UUID,
    snapshot_a: uuid.UUID = Query(...),
    snapshot_b: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snap_a = await db.get(ModelSnapshot, snapshot_a)
    snap_b = await db.get(ModelSnapshot, snapshot_b)

    if not snap_a or snap_a.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Snapshot A not found")
    if not snap_b or snap_b.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Snapshot B not found")

    # Compare celldata across sheets
    changed_cells = []
    sheets_a = {s["name"]: s.get("celldata", []) for s in snap_a.luckysheet_json.get("sheets", [])}
    sheets_b = {s["name"]: s.get("celldata", []) for s in snap_b.luckysheet_json.get("sheets", [])}

    all_sheet_names = set(sheets_a.keys()) | set(sheets_b.keys())
    for sheet_name in all_sheet_names:
        cells_a = {(c["r"], c["c"]): c.get("v", {}).get("v") for c in sheets_a.get(sheet_name, [])}
        cells_b = {(c["r"], c["c"]): c.get("v", {}).get("v") for c in sheets_b.get(sheet_name, [])}
        all_coords = set(cells_a.keys()) | set(cells_b.keys())
        for coord in all_coords:
            val_a = cells_a.get(coord)
            val_b = cells_b.get(coord)
            if val_a != val_b:
                changed_cells.append({
                    "sheet": sheet_name,
                    "row": coord[0],
                    "col": coord[1],
                    "value_a": val_a,
                    "value_b": val_b,
                })

    return {
        "snapshot_a_id": str(snapshot_a),
        "snapshot_b_id": str(snapshot_b),
        "changed_cells": changed_cells,
        "total_changes": len(changed_cells),
    }
