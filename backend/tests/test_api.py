"""Contract tests for the FastAPI routes.

Each test hits an endpoint via TestClient (bypasses the network but exercises
the full FastAPI request/response stack) and asserts response shape and
basic behavior. The DB sees only what each test seeds — rollback after.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from safetysignal.models import AdverseEvent, Drug, Report


def _seed_minimal(db: Session) -> dict:
    """Insert a small dataset and return the seeded objects by name."""
    drug_a = Drug(name="aspirin", therapeutic_area="nsaid")
    drug_b = Drug(name="ibuprofen", therapeutic_area="nsaid")
    drug_c = Drug(name="lipitor", therapeutic_area="statin")
    ae_headache = AdverseEvent(meddra_pt="Headache")
    ae_nausea = AdverseEvent(meddra_pt="Nausea")
    db.add_all([drug_a, drug_b, drug_c, ae_headache, ae_nausea])
    db.flush()

    # Reports — enough to make signals computable
    reports = []
    for i in range(20):
        reports.append(
            Report(openfda_report_id=f"a_h_{i}", drug_id=drug_a.id, ae_id=ae_headache.id)
        )
    for i in range(5):
        reports.append(
            Report(openfda_report_id=f"a_n_{i}", drug_id=drug_a.id, ae_id=ae_nausea.id)
        )
    for i in range(10):
        reports.append(
            Report(openfda_report_id=f"b_n_{i}", drug_id=drug_b.id, ae_id=ae_nausea.id)
        )
    for i in range(15):
        reports.append(
            Report(openfda_report_id=f"c_h_{i}", drug_id=drug_c.id, ae_id=ae_headache.id)
        )
    db.add_all(reports)
    db.flush()

    return {
        "drug_a": drug_a,
        "drug_b": drug_b,
        "drug_c": drug_c,
        "ae_headache": ae_headache,
        "ae_nausea": ae_nausea,
    }


# ---------- /health ----------

def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------- /drugs ----------

def test_list_drugs_empty_db_returns_empty_list(client: TestClient) -> None:
    response = client.get("/drugs")
    assert response.status_code == 200
    assert response.json() == []


def test_list_drugs_returns_inserted_drugs_with_report_counts(
    client: TestClient, db: Session
) -> None:
    _seed_minimal(db)
    response = client.get("/drugs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    by_name = {d["name"]: d for d in data}
    assert by_name["aspirin"]["report_count"] == 25       # 20 + 5
    assert by_name["ibuprofen"]["report_count"] == 10
    assert by_name["lipitor"]["report_count"] == 15
    assert by_name["aspirin"]["therapeutic_area"] == "nsaid"


def test_list_drugs_filters_by_therapeutic_area(
    client: TestClient, db: Session
) -> None:
    _seed_minimal(db)
    response = client.get("/drugs", params={"therapeutic_area": "nsaid"})
    assert response.status_code == 200
    names = {d["name"] for d in response.json()}
    assert names == {"aspirin", "ibuprofen"}


# ---------- /drugs/{id} ----------

def test_get_drug_returns_detail_with_date_range(
    client: TestClient, db: Session
) -> None:
    seeded = _seed_minimal(db)
    drug_id = seeded["drug_a"].id
    response = client.get(f"/drugs/{drug_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == drug_id
    assert data["name"] == "aspirin"
    assert data["report_count"] == 25
    # first/last_report_date present (null because seed reports have no date)
    assert "first_report_date" in data
    assert "last_report_date" in data


def test_get_drug_returns_404_for_unknown_id(client: TestClient) -> None:
    response = client.get("/drugs/99999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Drug 99999 not found"}


# ---------- /drugs/{id}/signals ----------

def test_get_drug_signals_returns_signals_with_full_shape(
    client: TestClient, db: Session
) -> None:
    seeded = _seed_minimal(db)
    drug_id = seeded["drug_a"].id
    response = client.get(
        f"/drugs/{drug_id}/signals",
        params={"min_prr": 0, "min_count": 1, "limit": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    signal = data[0]
    # Top-level shape
    assert set(signal.keys()) >= {"ae", "report_count", "prr", "contingency"}
    # Nested AE shape
    assert set(signal["ae"].keys()) >= {"meddra_pt", "meddra_soc"}
    # Nested contingency shape — all four cells present
    assert set(signal["contingency"].keys()) == {"a", "b", "c", "d"}


def test_get_drug_signals_returns_404_for_unknown_drug(client: TestClient) -> None:
    response = client.get("/drugs/99999/signals")
    assert response.status_code == 404


def test_get_drug_signals_validates_negative_min_prr(
    client: TestClient, db: Session
) -> None:
    seeded = _seed_minimal(db)
    drug_id = seeded["drug_a"].id
    response = client.get(f"/drugs/{drug_id}/signals", params={"min_prr": -1})
    assert response.status_code == 422  # FastAPI's Query(ge=0.0) enforcement


# ---------- /signals ----------

def test_list_signals_returns_cross_drug_signals_with_drug_field(
    client: TestClient, db: Session
) -> None:
    _seed_minimal(db)
    response = client.get(
        "/signals", params={"min_prr": 0, "min_count": 1, "limit": 50}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        # GlobalSignalOut adds a `drug` field on top of SignalOut's shape.
        assert "drug" in data[0]
        assert set(data[0]["drug"].keys()) >= {"id", "name"}


# ---------- /adverse_events ----------

def test_list_adverse_events_returns_terms_with_counts(
    client: TestClient, db: Session
) -> None:
    _seed_minimal(db)
    response = client.get("/adverse_events", params={"limit": 100})
    assert response.status_code == 200
    data = response.json()
    by_pt = {ae["meddra_pt"]: ae for ae in data}
    assert by_pt["Headache"]["report_count"] == 35   # 20 + 15
    assert by_pt["Nausea"]["report_count"] == 15     # 5 + 10
