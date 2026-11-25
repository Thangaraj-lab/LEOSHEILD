# Laptop 2 integration

Contract 1.0.0 runs on port 8001. Laptop 2 uses port 8000 for its own backend. The machine-readable contract is in [shared](../shared/api-contract.json) and includes [OpenAPI](../shared/openapi.json) and the [inspection schema](../shared/inspection-schema.json).

For same-laptop checks, run `./scripts/start_engine.ps1`. For LAN testing, run `Get-NetIPAddress -AddressFamily IPv4` and select the inspection LAN address. Provision a shared token through the environment on both machines, then start with `./scripts/start_engine.ps1 --host <inspection-LAN-IPv4>`. All documented business endpoints require `Authorization: Bearer <token>` when configured. Limit any approved firewall rule to the inspection network and intended peer. Local HTTP carries the token and files without transport encryption. Use an isolated trusted network for the prototype.

| Request | Result |
|---|---|
| `GET /health` | Status and contract version |
| `GET /hardware/status` | Verification flags and observed USB serial port count |
| `GET /engine/capabilities` | Experimental leather, manual upload and classical candidates |
| `POST /inspect` with multipart | Accepts first capture and returns 202 with UUID and the current state |
| `GET /inspections/{inspection_id}` | Read progress, coverage, candidate boxes and recommendation |
| `POST /inspections/{inspection_id}/captures` with multipart | Append another capture, returns 202 |
| `POST /inspections/{inspection_id}/finish` | End an incomplete inspection with terminal HOLD |
| `GET /inspections/{inspection_id}/evidence` | Evidence metadata including original-image links |
| `GET /inspections/{inspection_id}/evidence/{capture_id}/image` | Original bytes with JPEG or PNG content type |
| `POST /lighting/set`, `POST /capture` | 503 for valid commands while station hardware is unavailable |
| `GET /benchmarks/latest` | Returns the latest published physical replay report, or 404 |

For the first multipart request, send `product_id`, `lot_id`, `profile=leather`, `view=front` or `view=back`, `lighting=manual_diffuse`, and `image` with the matching media type. Send only `view`, `lighting`, and `image` for subsequent captures. Both accept optional `captured_at` as an ISO 8601 timestamp with offset. When absent, the evidence retains the separate server receipt time. Upload up to 10 MiB per image and 24 megapixels. JSON station input is `{"source":"station","product_id":"P1","lot_id":"L1","profile":"leather"}`. It receives 503 in manual mode.

The live manual workflow returns `awaiting_capture` or `completed`. Render the next view, lighting and reason from `actions`. Manual foreground contrast candidates appear in `uncertain_regions`. Each candidate has a capture ID, region ID and normalized coordinates relative to the original encoded image, with origin at the upper left. A terminal `completed` job can still recommend HOLD. All results require human approval. Preserve the recommendation separately from the final decision.

Handle 400 for malformed multipart requests, 401 for missing or invalid credentials, 404 for unavailable records, 408 for slow uploads, 409 for closed jobs or duplicate uploads, 413 for size limits, 415 for unsupported media, 422 for invalid fields or malformed image data, and 503 for unavailable station functions or server capacity. Configure a client timeout of at least 30 seconds for demonstration uploads. The sample client is [scripts/inspection_client.py](../scripts/inspection_client.py).
