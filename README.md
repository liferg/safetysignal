# SafetySignal

A pharmacovigilance signal explorer that ingests FDA adverse event reports and computes Proportional Reporting Ratio (PRR) statistics to surface drug-symptom safety signals.

> **Demo / portfolio project. Not for clinical use.**

## Run locally

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
docker compose up --build
```

When you see `Application startup complete`, open:

- http://localhost:8000/health — should return `{"status":"ok"}`
- http://localhost:8000/docs — auto-generated API docs

## Status

Phase 1 (backbone) — in progress.
