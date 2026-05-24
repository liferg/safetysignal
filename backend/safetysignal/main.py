from fastapi import FastAPI

from safetysignal.api import adverse_events, drugs, signals

app = FastAPI(title="SafetySignal", version="0.1.0")

app.include_router(drugs.router)
app.include_router(signals.router)
app.include_router(adverse_events.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
