"""Pre-flight check: count openFDA reports for each curated drug.

Run inside the running backend container:
    docker compose exec backend python -m safetysignal.preflight

Prints a table of drug -> total reports. Flags any drug below
MIN_REPORTS_THRESHOLD so it can be swapped before the full ingest.

Note: this counts ALL reports mentioning the drug (any role). The full
ingest will further restrict to reports where the drug is listed as
'suspect' (drugcharacterization == "1"), so actual ingested counts will
be lower than the numbers shown here.
"""
import os
import time

import httpx

from safetysignal.drugs import CURATED_DRUGS

OPENFDA_URL = "https://api.fda.gov/drug/event.json"
API_KEY = os.environ.get("OPENFDA_API_KEY") or None
SLEEP_SECONDS = 0.25
MIN_REPORTS_THRESHOLD = 500


def count_reports(drug_name: str) -> int:
    """Return total openFDA report count for a given drug name."""
    params: dict[str, str | int] = {
        "search": f'patient.drug.medicinalproduct:"{drug_name.upper()}"',
        "limit": 1,
    }
    if API_KEY:
        params["api_key"] = API_KEY

    response = httpx.get(OPENFDA_URL, params=params, timeout=30.0)

    # openFDA returns 404 when zero results match (rather than an empty list).
    if response.status_code == 404:
        return 0
    response.raise_for_status()
    return response.json()["meta"]["results"]["total"]


def main() -> None:
    print(f"openFDA API key: {'set' if API_KEY else 'not set (using anonymous limits)'}")
    print()
    print(f"{'Drug':<16} {'Class':<12} {'Reports':>10}  Status")
    print("-" * 52)

    flagged: list[str] = []

    for drug in CURATED_DRUGS:
        try:
            count = count_reports(drug.name)
            if count >= MIN_REPORTS_THRESHOLD:
                status = "OK"
            else:
                status = "TOO FEW"
                flagged.append(drug.name)
            print(f"{drug.name:<16} {drug.therapeutic_area:<12} {count:>10,}  {status}")
        except Exception as e:  # noqa: BLE001 -- want to keep going on any failure
            print(f"{drug.name:<16} {drug.therapeutic_area:<12} {'ERROR':>10}  {e}")
            flagged.append(drug.name)
        time.sleep(SLEEP_SECONDS)

    print()
    print(f"Threshold: >= {MIN_REPORTS_THRESHOLD} reports per drug.")
    if flagged:
        print(f"\nFlagged for review: {', '.join(flagged)}")
    else:
        print("\nAll drugs meet the threshold.")


if __name__ == "__main__":
    main()
