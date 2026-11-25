# Environment and setup report

Audit date: 2026-11-25 (Asia/Calcutta)

## Machine

- Windows x64; 12 logical CPUs; Python 3.14.6; Node 24.19.0; npm 12.0.2; Git 2.55.0.
- Total RAM reported by Node: 16,127,737,856 bytes; free at audit: 4,292,227,424 bytes.
- C: free disk: 101,283,250,176 bytes.
- CPU model and GPU were not queryable because Windows CIM access was denied.
- `pypi.org` DNS failed. Internet/package availability is blocked or unverified; installing packages was attempted and pip could not resolve its host. npm cache did not contain Vite.
- Workspace was empty before this project; local Git repository initialized, no remote.

## Installed stack and deviations

Present in the system Python: FastAPI 0.115.12, Uvicorn 0.34.2, Pydantic 2.13.4, HTTPX 0.28.1, pytest 9.1.1, python-multipart 0.0.32, Pillow 13.0.0, scrypt in Python standard library. Missing: SQLAlchemy, Alembic, Argon2, QRCode, ReportLab. No React/Vite packages or frontend test harness are installed.

This prototype uses standard-library sqlite3, scrypt, local HTML/CSS/JavaScript and Pillow PDF rendering. A compatible dependency set was installed into `.venv`, but Windows Application Control blocks loading its downloaded `pydantic_core` extension from the workspace, so the launcher uses system Python. System Python pairs FastAPI 0.115.12 with incompatible Starlette 1.8.0. A narrow compatibility shim supplies the missing router callback attributes and `max_body_size`; the launcher initializes the database explicitly because this Starlette build does not run the ASGI lifespan hook. Local `/` and `/health` requests now return HTTP 200. Keep this workaround scoped to this managed machine; a standard isolated environment with supported FastAPI/Starlette versions is preferred for deployment.

The UI uses system fonts and no CDN. Runtime image, database, and report storage is local. `AI_ENGINE_MODE=mock` is rejected because no mock engine implementation exists.

## Start command

From PowerShell at the workspace root:

```powershell
.\scripts\start_backend.ps1
```

The script prompts securely for the first owner password only when the database does not exist. The app is configured for http://127.0.0.1:8000; SQLite defaults to `storage/database/leo_shield.sqlite3`. Configure Laptop 1 with `AI_ENGINE_URL`/`AI_ENGINE_TOKEN` before launch, or save its URL from Station Settings. There is no separate `5173` frontend server in this dependency-constrained UI slice.

## Verification

- `python -m py_compile backend/app/main.py backend/app/integrations/ai_engine_client.py backend/app/reports/pdf_generator.py tests/test_workflow.py`: passed.
- `node --check frontend/app.js`: passed.
- `python -m pytest -q`: 5 passed; 37 deprecation warnings from the preinstalled FastAPI/Starlette combination.
- Tests used isolated temporary SQLite databases, Pillow-created images, a contract fixture for engine responses, and verified generated PDF headers. No live engine/hardware result is included.
- `shared/openapi.json` is generated from the current FastAPI routes.
- Local Uvicorn checks: `/` returned HTTP 200 and `/health` returned `{"status":"ok","database":"sqlite","engine_mode":"real"}`. The image-upload flow and browser interactions still need manual verification.
- User-provided hardware update: Laptop 1 is testing individual ESP32 LEDs; automatic LED-strip lighting is unavailable. Laptop 2 exposes operator-selected lighting metadata and issues no ESP32 commands.
