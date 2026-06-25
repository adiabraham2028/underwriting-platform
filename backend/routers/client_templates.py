import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.client_template import ClientTemplate
from models.user import User
from routers.auth import get_current_user, get_tenant_id
from schemas.client_template import ClientTemplateOut, UpdateCellMappingRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/my/template", tags=["client-templates"])


def _get_tab_names(file_data: bytes, filename: str) -> list[str]:
    """Extract sheet names from an Excel file."""
    try:
        import openpyxl
        import io
        wb = openpyxl.load_workbook(io.BytesIO(file_data), read_only=True, keep_vba=True)
        return list(wb.sheetnames)
    except Exception as e:
        logger.warning(f"Could not read tab names from {filename}: {e}")
        return []


@router.get("", response_model=ClientTemplateOut)
async def get_active_template(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the active client template for the current tenant."""
    tenant_id = get_tenant_id(current_user)
    result = await db.execute(
        select(ClientTemplate)
        .where(ClientTemplate.tenant_id == tenant_id, ClientTemplate.is_active == True)
        .order_by(ClientTemplate.version.desc())
        .limit(1)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="No active template found")
    return ClientTemplateOut.model_validate(template)


@router.post("", response_model=ClientTemplateOut)
async def upload_template(
    name: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a new client template (.xlsm or .xlsx)."""
    tenant_id = get_tenant_id(current_user)

    if not file.filename.endswith(('.xlsx', '.xlsm')):
        raise HTTPException(status_code=400, detail="Only .xlsx or .xlsm files are supported")

    file_data = await file.read()

    # Get highest current version
    result = await db.execute(
        select(ClientTemplate)
        .where(ClientTemplate.tenant_id == tenant_id)
        .order_by(ClientTemplate.version.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    new_version = (latest.version + 1) if latest else 1

    # Deactivate existing active templates
    active_result = await db.execute(
        select(ClientTemplate).where(
            ClientTemplate.tenant_id == tenant_id,
            ClientTemplate.is_active == True,
        )
    )
    for t in active_result.scalars().all():
        t.is_active = False

    tab_names = _get_tab_names(file_data, file.filename)

    template = ClientTemplate(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        version=new_version,
        file_data=file_data,
        cell_mapping={},
        mapping_confirmed=False,
        is_active=True,
        tab_names=tab_names,
        created_at=datetime.now(timezone.utc),
        created_by=current_user.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return ClientTemplateOut.model_validate(template)


@router.get("/mapping", response_model=dict)
async def get_cell_mapping(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the cell mapping for the active template."""
    tenant_id = get_tenant_id(current_user)
    result = await db.execute(
        select(ClientTemplate)
        .where(ClientTemplate.tenant_id == tenant_id, ClientTemplate.is_active == True)
        .order_by(ClientTemplate.version.desc())
        .limit(1)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="No active template found")
    return template.cell_mapping or {}


@router.put("/mapping", response_model=ClientTemplateOut)
async def update_cell_mapping(
    body: UpdateCellMappingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the cell mapping for the active template."""
    tenant_id = get_tenant_id(current_user)
    result = await db.execute(
        select(ClientTemplate)
        .where(ClientTemplate.tenant_id == tenant_id, ClientTemplate.is_active == True)
        .order_by(ClientTemplate.version.desc())
        .limit(1)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="No active template found")

    template.cell_mapping = body.cell_mapping
    if body.mapping_confirmed is not None:
        template.mapping_confirmed = body.mapping_confirmed
    await db.commit()
    await db.refresh(template)
    return ClientTemplateOut.model_validate(template)


@router.get("/versions", response_model=list[ClientTemplateOut])
async def list_template_versions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all versions of the client template."""
    tenant_id = get_tenant_id(current_user)
    result = await db.execute(
        select(ClientTemplate)
        .where(ClientTemplate.tenant_id == tenant_id)
        .order_by(ClientTemplate.version.desc())
    )
    templates = result.scalars().all()
    return [ClientTemplateOut.model_validate(t) for t in templates]


@router.post("/{template_id}/activate", response_model=ClientTemplateOut)
async def activate_template_version(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Switch the active version to the specified template."""
    tenant_id = get_tenant_id(current_user)

    # Deactivate all
    all_result = await db.execute(
        select(ClientTemplate).where(ClientTemplate.tenant_id == tenant_id)
    )
    for t in all_result.scalars().all():
        t.is_active = False

    # Activate target
    target = await db.get(ClientTemplate, template_id)
    if not target or target.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Template not found")
    target.is_active = True
    await db.commit()
    await db.refresh(target)
    return ClientTemplateOut.model_validate(target)
