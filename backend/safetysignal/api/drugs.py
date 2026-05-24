"""Routes for /drugs, /drugs/{id}, and /drugs/{id}/signals."""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from safetysignal import schemas, stats
from safetysignal.deps import DbSession
from safetysignal.models import Drug, Report

router = APIRouter(prefix="/drugs", tags=["drugs"])


@router.get("")
def list_drugs(
    db: DbSession,
    therapeutic_area: str | None = Query(
        None, description="Filter by therapeutic area (e.g. 'ssri_snri', 'statin')."
    ),
) -> list[schemas.DrugOut]:
    """List all curated drugs with their total report counts."""
    stmt = (
        select(
            Drug.id,
            Drug.name,
            Drug.rxnorm_id,
            Drug.atc_class,
            Drug.therapeutic_area,
            func.count(Report.id).label("report_count"),
        )
        .outerjoin(Report, Report.drug_id == Drug.id)
        .group_by(Drug.id)
        .order_by(Drug.name)
    )
    if therapeutic_area:
        stmt = stmt.where(Drug.therapeutic_area == therapeutic_area)

    rows = db.execute(stmt).all()
    return [schemas.DrugOut(**row._mapping) for row in rows]


@router.get(
    "/{drug_id}",
    responses={404: {"model": schemas.ErrorOut, "description": "Drug not found"}},
)
def get_drug(drug_id: int, db: DbSession) -> schemas.DrugDetailOut:
    """Get full detail for one drug, including date range of reports."""
    stmt = (
        select(
            Drug.id,
            Drug.name,
            Drug.rxnorm_id,
            Drug.atc_class,
            Drug.therapeutic_area,
            func.count(Report.id).label("report_count"),
            func.min(Report.report_date).label("first_report_date"),
            func.max(Report.report_date).label("last_report_date"),
        )
        .outerjoin(Report, Report.drug_id == Drug.id)
        .where(Drug.id == drug_id)
        .group_by(Drug.id)
    )
    row = db.execute(stmt).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Drug {drug_id} not found")
    return schemas.DrugDetailOut(**row._mapping)


@router.get(
    "/{drug_id}/signals",
    responses={404: {"model": schemas.ErrorOut, "description": "Drug not found"}},
)
def get_drug_signals(
    drug_id: int,
    db: DbSession,
    min_prr: float = Query(stats.MIN_SIGNAL_PRR, ge=0.0),
    min_count: int = Query(stats.MIN_SIGNAL_COUNT, ge=0),
    limit: int = Query(stats.DEFAULT_LIMIT, ge=1, le=500),
) -> list[schemas.SignalOut]:
    """Return PRR-ranked adverse-event signals for this drug."""
    # Verify the drug exists; otherwise the empty signal list would be ambiguous.
    exists = db.execute(select(Drug.id).where(Drug.id == drug_id)).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail=f"Drug {drug_id} not found")

    raw_signals = stats.compute_signals(
        db,
        drug_id=drug_id,
        min_count=min_count,
        min_prr=min_prr,
        limit=limit,
    )
    return [schemas.SignalOut.from_signal(s) for s in raw_signals]
