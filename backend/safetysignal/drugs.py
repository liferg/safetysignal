"""The curated list of drugs we ingest from openFDA.

Single source of truth used by both preflight (to verify report counts
before committing to the list) and ingest (to drive the actual data load).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CuratedDrug:
    name: str
    therapeutic_area: str


CURATED_DRUGS: list[CuratedDrug] = [
    # SSRIs / SNRIs
    CuratedDrug("fluoxetine", "ssri_snri"),
    CuratedDrug("sertraline", "ssri_snri"),
    CuratedDrug("paroxetine", "ssri_snri"),
    CuratedDrug("citalopram", "ssri_snri"),
    CuratedDrug("escitalopram", "ssri_snri"),
    CuratedDrug("fluvoxamine", "ssri_snri"),
    CuratedDrug("venlafaxine", "ssri_snri"),
    CuratedDrug("duloxetine", "ssri_snri"),
    CuratedDrug("vortioxetine", "ssri_snri"),
    CuratedDrug("vilazodone", "ssri_snri"),
    # Statins
    CuratedDrug("atorvastatin", "statin"),
    CuratedDrug("rosuvastatin", "statin"),
    CuratedDrug("simvastatin", "statin"),
    CuratedDrug("pravastatin", "statin"),
    CuratedDrug("lovastatin", "statin"),
    CuratedDrug("fluvastatin", "statin"),
    CuratedDrug("pitavastatin", "statin"),
]
