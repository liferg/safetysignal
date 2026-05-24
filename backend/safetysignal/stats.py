"""PRR (Proportional Reporting Ratio) computation for drug-AE signals.

For each (drug, AE) pair, builds a 2x2 contingency table from the
`reports` table and computes:

    PRR = (a / (a + b)) / (c / (c + d))

A "signal" is flagged when PRR >= MIN_SIGNAL_PRR with at least
MIN_SIGNAL_COUNT supporting reports — the conventional thresholds per
WHO-UMC signal-detection guidance.

This is the same disproportionality method regulators (EMA, FDA, WHO-UMC)
use to scan post-market safety data. NOT a clinical-grade implementation;
for portfolio/demo purposes only.

Quick smoke test:
    docker compose exec backend python -m safetysignal.stats
"""
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from safetysignal.db import SessionLocal

# WHO-UMC conventional signal thresholds.
MIN_SIGNAL_COUNT = 3
MIN_SIGNAL_PRR = 2.0
DEFAULT_LIMIT = 50


@dataclass(frozen=True)
class Signal:
    """One row of the signals query: a (drug, AE) pair plus PRR + contingency cells."""

    drug_id: int
    drug_name: str
    ae_id: int
    meddra_pt: str
    meddra_soc: str | None
    reports_drug_ae: int                # contingency cell a
    reports_drug_other_ae: int          # contingency cell b
    reports_other_drug_ae: int          # contingency cell c
    reports_other_drug_other_ae: int    # contingency cell d
    prr: float


_PRR_SQL = text("""
    WITH drug_totals AS (
        SELECT drug_id, COUNT(*) AS total
        FROM reports
        GROUP BY drug_id
    ),
    ae_totals AS (
        SELECT ae_id, COUNT(*) AS total
        FROM reports
        GROUP BY ae_id
    ),
    all_reports AS (
        SELECT COUNT(*)::float AS total FROM reports
    ),
    combos AS (
        SELECT drug_id, ae_id, COUNT(*) AS a
        FROM reports
        GROUP BY drug_id, ae_id
    ),
    signals_unfiltered AS (
        SELECT
            combos.drug_id,
            combos.ae_id,
            combos.a,
            drug_totals.total - combos.a AS b,
            ae_totals.total   - combos.a AS c,
            all_reports.total - drug_totals.total - ae_totals.total + combos.a AS d,
            (combos.a::float / drug_totals.total) /
                (NULLIF(ae_totals.total - combos.a, 0)::float /
                 NULLIF(all_reports.total - drug_totals.total, 0)) AS prr
        FROM combos
        JOIN drug_totals ON drug_totals.drug_id = combos.drug_id
        JOIN ae_totals   ON ae_totals.ae_id     = combos.ae_id
        CROSS JOIN all_reports
    )
    SELECT
        s.drug_id,
        d.name        AS drug_name,
        s.ae_id,
        ae.meddra_pt,
        ae.meddra_soc,
        s.a,
        s.b,
        s.c,
        s.d,
        s.prr
    FROM signals_unfiltered s
    JOIN drugs           d  ON d.id  = s.drug_id
    JOIN adverse_events  ae ON ae.id = s.ae_id
    WHERE s.a >= :min_count
      AND s.prr IS NOT NULL
      AND s.prr >= :min_prr
      AND (CAST(:drug_id AS INTEGER) IS NULL OR s.drug_id = :drug_id)
    ORDER BY s.prr DESC
    LIMIT :limit
""")


def compute_signals(
    session: Session,
    *,
    drug_id: int | None = None,
    min_count: int = MIN_SIGNAL_COUNT,
    min_prr: float = MIN_SIGNAL_PRR,
    limit: int = DEFAULT_LIMIT,
) -> list[Signal]:
    """Compute disproportionality signals from the reports table.

    Parameters
    ----------
    session : an active SQLAlchemy session.
    drug_id : optional. If set, restrict to signals for this drug; if None,
              returns top signals across all drugs.
    min_count : minimum (drug, AE) report count to consider (default 3).
    min_prr : minimum PRR to flag as a signal (default 2.0).
    limit : maximum signals to return, sorted by PRR descending.

    Returns
    -------
    A list of Signal objects, ordered by PRR descending.
    """
    rows = session.execute(
        _PRR_SQL,
        {
            "drug_id": drug_id,
            "min_count": min_count,
            "min_prr": min_prr,
            "limit": limit,
        },
    ).all()

    return [
        Signal(
            drug_id=row.drug_id,
            drug_name=row.drug_name,
            ae_id=row.ae_id,
            meddra_pt=row.meddra_pt,
            meddra_soc=row.meddra_soc,
            reports_drug_ae=row.a,
            reports_drug_other_ae=row.b,
            reports_other_drug_ae=row.c,
            reports_other_drug_other_ae=row.d,
            prr=row.prr,
        )
        for row in rows
    ]


def _demo() -> None:
    """Smoke test: print top-15 paroxetine signals."""
    from sqlalchemy import select

    from safetysignal.models import Drug

    with SessionLocal() as session:
        paroxetine_id = session.execute(
            select(Drug.id).where(Drug.name == "paroxetine")
        ).scalar_one()

        signals = compute_signals(session, drug_id=paroxetine_id, limit=15)

        print(
            f"Top {len(signals)} signals for paroxetine "
            f"(PRR >= {MIN_SIGNAL_PRR}, count >= {MIN_SIGNAL_COUNT}):\n"
        )
        print(f"{'PRR':>7}  {'Count':>6}  {'AE Term':<40}  SOC")
        print("-" * 100)
        for s in signals:
            soc = s.meddra_soc or "(unknown)"
            print(f"{s.prr:>7.2f}  {s.reports_drug_ae:>6}  {s.meddra_pt[:40]:<40}  {soc}")


if __name__ == "__main__":
    _demo()
