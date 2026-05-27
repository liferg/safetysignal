"""Tests for the PRR computation.

The critical test of the project.
If this passes, every signal the API serves is mathematicallysound. If it ever fails, every signal is suspect.
"""
import pytest
from sqlalchemy.orm import Session

from safetysignal import stats
from safetysignal.models import AdverseEvent, Drug, Report


def _make_reports(
    drug_id: int, ae_id: int, count: int, id_prefix: str
) -> list[Report]:
    """Build `count` Report rows for a (drug, AE) pair with unique IDs."""
    return [
        Report(
            openfda_report_id=f"{id_prefix}_{i}",
            drug_id=drug_id,
            ae_id=ae_id,
        )
        for i in range(count)
    ]


def test_prr_against_hand_worked_2x2(db: Session) -> None:
    """Appendix A's worked example.

    Setup:
        drug X has 1000 reports, 50 of which mention AE "Headache"
        other drugs together have 9000 reports, 100 of which mention "Headache"

    Contingency cells:
                       | Headache | Other AEs
        drug X         |    50    |    950
        other drugs    |   100    |   8900

    Expected PRR = (50 / 1000) / (100 / 9000)
                 = 0.05 / 0.0111...
                 = 4.5
    """
    # Two drugs (target X, plus a stand-in for "other drugs"),
    # two AEs (Headache, plus a stand-in for "other AEs").
    drug_x = Drug(name="drug_x", therapeutic_area="test")
    drug_other = Drug(name="drug_other", therapeutic_area="test")
    ae_headache = AdverseEvent(meddra_pt="Headache")
    ae_other = AdverseEvent(meddra_pt="OtherAE")
    db.add_all([drug_x, drug_other, ae_headache, ae_other])
    db.flush()

    db.add_all(_make_reports(drug_x.id, ae_headache.id, 50, "x_h"))
    db.add_all(_make_reports(drug_x.id, ae_other.id, 950, "x_o"))
    db.add_all(_make_reports(drug_other.id, ae_headache.id, 100, "o_h"))
    db.add_all(_make_reports(drug_other.id, ae_other.id, 8900, "o_o"))
    db.flush()

    signals = stats.compute_signals(
        db,
        drug_id=drug_x.id,
        min_count=1,
        min_prr=0.0,
        limit=100,
    )

    headache = next(s for s in signals if s.meddra_pt == "Headache")

    # Contingency cells must match the hand-worked table exactly.
    assert headache.reports_drug_ae == 50           # a
    assert headache.reports_drug_other_ae == 950    # b
    assert headache.reports_other_drug_ae == 100    # c
    assert headache.reports_other_drug_other_ae == 8900  # d

    # PRR must equal 4.5 within floating-point tolerance.
    assert headache.prr == pytest.approx(4.5, abs=1e-9)


def test_min_count_filter_excludes_sparse_pairs(db: Session) -> None:
    """min_count should drop any (drug, AE) pair with fewer than N reports.

    Note: PRR requires a non-trivial background — we need at least one other
    drug in the database, otherwise every PRR computes to NULL (division by
    zero on the 'other drugs' side) and the SQL filters them out.
    """
    drug = Drug(name="drug", therapeutic_area="test")
    other = Drug(name="other", therapeutic_area="test")
    ae_rare = AdverseEvent(meddra_pt="Rare")
    ae_common = AdverseEvent(meddra_pt="Common")
    db.add_all([drug, other, ae_rare, ae_common])
    db.flush()

    db.add_all(_make_reports(drug.id, ae_rare.id, 2, "rare"))
    db.add_all(_make_reports(drug.id, ae_common.id, 10, "common"))
    # Background reports so PRR has a non-zero denominator on the "other" side.
    db.add_all(_make_reports(other.id, ae_rare.id, 50, "other_rare"))
    db.add_all(_make_reports(other.id, ae_common.id, 50, "other_common"))
    db.flush()

    signals = stats.compute_signals(db, drug_id=drug.id, min_count=3, min_prr=0.0)
    terms = {s.meddra_pt for s in signals}

    assert "Common" in terms     # 10 reports >= min_count=3
    assert "Rare" not in terms   # 2 reports < min_count=3


def test_min_prr_filter_excludes_below_threshold(db: Session) -> None:
    """min_prr should drop signals below the threshold."""
    drug_x = Drug(name="drug_x", therapeutic_area="test")
    drug_y = Drug(name="drug_y", therapeutic_area="test")
    ae_flat = AdverseEvent(meddra_pt="Flat")  # equally common in both -> PRR ~ 1
    db.add_all([drug_x, drug_y, ae_flat])
    db.flush()

    db.add_all(_make_reports(drug_x.id, ae_flat.id, 50, "x"))
    db.add_all(_make_reports(drug_y.id, ae_flat.id, 50, "y"))
    db.flush()

    signals = stats.compute_signals(db, drug_id=drug_x.id, min_count=1, min_prr=2.0)
    assert signals == []  # PRR ~ 1.0 doesn't clear the 2.0 threshold
