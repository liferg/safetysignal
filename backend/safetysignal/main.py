from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from safetysignal.api import adverse_events, drugs, signals

app = FastAPI(title="SafetySignal", version="0.1.0")

# CORS: allow the Vite dev server to call the API from the browser.
# Tighten allow_origins (or move to a settings env var) before any prod deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(drugs.router)
app.include_router(signals.router)
app.include_router(adverse_events.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
