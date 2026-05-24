"""Route for /adverse_events — list of MedDRA Preferred Terms with frequencies."""
from fastapi import APIRouter, Query
from sqlalchemy import func, select

from safetysignal import schemas
from safetysignal.deps import DbSession
from safetysignal.models import AdverseEvent, Report

router = APIRouter(prefix="/adverse_events", tags=["adverse_events"])


@router.get("")
def list_adverse_events(
    db: DbSession,
    soc: str | None = Query(
        None, description="Filter by MedDRA System Organ Class (currently always null)."
    ),
    limit: int = Query(100, ge=1, le=1000),
) -> list[schemas.AdverseEventOut]:
    """List adverse-event terms, ordered by total report count descending."""
    stmt = (
        select(
            AdverseEvent.id,
            AdverseEvent.meddra_pt,
            AdverseEvent.meddra_soc,
            func.count(Report.id).label("report_count"),
        )
        .outerjoin(Report, Report.ae_id == AdverseEvent.id)
        .group_by(AdverseEvent.id)
        .order_by(func.count(Report.id).desc())
        .limit(limit)
    )
    if soc:
        stmt = stmt.where(AdverseEvent.meddra_soc == soc)

    rows = db.execute(stmt).all()
    return [schemas.AdverseEventOut(**row._mapping) for row in rows]
