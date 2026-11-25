# LEO Shield Laptop 1 completion report

25 November 2026 · API contract **1.0.0** · LEO-EVE **0.2.0**

## Delivery status

Laptop 1 can ingest original JPEG and PNG photos, assess image quality, extract the visible surface, flag contrast candidates, and request further evidence while retaining traceable originals. The local API and manual adaptive flow have been software-tested. The station has yet to pass the full physical acceptance test or exchange an inspection with Laptop 2.

## Environment and connected hardware

| Check | Observed result |
|---|---|
| Operating system | Windows 11 build 26200, x64 |
| CPU and memory | AMD Ryzen 7 7445HS, 6 physical cores and 12 logical processors, 16.36 GB visible RAM |
| GPU | NVIDIA RTX 3050 Laptop GPU with 6,144 MiB dedicated memory. This pipeline uses CPU OpenCV. |
| Runtime | Python 3.13.12 in `.venv`, Git 2.54.0, Arduino CLI 1.5.1, Arduino ESP32 core 3.3.12 |
| Packages | OpenCV Headless 5.1.0.95, NumPy 2.5.5, Pillow 13.0.0, PySerial 3.5, FastAPI 0.165.0, Uvicorn 0.54.0 and pytest 9.2.0. `python -m pip --python .venv check` found no broken requirements. |
| Laptop 1 IPv4 | Wi‑Fi `10.192.151.43`, Windows profile Public |
| USB serial | Silicon Labs CP210x bridge, VID:PID 10C4:EA60, **COM5** |
| ESP32 chip | Prior read-only bootloader probe verified ESP32-D0WD-V3 revision 3.1 and 4 MB SPI flash. Exact PCB vendor variant remains unidentified. |
| Indicator wiring | Operator close-up showed P23 and adjacent ground. Operator reports P23 → 1 kΩ resistor → small LED anode, with cathode to ground. |
| White illumination | Operator reports that the separately powered white strip works. No firmware control of the strip is available. |
| Status firmware | Original ESP32 build passed. The sketch uses 273,100 bytes of program storage and 22,212 bytes of global RAM. |
| Flash and physical indicator | No firmware uploaded during this pass. A read-only GET_STATUS on COM5 timed out. Status pattern and disconnect behavior on real hardware remain unverified. |
| Phone | File upload is usable with existing smartphone photos. ADB detected no connected Android device during the audit. Live capture remains unverified on a physical phone. |

The firmware implements six non-blocking GPIO23 patterns and an idle-off timeout after five seconds without valid communication. The optional Python worker matches command IDs, retries connection, publishes lifecycle state and leaves image processing independent of serial availability. The status LED does not switch the white strip.

## Inspection and artifacts

- **Acquisition** supports JPEG and PNG originals, source metadata and timestamps where supplied, front and back and same-inspection follow-ups. Lighting is operator-supplied.
- **Quality and station check** use resolution, background consistency, foreground size and framing, Laplacian sharpness, dark-pixel fraction and probable glare. The reference tool can compare normalized framing against an earlier photo. The station remains uncalibrated for dimensions and colour.
- **Surface coverage** reports the required and accepted views, quality and normalized geometry. New captures can retain a binary analysis mask and generate an overlay. Coverage concerns visible, required views only.
- **Candidate detection** uses masked Lab local contrast, morphological closing and connected components. Findings include identifiers, original-image coordinates, supporting captures, explanation and unverified uncertainty. Natural grain, decoration and shadow can trigger findings. No trained model or labeled station dataset was found. The detector boundary can support a validated replacement.
- **Adaptive policy** requests a replacement photo when mandatory quality or lighting is insufficient. A limited number of baseline candidates can trigger a manually lit right-side follow-up for the same view and inspection ID. Poor or unregistered directional evidence is retried within budget. Missing mandatory coverage finishes with HOLD. Unresolved optional evidence leaves the findings for human REVIEW.
- **Evidence fusion** compares spatial overlap only after surface-feature ORB alignment passes RANSAC checks. Both results remain available for human review. Actual controlled cross-light performance has yet to be evaluated.
- **Evidence and security** use original-byte SHA-256, UUID paths, atomic writes, bounded uploads, environment-based bearer authentication and no automatic publication. Hashes support local integrity checks and provide no independent attestation.

## Verification

`python -m scripts.export_contract`, the 21-test suite, the offline loopback smoke test, the local station reference check, and the firmware compile succeeded. Pytest emitted one Starlette test adapter deprecation warning. Coverage included invalid images and authentication, segmentation, overlays, hash and original retrieval, HOLD, retakes, direction validation, registration, synthetic cross-light persistence, and simulated serial timeout and disconnect. The loopback run on port 8001 measured 179 ms for image processing and 353 ms for the scripted HTTP sequence. Fixture timings exclude physical acquisition, repositioning and human decision time.

Three pairs were replayed through the running local API. For each capture, retrieved bytes and SHA-256 matched the uploaded file.

| Input | Accepted required views | Result | Decode and processing | Local HTTP sequence |
|---|---:|---|---:|---:|
| Original operator purse photographs | 0/2 | HOLD. Front failed framing. Back passed image quality but lighting was unknown. It reached the 40-candidate limit. | 438 ms | 603 ms |
| Original publicly sourced museum wallet views | 0/2 | HOLD. Both frames failed the background check. | 284 ms | 461 ms |
| Same museum photographs with a prepared uniform background | 2/2 | REVIEW. Both views reached the 40-candidate limit. | 601 ms | 735 ms |

The station-reference check on the full operator view measured 899 × 1599 pixels, Laplacian variance 273.316, dark fraction 0.0657 and glare fraction 0.0 under the current thresholds. The raw replay files and private capture IDs are in `storage/final-validation/photo-replay.json`. The museum background was replaced for software replay. These runs provide no labeled accuracy result for good leather, scratches, cuts, holes or directional cross-light captures. The two-view replay benchmark runner is available. Fixed versus adaptive comparison, physical capture savings, precision, recall, false-positive rate and assisted-human performance remain unmeasured.

## Startup and handoff

The verified Laptop 1 server is bound to **http://127.0.0.1:8001**. From the project folder, run:

```powershell
.\scripts\start_engine.ps1 --host 127.0.0.1 --port 8001
```

Transfer `shared/api-contract.json`, `shared/inspection-schema.json`, `shared/openapi.json` and `shared/contract-version.txt` together. The original contract 1.0.0 routes remain and the current snapshot adds station modes, findings and evidence artifacts plus optional metadata. Laptop 2 should accept the new manual-light values and algorithm version 0.2.0. Laptop 1's current remote endpoint would be `https://10.192.151.43:8001` with trusted certificate, token and approved network access configured. No public-interface binding or firewall change was made. The actual remote import URL and human-review exchange remain pending.

## Completion methodology and remaining gates

The following 14 equally weighted gates count an implementation separately from its required verification. The unit is an acceptance gate.

| Gate | Code or workflow | Verification |
|---|---|---|
| 1. Environment and startup | Complete locally | Verified |
| 2. Original image intake and metadata | Implemented | Verified locally with originals |
| 3. Image quality and surface extraction | Implemented | Verified locally with real images and fixtures |
| 4. Classical candidate screening | Implemented | Verified for image-dependent behavior |
| 5. Mandatory coverage and adaptive action selection | Implemented | Verified in software |
| 6. Evidence, masks, overlays and retrieval | Implemented | Verified locally |
| 7. Guarded cross-light registration and fusion | Implemented | Verified with synthetic transformations |
| 8. Local API and contract snapshot | Implemented | Verified on port 8001 |
| 9. ESP32 status firmware build | Implemented | Verified by compile |
| 10. Physical status indicator | Implemented | Pending flash approval and physical observation |
| 11. Physical Android live capture | Implemented | Pending device connection and browser permission |
| 12. Physical adaptive station sequence | Implemented | Pending same-piece accepted views and controlled directional capture |
| 13. Laptop 2 transfer and human verification | Laptop 1 handoff ready | Pending second laptop exchange |
| 14. Ground-truth strategy and accuracy benchmarks | Baseline runner available | Pending labeled station set and comparison runs |

**Implemented at Laptop 1 for the stated gate: 12/14 (85.7%). Verified at the stated gate: 9/14 (64.3%).** These are completion counts and carry no product accuracy or certification claim.

The local demonstration can show original photo ingestion, rejection of incomplete evidence, candidate review and traceable retrieval today. Physical acceptance requires the full controlled sample set, an approved upload and observed status patterns for the optional indicator, and actual Laptop 2 transfer followed by a human decision.
