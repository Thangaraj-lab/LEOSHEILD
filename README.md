# LEO Shield

Local-first quality inspection and export assurance for leather, footwear and auto-component MSMEs. AI output remains separate from human decisions.

## Current implementation

This workspace now has a functional local proof-of-concept workflow: owner login, lot/product registration, verified image upload, manual lighting metadata, provisional Laptop 1 submission and job polling, image evidence hashes, defect annotations, human decisions, buyer rules, measurement and lab-report review, an Export Ready Gate, owner dispatch authorization, database-driven summaries and local PDF quality reports.

The Laptop 1 OpenAPI file and additional-image resubmission mechanism have not been agreed. Real engine integration is therefore provisional. Additional operator photos are stored locally and clearly marked as **not submitted to the engine**. No mock result mode, hardware command, QR passport, digital signature or public verification is claimed.

## Startup

Run PowerShell from the workspace root:

```powershell
.\scripts\start_backend.ps1
```

On first run, the script prompts for a local owner password if the database does not exist. To configure Laptop 1, set `AI_ENGINE_URL` (for example `http://192.168.1.20:8001`) and, if required, `AI_ENGINE_TOKEN` in the process environment before starting; the Station Settings page can save the engine URL and station name. The token remains environment-only. Current UI is served by FastAPI at `http://127.0.0.1:8000`; there is no separate Vite server or frontend build yet.

SQLite is stored at `storage/database/leo_shield.sqlite3`; images and reports remain under `storage/`. Core application assets and report generation are local. Do not expose this HTTP prototype to the internet or an untrusted network. The managed environment denied loopback socket access, so end-to-end HTTP launch could not be verified here.

## Development checks

```powershell
python -m pytest -q
node --check frontend/app.js
python -m py_compile backend/app/main.py backend/app/integrations/ai_engine_client.py backend/app/reports/pdf_generator.py
```

See [implementation status](docs/implementation-status.md), [setup report](docs/setup-report.md), [API integration notes](docs/api-integration.md), and [user guide](docs/user-guide.md). Commercial readiness is not claimed.
