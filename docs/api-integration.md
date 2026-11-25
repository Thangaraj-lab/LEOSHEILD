# Laptop 1 integration

Laptop 1 owns the AI engine and hardware on port 8001. Laptop 2's business API is configured for port 8000. `AI_ENGINE_URL` defaults to `http://127.0.0.1:8001`; during cross-laptop integration set it to Laptop 1's local IP. `AI_ENGINE_TOKEN` is consumed as a Bearer token when present. Station Settings can store the station name and engine URL; credentials remain in the backend process environment.

## Implemented calls

- `GET /health`, `GET /hardware/status`, and `GET /engine/capabilities` power the actual connection panel. Unknown payloads remain Unknown; no capability is assumed active.
- `POST /inspect` submits a multipart image with provisional fields `image`, `product_id`, `lot_id`, `profile` and `lighting_mode`. Only image/product/lot had been documented in the earlier Laptop 2 provisional contract; profile and lighting fields still need Laptop 1 agreement.
- A valid pending job is polled with `GET /inspections/{id}` only when Laptop 1 returns its UUID. Browser polls the Laptop 2 refresh route every two seconds for up to two minutes and stops at a terminal state.
- A completed job may query `GET /inspections/{id}/evidence`; returned metadata is stored separately. The app does not assume metadata provides downloadable image bytes.

Request timeout/errors persist a failed record and original photograph. POST is not automatically retried because upstream idempotency is unconfirmed. The business API accepts an `Idempotency-Key` for duplicate browser submission protection; it is not forwarded as an upstream guarantee. Invalid result state, recommendation, UUID or contract version fails closed.

## Still needed from Laptop 1

Please exchange the authoritative OpenAPI and agree on request field names and semantics, profile/lighting support, defect geometry, optional response fields, error bodies, authentication, job lifecycle, idempotency, evidence file transfer/download, and additional-image resubmission. The app stores operator supplemental photos locally and reports `submitted_to_engine=false` until that mechanism is agreed. It does not issue `POST /lighting/set` or `POST /capture`; individual ESP32 LEDs remain under Laptop 1 testing and automatic lighting is not active here.

The current Laptop 1 integration fixture is only a provisional schema contract in `shared/api-contract.json`, not a production result. No fake engine health, defect, coverage, or hardware state is enabled.
