# Database design

SQLite is initialized and additively upgraded at startup using stdlib `sqlite3` (not Alembic yet). Relationships are enforced with foreign keys.

- `users` and expiring `sessions` store owner identity and session digests.
- `lots` contain multiple `products`; a product has multiple `inspections`.
- Each inspection retains its original AI JSON, recommendation, state, request idempotency key, execution mode and evidence metadata. `captures` preserve one or more source images, sequence, actual operator lighting label, source, dimensions and SHA-256.
- `defects` stores imported AI annotations plus corrected, false-positive and manual records. `original_label` remains unchanged after human corrections.
- `decisions` retain each human outcome/reason. Gate and lot counts use the latest inspection and latest decision for each product.
- `buyer_requirements`, `measurements`, `lab_reports`, `dispatches` and `station_settings` support the current buyer checks and dispatch workflow.
- `audit` records significant actions, but is not hash chained or signed.

Image bytes are kept under local `storage/images` or `storage/evidence`; PDF lab attachments and generated reports are stored separately. Startup recovers a record left in the local `submitting` state as failed, never completed. No cloud synchronization or cascade delete is exposed.
