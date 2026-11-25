# Laptop 1 architecture

The API validates uploads and delegates processing to LEO-EVE. The acquisition layer decodes JPEG and PNG and applies EXIF orientation. Preprocessing estimates the visible surface and checks image quality. The detector estimates local contrast using only pixels inside the segmented surface. LEO-EVE updates per-view coverage, schedules one next operator action, and derives a recommendation. The artifact store writes the original file before atomically publishing its manifest.

A single Uvicorn process and an engine lock serialize writes. Polling reads under the same lock so expiry and capture updates stay consistent. UUID paths isolate jobs and captures. A crash before manifest replacement can leave an unreferenced file. Recovery uses the prior readable manifest and exposes only files listed in it. The runtime performs all processing locally and uses CPU inference.

Laptop 2 consumes the API, handles operator prompts and owns the final decision and signed business record.
