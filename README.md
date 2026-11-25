# LEO Shield

**Catch the defect before the buyer does.**

Team LEO, Muthayammal Engineering College · GREENOVATE 2026

Laptop 1 runs LEO-EVE, an offline inspection engine for the Hosur auto-component and Ambur–Vaniyambadi leather and footwear MSME problem statement. The current prototype processes manually captured leather images under controlled lighting and preserves the evidence for a human quality decision.

## Run the manual prototype

Use Windows PowerShell and Python 3.13. On a fresh checkout, run `./scripts/setup.ps1` once to install the pinned packages. Run `./scripts/start_engine.ps1` from the workspace. The engine listens on `127.0.0.1:8001` by default.

Capture JPEG or PNG photos of the front and back of one real leather sample. Use diffuse manual lighting and a matte background that contrasts with the sample. Leave a visible margin around the entire piece. Keep images at least 512 pixels on each side and at most 10 MiB. Capture metadata supplied by the operator is treated as self-reported.

```powershell
.venv/Scripts/python.exe -m scripts.inspection_client --product SAMPLE-1 --lot DEMO-1 front.jpg back.jpg
./scripts/run_tests.ps1 -q
```

Check the returned `actions` after each upload. Supply a fresh image when the engine requests recapture. A HOLD is expected until the mandatory evidence is present. Original image bytes and manifests are stored in `storage/inspections/`.

If LEO-EVE requests right-side evidence, keep the phone and sample fixed and switch off the manually powered white light before moving it. Turn the light on and submit the new photo to the same inspection.

```powershell
.venv/Scripts/python.exe -m scripts.inspection_client --resume <inspection-id> --lighting manual_right right.jpg
.venv/Scripts/python.exe -m scripts.check_station reference.jpg
```

For a station check, use a flat matte reference that contrasts with the background. Center it, keep all edges visible, and photograph it with the phone perpendicular to the work surface. The command reports framing and image quality. After moving or remounting the phone, use `--reference previous-reference.jpg` with the same reference object in the same position to compare framing. A ruler or colour card can be recorded in a separate reference photo. The current station reports uncalibrated and does not return physical dimensions or colour measurements.

- [Laptop 2 integration](docs/api-integration.md)
- [Implementation status](docs/implementation-status.md)
- [Environment audit](docs/setup-report.md)
- [Hardware preparation](docs/hardware.md)
- [LEO-EVE algorithm](docs/leo-eve-algorithm.md)
