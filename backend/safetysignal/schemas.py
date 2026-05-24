"""Pydantic response schemas for the SafetySignal API.

Each `*Out` class is the shape returned by a specific endpoint.
Lightweight `*Summary` classes are used to embed related objects inside
those responses (e.g. the AE info inside a signal).

The classmethods on signal schemas convert from the `stats.Signal`
dataclass (data layer) into the API response shape (presentation layer),
keeping the mapping in one place.
"""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from safetysignal import stats


# ---------- Error response ----------

class ErrorOut(BaseModel):
    """Shape of error responses (404, etc.). Matches what FastAPI's HTTPException emits."""

    detail: str


# ---------- Drug schemas ----------

class DrugSummary(BaseModel):
    """A drug, minimal form. Embedded in cross-drug signal responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class DrugOut(BaseModel):
    """One row in the GET /drugs list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    rxnorm_id: str | None = None
    atc_class: str | None = None
    therapeutic_area: str
    report_count: int = Field(
        ..., description="Total reports mentioning this drug as a suspect drug"
    )


class DrugDetailOut(DrugOut):
    """GET /drugs/{id} response. Adds date-range metadata."""

    first_report_date: date | None = None
    last_report_date: date | None = None


# ---------- Adverse event schemas ----------

class AdverseEventSummary(BaseModel):
    """An AE, minimal form. Embedded in signal responses."""

    model_config = ConfigDict(from_attributes=True)

    meddra_pt: str
    meddra_soc: str | None = None


class AdverseEventOut(BaseModel):
    """One row in the GET /adverse_events list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    meddra_pt: str
    meddra_soc: str | None = None
    report_count: int


# ---------- Signal schemas ----------

class ContingencyOut(BaseModel):
    """2x2 contingency table cells for one (drug, AE) pair.

        a = this drug AND this AE
        b = this drug AND other AEs
        c = other drugs AND this AE
        d = other drugs AND other AEs
    """

    a: int
    b: int
    c: int
    d: int


class SignalOut(BaseModel):
    """One signal for a known drug. Used by GET /drugs/{id}/signals.

    The drug is implicit from the URL, so it's not repeated in the body.
    """

    ae: AdverseEventSummary
    report_count: int = Field(
        ...,
        description="Number of reports linking this drug to this AE (= contingency.a)",
    )
    prr: float
    contingency: ContingencyOut

    @classmethod
    def from_signal(cls, s: stats.Signal) -> "SignalOut":
        return cls(
            ae=AdverseEventSummary(meddra_pt=s.meddra_pt, meddra_soc=s.meddra_soc),
            report_count=s.reports_drug_ae,
            prr=s.prr,
            contingency=ContingencyOut(
                a=s.reports_drug_ae,
                b=s.reports_drug_other_ae,
                c=s.reports_other_drug_ae,
                d=s.reports_other_drug_other_ae,
            ),
        )


class GlobalSignalOut(SignalOut):
    """A signal across all drugs. Used by GET /signals — includes the drug."""

    drug: DrugSummary

    @classmethod
    def from_signal(cls, s: stats.Signal) -> "GlobalSignalOut":
        return cls(
            ae=AdverseEventSummary(meddra_pt=s.meddra_pt, meddra_soc=s.meddra_soc),
            report_count=s.reports_drug_ae,
            prr=s.prr,
            contingency=ContingencyOut(
                a=s.reports_drug_ae,
                b=s.reports_drug_other_ae,
                c=s.reports_other_drug_ae,
                d=s.reports_other_drug_other_ae,
            ),
            drug=DrugSummary(id=s.drug_id, name=s.drug_name),
        )
