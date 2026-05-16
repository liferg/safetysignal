"""Ingest FAERS adverse event reports for the curated drug list.

For each curated drug, paginates openFDA /drug/event.json, walks each
returned report's patient.drug[] array for *suspect* drugs that match
our curated list (whole-word match), and inserts one row per
(report, curated_drug, AE) triple into the `reports` table. The UNIQUE
constraint on (openfda_report_id, drug_id, ae_id) deduplicates silently
via ON CONFLICT DO NOTHING.

Run inside the running backend container:
    docker compose exec backend python -m safetysignal.ingest
"""
import logging
import os
import re
import time
from datetime import date
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from safetysignal.db import SessionLocal
from safetysignal.drugs import CURATED_DRUGS, CuratedDrug
from safetysignal.models import AdverseEvent, Drug, Report

OPENFDA_URL = "https://api.fda.gov/drug/event.json"
API_KEY = os.environ.get("OPENFDA_API_KEY") or None
SLEEP_SECONDS = 0.25
PAGE_SIZE = 1000                      # openFDA's max
MAX_REPORTS_PER_DRUG = 5000           # cap per design doc; keeps total runtime ~30 min
SUSPECT_DRUGCHARACTERIZATION = "1"    # openFDA code for "suspect" (vs concomitant, interacting)
INSERT_CHUNK_SIZE = 5000              # Postgres caps prepared-statement params at 65,535;
                                      # with 7 cols per row, this stays safely under the cap.

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ---------- Parsing helpers ----------

def parse_faers_date(raw: str | None) -> date | None:
    """openFDA dates are 'YYYYMMDD' strings. Return None on missing/malformed."""
    if not raw or len(raw) != 8:
        return None
    try:
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    except ValueError:
        return None


def parse_age(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


SEX_CODE = {"1": "M", "2": "F"}


def build_drug_patterns(curated_names: list[str]) -> dict[str, re.Pattern[str]]:
    """Pre-compile a whole-word regex per curated drug name.

    Whole-word matching avoids false positives like 'citalopram' matching
    'escitalopram' or 'venlafaxine' matching 'desvenlafaxine'.
    """
    return {name: re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE) for name in curated_names}


# ---------- openFDA HTTP ----------

def fetch_openfda_page(drug_name: str, skip: int) -> list[dict[str, Any]]:
    """Fetch one page (up to PAGE_SIZE reports) for a given drug name."""
    params: dict[str, str | int] = {
        "search": f'patient.drug.medicinalproduct:"{drug_name.upper()}"',
        "limit": PAGE_SIZE,
        "skip": skip,
    }
    if API_KEY:
        params["api_key"] = API_KEY

    response = httpx.get(OPENFDA_URL, params=params, timeout=60.0)
    # openFDA returns 404 when the query has zero matches (rather than empty list).
    if response.status_code == 404:
        return []
    response.raise_for_status()
    return response.json().get("results", [])


# ---------- DB upserts ----------

def upsert_curated_drugs(session: Session) -> dict[str, int]:
    """Make sure every curated drug exists in `drugs`. Return {name: id}."""
    for cd in CURATED_DRUGS:
        stmt = (
            insert(Drug)
            .values(name=cd.name, therapeutic_area=cd.therapeutic_area)
            .on_conflict_do_nothing(index_elements=["name"])
        )
        session.execute(stmt)
    session.commit()

    rows = session.execute(select(Drug.id, Drug.name)).all()
    return {name: drug_id for drug_id, name in rows}


def fetch_or_create_ae(session: Session, meddra_pt: str, cache: dict[str, int]) -> int:
    """Return the ae_id for this MedDRA PT, inserting on first sight. Cached in memory."""
    if meddra_pt in cache:
        return cache[meddra_pt]

    stmt = (
        insert(AdverseEvent)
        .values(meddra_pt=meddra_pt)
        .on_conflict_do_nothing(index_elements=["meddra_pt"])
    )
    session.execute(stmt)
    session.commit()

    ae_id = session.execute(
        select(AdverseEvent.id).where(AdverseEvent.meddra_pt == meddra_pt)
    ).scalar_one()
    cache[meddra_pt] = ae_id
    return ae_id


# ---------- Report walking ----------

def extract_curated_suspect_drugs(
    report: dict[str, Any],
    patterns: dict[str, re.Pattern[str]],
) -> set[str]:
    """Return the set of curated drug names that appear as suspect drugs in this report."""
    found: set[str] = set()
    for entry in report.get("patient", {}).get("drug", []):
        if entry.get("drugcharacterization") != SUSPECT_DRUGCHARACTERIZATION:
            continue
        med = entry.get("medicinalproduct") or ""
        for name, pattern in patterns.items():
            if pattern.search(med):
                found.add(name)
    return found


def build_report_rows(
    report: dict[str, Any],
    name_to_id: dict[str, int],
    patterns: dict[str, re.Pattern[str]],
    session: Session,
    ae_cache: dict[str, int],
) -> list[dict[str, Any]]:
    """Cartesian-product (suspect curated drugs) x (reactions) into row dicts."""
    openfda_id = report.get("safetyreportid")
    if not openfda_id:
        return []

    suspect_names = extract_curated_suspect_drugs(report, patterns)
    if not suspect_names:
        return []

    patient = report.get("patient", {})
    age = parse_age(patient.get("patientonsetage"))
    sex = SEX_CODE.get(patient.get("patientsex"))
    report_date = parse_faers_date(report.get("receivedate"))
    serious = report.get("serious") == "1"

    rows: list[dict[str, Any]] = []
    for reaction in patient.get("reaction", []):
        meddra_pt = reaction.get("reactionmeddrapt")
        if not meddra_pt:
            continue
        ae_id = fetch_or_create_ae(session, meddra_pt, ae_cache)
        for name in suspect_names:
            rows.append(
                {
                    "openfda_report_id": openfda_id,
                    "drug_id": name_to_id[name],
                    "ae_id": ae_id,
                    "age": age,
                    "sex": sex,
                    "report_date": report_date,
                    "serious": serious,
                }
            )
    return rows


# ---------- Per-drug ingestion ----------

def ingest_drug(
    session: Session,
    drug: CuratedDrug,
    name_to_id: dict[str, int],
    patterns: dict[str, re.Pattern[str]],
    ae_cache: dict[str, int],
) -> int:
    """Ingest up to MAX_REPORTS_PER_DRUG reports for one drug. Return rows inserted."""
    log.info("[%s] starting", drug.name)
    inserted = 0
    skip = 0

    while skip < MAX_REPORTS_PER_DRUG:
        reports = fetch_openfda_page(drug.name, skip)
        if not reports:
            break

        batch_rows: list[dict[str, Any]] = []
        for report in reports:
            batch_rows.extend(
                build_report_rows(report, name_to_id, patterns, session, ae_cache)
            )

        if batch_rows:
            for i in range(0, len(batch_rows), INSERT_CHUNK_SIZE):
                chunk = batch_rows[i : i + INSERT_CHUNK_SIZE]
                # RETURNING id makes Postgres send back the IDs of rows actually
                # inserted. Rows skipped by ON CONFLICT DO NOTHING are not returned,
                # so len(result.all()) is an accurate inserted-row count.
                # (psycopg3's rowcount is unreliable for ON CONFLICT DO NOTHING.)
                stmt = (
                    insert(Report)
                    .values(chunk)
                    .on_conflict_do_nothing(
                        index_elements=["openfda_report_id", "drug_id", "ae_id"]
                    )
                    .returning(Report.id)
                )
                result = session.execute(stmt)
                inserted += len(result.all())
            session.commit()

        skip += PAGE_SIZE
        if len(reports) < PAGE_SIZE:
            break  # last page

        time.sleep(SLEEP_SECONDS)

    log.info("[%s] done. inserted %d new (report, drug, AE) rows", drug.name, inserted)
    return inserted


# ---------- Entrypoint ----------

def main() -> None:
    log.info("Starting ingestion")
    log.info("openFDA API key: %s", "set" if API_KEY else "not set (anonymous limits)")
    log.info("Cap per drug: %d reports", MAX_REPORTS_PER_DRUG)

    with SessionLocal() as session:
        name_to_id = upsert_curated_drugs(session)
        patterns = build_drug_patterns(list(name_to_id.keys()))
        ae_cache: dict[str, int] = {}

        totals: dict[str, int] = {}
        for drug in CURATED_DRUGS:
            totals[drug.name] = ingest_drug(session, drug, name_to_id, patterns, ae_cache)

    log.info("Ingestion complete.")
    log.info("Per-drug insertion counts:")
    for name, count in totals.items():
        log.info("  %-16s %8d", name, count)


if __name__ == "__main__":
    main()
