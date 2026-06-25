import uuid
import io
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database import get_db
from models.expense_comp import ExpenseComp
from models.user import User
from routers.auth import get_current_user, get_tenant_id
from schemas.expense_comp import ExpenseCompOut, IncExpVarOut, ComparisonOut, SubjectComparison, CompComparison, ComparisonPeriod
from services.seed_classifications import THE_21_CATEGORIES

logger = logging.getLogger(__name__)
router = APIRouter(tags=["expense-comps"])


def _compute_per_unit(metrics: dict, num_units: int | None) -> tuple[dict, dict]:
    """Compute per-unit/year and per-unit/month metrics from annual totals."""
    if not num_units or num_units == 0:
        return {}, {}
    per_unit_yr = {k: round(v / num_units, 2) for k, v in metrics.items() if isinstance(v, (int, float))}
    per_unit_mo = {k: round(v / num_units / 12, 2) for k, v in per_unit_yr.items()}
    return per_unit_yr, per_unit_mo


def _parse_expense_comp_xlsx(file_data: bytes) -> list[dict]:
    """
    Parse an expense comp import file.
    Expected columns: Property Name, Yardi/MRI Code, Year Built, # Units, Avg SF,
    City, State, Stmt Year, Stmt Type, [category columns...]
    """
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_data), read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            return []
        headers = [str(h).strip() if h is not None else '' for h in rows[0]]

        def col(row, name):
            try:
                idx = headers.index(name)
                return row[idx]
            except ValueError:
                return None

        results = []
        for row in rows[1:]:
            if not any(row):
                continue
            prop_name = col(row, 'Property Name')
            if not prop_name:
                continue
            num_units = col(row, '# Units')
            try:
                num_units = int(num_units) if num_units else None
            except (TypeError, ValueError):
                num_units = None

            avg_sf = col(row, 'Avg SF')
            try:
                avg_sf = float(avg_sf) if avg_sf else None
            except (TypeError, ValueError):
                avg_sf = None

            # Extract category metrics
            metrics = {}
            for cat in THE_21_CATEGORIES:
                val = col(row, cat)
                if val is not None:
                    try:
                        metrics[cat] = float(val)
                    except (TypeError, ValueError):
                        pass

            per_unit_yr, per_unit_mo = _compute_per_unit(metrics, num_units)

            results.append({
                'property_name': str(prop_name),
                'yardi_mri_code': str(col(row, 'Yardi/MRI Code') or '') or None,
                'year_built': int(col(row, 'Year Built')) if col(row, 'Year Built') else None,
                'num_units': num_units,
                'avg_sf': avg_sf,
                'city': str(col(row, 'City') or '') or None,
                'state': str(col(row, 'State') or '') or None,
                'financial_stmt_year': str(col(row, 'Stmt Year') or ''),
                'financial_stmt_type': str(col(row, 'Stmt Type') or ''),
                'metrics': metrics,
                'metrics_per_unit_yr': per_unit_yr,
                'metrics_per_unit_mo': per_unit_mo,
            })
        return results
    except Exception as e:
        logger.error(f"Failed to parse expense comp xlsx: {e}")
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")


@router.post("/my/expense-comps/import", response_model=list[ExpenseCompOut])
async def import_expense_comps(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload an Expense Comp File (.xlsx) to import historical properties."""
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    tenant_id = get_tenant_id(current_user)
    file_data = await file.read()
    rows = _parse_expense_comp_xlsx(file_data)

    created = []
    now = datetime.now(timezone.utc)
    for row in rows:
        comp = ExpenseComp(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            source="import",
            created_at=now,
            uploaded_by=current_user.id,
            **row,
        )
        db.add(comp)
        created.append(comp)

    await db.commit()
    for c in created:
        await db.refresh(c)
    return [ExpenseCompOut.model_validate(c) for c in created]


@router.get("/my/expense-comps", response_model=list[ExpenseCompOut])
async def list_expense_comps(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List historical expense comp properties."""
    tenant_id = get_tenant_id(current_user)
    result = await db.execute(
        select(ExpenseComp)
        .where(ExpenseComp.tenant_id == tenant_id)
        .order_by(ExpenseComp.created_at.desc())
    )
    return [ExpenseCompOut.model_validate(c) for c in result.scalars().all()]


@router.delete("/my/expense-comps/{comp_id}")
async def delete_expense_comp(
    comp_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove an expense comp."""
    tenant_id = get_tenant_id(current_user)
    comp = await db.get(ExpenseComp, comp_id)
    if not comp or comp.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Expense comp not found")
    await db.delete(comp)
    await db.commit()
    return {"ok": True, "deleted_id": str(comp_id)}


@router.get("/deals/{deal_id}/comparison", response_model=ComparisonOut)
async def get_deal_comparison(
    deal_id: uuid.UUID,
    comp_ids: Optional[str] = Query(None, description="Comma-separated expense comp UUIDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return structured comparison data: subject deal metrics vs selected comps."""
    from models.deal import Deal
    from models.classification import ClassificationSession, ClassificationSessionItem

    deal = await db.get(Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # --- Subject: aggregate T12 from the latest applied/approved classification session ---
    session_result = await db.execute(
        select(ClassificationSession)
        .where(
            ClassificationSession.deal_id == deal_id,
            ClassificationSession.status.in_(["applied", "approved"]),
        )
        .order_by(ClassificationSession.created_at.desc())
        .limit(1)
    )
    cls_session = session_result.scalar_one_or_none()

    periods = []
    if cls_session:
        agg = await db.execute(
            select(
                ClassificationSessionItem.final_category,
                func.sum(ClassificationSessionItem.trailing_total).label("total"),
            )
            .where(ClassificationSessionItem.session_id == cls_session.id)
            .group_by(ClassificationSessionItem.final_category)
        )
        metrics = {row.final_category: float(row.total or 0) for row in agg}
        periods.append(ComparisonPeriod(label="T12", stmt_type="Actual", metrics=metrics))

    subject = SubjectComparison(
        name=deal.name,
        num_units=deal.total_units,
        year_built=None,
        avg_sf=None,
        periods=periods,
    )

    # --- Comps: fetch by requested IDs ---
    comps = []
    if comp_ids:
        requested_ids = [uuid.UUID(cid.strip()) for cid in comp_ids.split(",") if cid.strip()]
        for cid in requested_ids:
            comp = await db.get(ExpenseComp, cid)
            if comp:
                comps.append(CompComparison(
                    id=comp.id,
                    name=comp.property_name,
                    num_units=comp.num_units,
                    year_built=comp.year_built,
                    avg_sf=comp.avg_sf,
                    financial_stmt_year=comp.financial_stmt_year,
                    financial_stmt_type=comp.financial_stmt_type,
                    metrics=comp.metrics or {},
                ))

    return ComparisonOut(subject=subject, comps=comps)


@router.get("/deals/{deal_id}/inc-exp-var", response_model=IncExpVarOut)
async def get_inc_exp_var(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get Inc-Exp Var data: subject deal metrics + available comps."""
    tenant_id = get_tenant_id(current_user)

    # Subject: the deal's expense comp (source='deal')
    subject_result = await db.execute(
        select(ExpenseComp)
        .where(ExpenseComp.deal_id == deal_id, ExpenseComp.source == "deal")
        .order_by(ExpenseComp.created_at.desc())
        .limit(1)
    )
    subject = subject_result.scalar_one_or_none()

    # Comps: all imported comps for this tenant
    comps_result = await db.execute(
        select(ExpenseComp)
        .where(ExpenseComp.tenant_id == tenant_id, ExpenseComp.source == "import")
        .order_by(ExpenseComp.created_at.desc())
    )
    comps = comps_result.scalars().all()

    return IncExpVarOut(
        subject=ExpenseCompOut.model_validate(subject) if subject else None,
        comps=[ExpenseCompOut.model_validate(c) for c in comps],
    )
