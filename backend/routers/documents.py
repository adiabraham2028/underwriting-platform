import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models.deal import Deal
from models.document import Document
from schemas.document import DocumentOut, DocumentStatusOut
from routers.auth import get_current_user
from models.user import User
from services.pdf_extractor import detect_format
from services.document_processor import process_document

router = APIRouter(tags=["documents"])

VALID_DOC_TYPES = {"rent_roll", "t12", "om", "other"}


@router.post("/deals/{deal_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    deal_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    if document_type not in VALID_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid document_type. Must be one of: {VALID_DOC_TYPES}")

    file_bytes = await file.read()
    file_format = detect_format(file_bytes, file.filename or "unknown")

    # Mark previous documents of same type as not latest
    result = await db.execute(
        select(Document).where(
            Document.deal_id == deal_id,
            Document.document_type == document_type,
            Document.is_latest == True,
        )
    )
    prev_docs = result.scalars().all()
    for prev in prev_docs:
        prev.is_latest = False

    doc = Document(
        id=uuid.uuid4(),
        deal_id=deal_id,
        document_type=document_type,
        file_name=file.filename or "upload",
        file_data=file_bytes,
        file_format=file_format,
        extraction_status="pending",
        uploaded_at=datetime.now(timezone.utc),
        uploaded_by=current_user.id,
        is_latest=True,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    background_tasks.add_task(process_document, doc.id, deal_id, current_user.id)

    return DocumentOut.model_validate(doc)


@router.get("/deals/{deal_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    result = await db.execute(
        select(Document)
        .where(Document.deal_id == deal_id)
        .order_by(Document.uploaded_at.desc())
    )
    docs = result.scalars().all()
    return [DocumentOut.model_validate(d) for d in docs]


@router.get("/deals/{deal_id}/documents/{doc_id}/status", response_model=DocumentStatusOut)
async def get_document_status(
    deal_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await db.get(Document, doc_id)
    if not doc or doc.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentStatusOut(id=doc.id, status=doc.extraction_status, error=doc.extraction_error)


@router.delete("/deals/{deal_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    deal_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await db.get(Document, doc_id)
    if not doc or doc.deal_id != deal_id:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    await db.commit()
