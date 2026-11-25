# Laptop 1 implementation status

| Module | Status | Verification and remaining work |
|---|---|---|
| Environment and workspace | SOFTWARE_TESTED | Audit, isolated dependencies, import checks and Git initialization complete |
| API contract and Laptop 2 client | SOFTWARE_TESTED | Contract and upload integration tests run on Laptop 1. Cross-laptop LAN exercise is pending. |
| Manual acquisition and evidence | SOFTWARE_TESTED | JPEG/PNG decoding, EXIF mapping, original bytes, SHA-256 and manifest restart recovery covered by tests |
| Leather quality, segmentation and candidates | SOFTWARE_TESTED | Synthetic normal, marked and low-resolution fixtures exercised. Thresholds and physical accuracy require labeled samples. |
| Coverage and scheduling | SOFTWARE_TESTED | Mandatory front/back under diffuse lighting, retry, HOLD, expiry and bounded attempts exercised |
| ESP32 USB diagnostics | IMPLEMENTED | Portable Arduino CLI verified. Exact board and USB cable require identification. Flashing requires approval. |
| GPIO23 blink sketch | SOFTWARE_TESTED | ESP32 core 3.3.12 installed and compile passed for the original ESP32 target. The chip was previously identified on COM5. COM5 was absent at the final check, and the physical blink test requires reconnection and flash approval. |
| External lighting and smartphone bridge | BLOCKED | Strip and adapter markings, power protection, wiring and phone capture options require verification. No external lighting was energized. |
| Camera/scale/colour calibration and measurements | NOT_STARTED | Requires calibration targets and known geometry |
| Multi-light registration, evidence fusion and selective activation | NOT_STARTED | Requires controlled paired physical captures and validated modules |
| Known-defect training and reference anomalies | BLOCKED | Requires a representative labeled and normal-piece dataset with piece-level splits |
| Footwear and auto components | NOT_STARTED | Explicitly unsupported at runtime pending separate profiles and validation |
| Two-view replay benchmark | SOFTWARE_TESTED | Synthetic replay exercises metric computation and the API excludes synthetic reports. Representative physical measurements remain pending. |
| Physical benchmarks and integrated demonstration | BLOCKED | Requires representative samples, reviewers and Laptop 2 access |

## Completion pass

| Module | Status | Scope |
|---|---|---|
| Manual directional scheduling | SOFTWARE_TESTED | Same-inspection right-light action, view and lighting validation, budget and explicit unresolved review |
| Registration and fusion | SOFTWARE_TESTED | Guarded ORB/RANSAC matching and retained originals. Tests use controlled synthetic transformations. |
| Surface artifacts and findings | SOFTWARE_TESTED | Normalized candidate metadata, binary masks, derived overlays and hash-preserving original retrieval |
| ESP32 GPIO23 status firmware | IMPLEMENTED | Original ESP32 target compiled. Upload and observed LED state patterns require operator approval and verification. |
| Python indicator worker | SOFTWARE_TESTED | Acknowledgment parsing, timeout and disconnect covered by simulated serial tests. Physical firmware handshake pending. |
| Station reference check | IMPLEMENTED | Reports image quality and relative framing for the same reference. Metric and colour calibration remain unimplemented. |
| Live phone capture | SOFTWARE_TESTED | Browser-side simulated capture and guarded preview verified. No connected Android device was detected during the audit. |
| Trained model, physical acceptance and Laptop 2 verification | BLOCKED | No suitable model or labeled station dataset was present. Laptop 2 transfer and human review remain external. |
