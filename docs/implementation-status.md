# Implementation status

As of 2026-11-25. Status is based on implemented and locally tested behavior; it does not imply factory validation.

| Capability | Status | Notes |
|---|---|---|
| Environment audit and project instructions | IMPLEMENTED | Windows x64; 12 logical CPUs; about 16 GB RAM. CIM blocked CPU/GPU model queries. No remote Git configured. |
| Local SQLite persistence | SOFTWARE_TESTED | Startup creates tables and applies additive column migrations; interruption of a submission is recovered as failed on restart. SQLAlchemy/Alembic unavailable. |
| Owner authentication | SOFTWARE_TESTED | Bootstrap owner, scrypt password hash, random expiring bearer tokens stored by digest. No user administration or multi-role workflow. |
| Lot and product management | SOFTWARE_TESTED | Unique lot/product IDs, expected quantity, supplier/machine fields, distinct physical-product statistics and inspection history. |
| Capture and image validation | SOFTWARE_TESTED | Pillow decodes actual JPEG/PNG, size/dimension checks, safe generated names and SHA-256. Lighting label and resolution recorded for each capture. |
| Manual evidence capture | SOFTWARE_TESTED | Additional images persist with lighting/hash; they are explicitly not represented as submitted to Laptop 1. |
| Defect evidence and corrections | SOFTWARE_TESTED | Actual engine defects imported, normalized bounding boxes rendered, numbered markers, correction/false-positive/manual records; raw AI JSON remains unchanged. Unsupported geometry is listed without a fabricated overlay. |
| Laptop 1 client | IN_PROGRESS | Configurable URL/token, health/hardware/capabilities calls, provisional multipart inspect request, bounded UUID job polling, event history and evidence-metadata lookup. No live Laptop 1 was reachable. |
| LEO-EVE activity | IN_PROGRESS | Displays actual `actions` returned by the engine. No activity events are generated locally. |
| Human verification | SOFTWARE_TESTED | Required reason; PASS/GRADE require completed job, complete coverage and acceptable image quality. HOLD/REJECT remain available. |
| Buyer quality rules and lab evidence | SOFTWARE_TESTED | Buyer profile, required measurements, PDF lab uploads, review status and measurement records feed the gate. This is not a full buyer/AQL rules engine. |
| Export Ready Gate and dispatch | SOFTWARE_TESTED | Checks quantity, latest inspection and decision, coverage, quality, buyer rule, required measurements/labs, accepted units and mock status. Owner dispatch must equal accepted quantity; one authorization per lot. |
| Manufacturing insights | SOFTWARE_TESTED | Database-derived defect rates by lot/supplier/machine, grades, repeated labels, durations and decision divergence. Association is not root-cause or accuracy. |
| PDF quality reports | SOFTWARE_TESTED | Pillow renders local inspection/lot evidence with images, hashes, decisions, model/algorithm fields and gate state. These are not signed passports. |
| Responsive local UI | IMPLEMENTED | Overview, inspection, lots, gate, insights and station settings. JavaScript syntax passes; a Vite bundle/frontend test harness is not available. |
| QR passport, signature and public verification | NOT_STARTED | No QR or official/export certificate claim. |
| Hardware lighting control | NOT_STARTED | Laptop 1 is testing individual ESP32 LEDs; this app issues no lighting commands. Manual lighting labels are supported. |
| Automated tests | SOFTWARE_TESTED | `python -m pytest -q`: 5 passed. Tests exercise image workflows, polling, persistence and temporary SQLite. Local `/` and `/health` HTTP checks pass; image upload and browser interaction still need manual verification. |
| Integrated demonstration | BLOCKED | Requires the agreed Laptop 1 request/evidence contract and a reachable engine/hardware. |

Commercial production readiness is not claimed. Remaining work includes real cross-laptop validation, RBAC, TLS/deployment review, independent passport signatures/verification, backup/restore drills, broader buyer rules and frontend browser QA.
