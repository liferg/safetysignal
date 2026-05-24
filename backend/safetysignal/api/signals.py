"""Route for /signals — top PRR signals across all drugs."""
from fastapi import APIRouter, Query

from safetysignal import schemas, stats
from safetysignal.deps import DbSession

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("")
def list_signals(
    db: DbSession,
    min_prr: float = Query(stats.MIN_SIGNAL_PRR, ge=0.0),
    min_count: int = Query(stats.MIN_SIGNAL_COUNT, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[schemas.GlobalSignalOut]:
    """Return top PRR-ranked safety signals across all drugs in the database."""
    raw_signals = stats.compute_signals(
        db,
        min_count=min_count,
        min_prr=min_prr,
        limit=limit,
    )
    return [schemas.GlobalSignalOut.from_signal(s) for s in raw_signals]
