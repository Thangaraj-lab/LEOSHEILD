# Laptop 2 integration

Contract 1.0.0 runs on port 8001. Laptop 2 uses port 8000 for its own backend. The machine-readable contract is in [shared](../shared/api-contract.json) and includes [OpenAPI](../shared/openapi.json) and the [inspection schema](../shared/inspection-schema.json).

For same-laptop checks, run `./scripts/start_engine.ps1`. For LAN testing, run `Get-NetIPAddress -AddressFamily IPv4` and select the inspection LAN address. Provision a shared token through the environment on both machines, then start with `./scripts/start_engine.ps1 --host <inspection-LAN-IPv4>`. All documented business endpoints require `Authorization: Bearer <token>` when configured. Limit any approved firewall rule to the inspection network and intended peer. Local HTTP carries the token and files without transport encryption. Use an isolated trusted network for the prototype.

| Request | Result |
|---|---|
| `GET /health` | Status and contract version |
| `GET /hardware/status` | Verification flags and observed USB serial port count |
| `GET /engine/capabilities` | Experimental leather, manual upload and classical candidates |
| `GET /engine/station-modes` | Separate indicator handshake, manual lighting, automatic lighting and phone-verification flags |
| `POST /inspect` with multipart | Accepts first capture and returns 202 with UUID and the current state |
| `GET /inspections/{inspection_id}` | Read progress, coverage, candidate boxes and recommendation |
| `POST /inspections/{inspection_id}/captures` with multipart | Append another capture, returns 202 |
| `POST /inspections/{inspection_id}/finish` | End an incomplete inspection with terminal HOLD |
| `GET /inspections/{inspection_id}/evidence` | Evidence metadata including original-image links |
| `GET /inspections/{inspection_id}/evidence/{capture_id}/image` | Original bytes with JPEG or PNG content type |
| `GET /inspections/{inspection_id}/evidence/{capture_id}/mask` | Downsampled binary analysis mask in the original image orientation |
| `GET /inspections/{inspection_id}/evidence/{capture_id}/overlay` | Image with the analyzed footprint and candidate boxes |
| `GET /inspections/{inspection_id}/findings` | Candidate IDs, geometry, supporting capture and method |
| `POST /lighting/set`, `POST /capture` | 503 for valid commands while station hardware is unavailable |
| `GET /benchmarks/latest` | Returns the latest published physical replay report, or 404 |

For the first multipart request, send `product_id`, `lot_id`, `profile=leather`, `view=front` or `view=back`, `lighting=manual_diffuse`, and `image` with the matching media type. Send only `view`, `lighting`, and `image` for subsequent captures. Both accept optional `captured_at` as an ISO 8601 timestamp with offset. When absent, the evidence retains the separate server receipt time. Upload up to 10 MiB per image and 24 megapixels. JSON station input is `{"source":"station","product_id":"P1","lot_id":"L1","profile":"leather"}`. It receives 503 in manual mode.

The live manual workflow returns `awaiting_capture` or `completed`. Render the next view, lighting and reason from `actions`. Manual foreground contrast candidates appear in `uncertain_regions`. Each candidate has a capture ID, region ID and normalized coordinates relative to the original encoded image, with origin at the upper left. A terminal `completed` job can still recommend HOLD. All results require human approval. Preserve the recommendation separately from the final decision.

The manual client follows the requested view. If it stops for a retake, use `.venv/Scripts/python.exe -m scripts.inspection_client --resume <inspection_id> retake.jpg`. The client reads the pending action and submits the image against that view. Use `--lighting unknown` when the capture mode is unknown. Use `coverage.regions` for each view's surface box, quality and completed lighting. The box encloses the analyzed surface, and the job-level coverage counts accepted views.

For `directional_evidence_requested`, display the returned `view`, `lighting`, `instruction` and optional normalized `target_box`. Submit the follow-up to the existing inspection ID with `--lighting manual_right` after actually moving the manually powered light. A job may have complete baseline coverage while it awaits optional directional evidence. For older records, the new mask and overlay routes may return 404. Source metadata is optional and self-reported. Supported lighting values include `manual_diffuse`, `manual_top`, `manual_left`, `manual_right`, `manual_front`, `manual_back` and `unknown`. The server also accepts `NORMAL`, `TOP`, `LEFT`, `RIGHT`, `FRONT`, `BACK` and `UNKNOWN` as input aliases.

Transfer all four files in `shared/` to Laptop 2 together. Contract 1.0.0 retains the original endpoints and fields and adds fields, lighting values and optional routes. Update response enum handling for algorithm 0.2.0 and the extra manual lighting values. The local network address observed on Laptop 1 was `10.192.151.43`, so its proposed remote URL is `https://10.192.151.43:8001` when a matching trusted certificate and approved network setup are present. The active smoke test is bound to Laptop 1 loopback. Remote reachability and Laptop 2 import remain unverified.

### Phone capture

Open `http://<Laptop-1-IP>:8001/mobile/` on the same trusted local network. Start Laptop 1 with `LEO_API_TOKEN` configured and `.venv/Scripts/python.exe -m ai_engine.main --host <Laptop-1-IP>`. Enter the same token on the phone and supply the product, lot and lighting. Tap **Open phone camera** and accept the photo in the phone's camera app. The page uploads it immediately and displays the next required side or retake. **Choose a JPEG or PNG** works as a fallback. The prototype LAN HTTP mode requires a trusted network because photos and the token travel without TLS.

For automatic capture on the phone, serve HTTPS with a certificate the phone trusts and which matches the address you open. Pass `--tls-cert <certificate> --tls-key <private-key>` to the same launcher. Tap **Start automatic camera** and allow access. The page shows **Place object** when it cannot find a foreground surface against the inspection background. It prompts for framing or lighting adjustments when the view is unsuitable. Once two acceptable frames have a steady surface outline, it uploads the second frame and closes the camera. Preview checks use a token-protected endpoint and do not save images or create inspections. Move the item as instructed before restarting the camera for the next view. The phone page and preview endpoint are excluded from the Laptop 2 contract.

Handle 400 for malformed multipart requests, 401 for missing or invalid credentials, 404 for unavailable records, 408 for slow uploads, 409 for closed jobs or duplicate uploads, 413 for size limits, 415 for unsupported media, 422 for invalid fields or malformed image data, and 503 for unavailable station functions or server capacity. Configure a client timeout of at least 30 seconds for demonstration uploads. The sample client is [scripts/inspection_client.py](../scripts/inspection_client.py).
