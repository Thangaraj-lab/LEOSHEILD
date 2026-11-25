# Architecture

The local browser app is served by FastAPI at port 8000. Authenticated `/api/v1` routes enforce input and workflow rules. SQLite holds business state; original and supplemental images, lab-report PDFs and generated reports remain in local storage. Only the backend calls Laptop 1's configured API on port 8001.

```text
Browser (local assets) -> Laptop 2 FastAPI -> SQLite + local files
                                      \----> Laptop 1 AI API
```

The frontend is dependency-free HTML/CSS/JavaScript in this environment. It has no Vite server or production bundle. `backend/app/integrations/ai_engine_client.py` isolates calls to Laptop 1. Its multipart inspection fields remain provisional; GET health/capabilities/status and job/evidence-metadata paths come from the requested contract. Evidence metadata is not treated as an image download.

Run on loopback for local use. No route controls ESP32 LEDs. The manually selected lighting label is attached to each local capture. Supplemental operator images are stored as evidence but are not resubmitted upstream until Laptop 1 defines the accepted mechanism.

The app does not currently provide TLS, multi-role administration, a digitally signed passport, public verification or cloud sync. The database and audit trail are editable by a privileged local user; SHA-256 evidence hashes do not independently prevent tampering.
