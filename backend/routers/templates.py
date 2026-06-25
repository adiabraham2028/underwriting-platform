import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database import get_db
from models.template import Template
from models.deal import Deal
from schemas.template import TemplateOut, TemplateMappingUpdate
from routers.auth import get_current_user, require_admin
from models.user import User
from services.excel_extractor import get_excel_structure
from services.llm_service import llm
import prompts.template_mapping as tmpl_prompt

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Template).order_by(Template.created_at.desc()))
    return [TemplateOut.model_validate(t) for t in result.scalars().all()]


@router.get("/default", response_model=TemplateOut)
async def get_default_template(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Template).where(Template.is_default == True, Template.is_active == True)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="No default template found")
    return TemplateOut.model_validate(template)


@router.post("", response_model=TemplateOut, status_code=201)
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    file_bytes = await file.read()

    fname = (file.filename or '').lower()
    allowed_mimes = {
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel.sheet.macroEnabled.12',
        'application/octet-stream',  # some browsers send this for both
    }
    if not (fname.endswith('.xlsx') or fname.endswith('.xlsm')):
        raise HTTPException(status_code=400, detail="Only .xlsx or .xlsm files are accepted")

    # Determine version
    result = await db.execute(select(Template).where(Template.name == name).order_by(Template.version.desc()))
    existing = result.scalars().first()
    version = (existing.version + 1) if existing else 1

    # Analyze template structure for auto-mapping
    try:
        structure = get_excel_structure(file_bytes)
        cell_mapping_result = await llm.complete_json(
            tmpl_prompt.SYSTEM if hasattr(tmpl_prompt, "SYSTEM") else "You are a real estate financial modeling expert. Analyze Excel template structure and suggest cell mappings. Return only valid JSON.",
            tmpl_prompt.build_prompt(structure),
        )
        cell_mapping = cell_mapping_result.get("cell_mapping", {})
    except Exception as e:
        cell_mapping = {}

    template = Template(
        id=uuid.uuid4(),
        name=name,
        version=version,
        is_default=False,
        file_data=file_bytes,
        cell_mapping=cell_mapping,
        created_at=datetime.now(timezone.utc),
        created_by=current_user.id,
        is_active=True,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return TemplateOut.model_validate(template)


@router.get("/{template_id}/mapping")
async def get_template_mapping(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = await db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"cell_mapping": template.cell_mapping}


@router.put("/{template_id}/mapping")
async def update_template_mapping(
    template_id: uuid.UUID,
    mapping_update: TemplateMappingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    template = await db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template.cell_mapping = mapping_update.cell_mapping
    await db.commit()
    return {"cell_mapping": template.cell_mapping}


@router.post("/{template_id}/set-default")
async def set_default_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    template = await db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Get current default
    result = await db.execute(select(Template).where(Template.is_default == True))
    old_default = result.scalar_one_or_none()

    if old_default and old_default.id != template_id:
        old_default.is_default = False
        # Mark deals with old template as outdated
        await db.execute(
            update(Deal)
            .where(Deal.active_template_id == old_default.id)
            .values(template_outdated=True)
        )

    template.is_default = True
    await db.commit()
    return {"message": f"Template '{template.name}' v{template.version} set as default"}
