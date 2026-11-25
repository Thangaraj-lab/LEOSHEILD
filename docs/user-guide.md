# User guide

## Start and sign in

From the workspace root run `scripts/start_backend.ps1`. On first launch it prompts securely for a local owner password and creates SQLite at `storage/database/leo_shield.sqlite3`. Open `http://127.0.0.1:8000` on the same machine. Do not expose this local HTTP prototype to untrusted networks.

## Inspection

1. Create a lot and select its industry profile, expected quantity, buyer, supplier and machine/drum if known.
2. Register each physical product.
3. Open Inspection Workspace and select a product. Profile defaults from the lot; the API rejects mismatched profiles.
4. Choose the lighting condition actually used: Normal, Top, Left, Right, Front, Back or Unknown.
5. Select **Open local camera**, allow access in your browser, frame the product and select **Capture photo**. You can also choose a JPEG/PNG file. Review the still image, then select **Start inspection** to save it and submit it to Laptop 1. Camera access requires localhost or HTTPS.
6. The captured product appears in **Product evidence** on the left of the review screen. The engine recommendation, recorded defects and human decision are on the right on wider screens. Numbered boxes appear on the original image when the engine returns supported coordinates. To revisit the latest inspection, select **View evidence** from the product's lot.
7. Review the original image and every capture. Add or correct defect annotations; false positives remain in the record while the raw AI response remains unchanged.
8. Record Pass, Grade, Reject or Hold with a reason. Pass/Grade remain blocked unless coverage is complete and capture quality is acceptable.

When Laptop 1 requests more evidence, follow the action text returned by the engine. A supplemental image may be stored with its operator-selected lighting label, but the current shared contract has no additional-image resubmission mechanism; it will not change the engine result or inspection state.

## Export readiness

Configure a buyer rule under Station Settings, including the profile and named measurements/lab types. Record measurements, upload actual PDF lab reports and mark them accepted/rejected after review. The gate lists exact blockers. An owner can authorize one dispatch only when all checks pass and its quantity exactly matches human-accepted units. Rejected units are excluded.

## Reports and settings

Download inspection and lot quality reports as local PDFs from their pages. Reports contain actual database records and images; they are not signed passports, public QR verifications or government export certificates. Station Settings configures the station name and Laptop 1 URL; keep any token in `AI_ENGINE_TOKEN` in the backend process environment.
