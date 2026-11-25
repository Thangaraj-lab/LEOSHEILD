# Engineering decisions

## 2026-11-25: small dependency-free first slice

The workspace was empty and DNS resolution blocked package installation. To make a reviewable offline workflow now, use installed FastAPI/Uvicorn and Python stdlib SQLite/scrypt plus locally served HTML/CSS/JS. This is a temporary deviation from the preferred React/Vite, SQLAlchemy/Alembic and Argon2 stack. No npm dependencies or external runtime assets are required. Revisit when package sources are available.

## Provisional Laptop 1 client

Only the user-pasted structural contract is available. The initial synchronous multipart client is explicitly provisional and its assumptions are documented. Real-mode failures remain failures; no silent mock fallback.
