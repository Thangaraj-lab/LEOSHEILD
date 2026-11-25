# LEO Shield engineering instructions

LEO Shield supports evidence-driven industrial quality inspection for leather, footwear and auto-component MSMEs. Laptop 2 owns the business application; Laptop 1 owns the AI engine, camera, ESP32 and LEO-EVE algorithm.

## Product rules
- Never treat an AI recommendation as human approval. Persist AI output separately from human decisions.
- Use the Laptop 1 API only through the backend. Real mode must fail clearly when unavailable; mock fixtures must be explicit and ineligible for dispatch.
- Do not invent detections, measurements, coverage, benchmark results or factory analytics. Label development data.
- Preserve original images and AI results. Store local evidence with SHA-256 hashes.
- Block dispatch on unresolved inspections, mock records, missing approval, quantity mismatch or incomplete requirements.
- No cloud dependency for essential local operation. No external publication or source upload without authorization.
- Do not claim QR passports are official certificates or hashes alone are tamper-proof.

## Ownership and workflow
- Laptop 2: frontend, business API, local persistence, authentication, workflow, analytics, reporting and integration.
- Laptop 1: firmware, hardware, image capture, AI/LEO-EVE, model and AI API.
- The agreed Laptop 1 OpenAPI/schema takes precedence. Mark provisional assumptions in docs.
- Make small, functional changes; document actual capabilities and blockers. Keep secrets, databases, images, venvs and node_modules out of Git.

## Current development boundary
Build the local proof-of-concept workflow first: local login, lot/product records, evidence upload, engine boundary, human decisions and dispatch gate. Do not represent unavailable AI or hardware as working.
