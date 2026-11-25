# Security notes

- Bootstrap owner password uses Python scrypt (`n=2^14, r=8, p=1`) because Argon2 was unavailable. Use `scripts/start_backend.ps1` first-run secure prompt; no default password is committed.
- Random session tokens expire and only their SHA-256 digest is stored in SQLite. Browser token is held in localStorage. This remains a prototype session design.
- All business routes require authentication. Dispatch authorization additionally checks the owner role. The app currently creates only one owner; inspector/reviewer role management is pending.
- Image input checks file size, MIME, decoded JPEG/PNG format, dimension bounds and generated UUID storage paths. Lab PDF uploads are size-limited, signature-prefixed, stored under generated names and held for human review.
- Queries use SQLite parameter binding. Request schemas validate sizes/ranges. Browser output is escaped before HTML insertion. The app has no external CDN.
- `AI_ENGINE_TOKEN` is read by the backend and sent as a Bearer token; it is not stored by Station Settings. Keep it in a protected process environment.
- Local HTTP is only suitable for a controlled prototype machine/network. Do not expose to the internet. Production needs TLS, network controls, rate limits, reviewed session storage, and complete authorization policies.
- Audit rows and evidence hashes are local records only, not hash-chained or signed. A privileged local operator can edit the database and files.
- Generated PDFs are unsigned reports. There is no official export certificate, QR verification or public passport endpoint.
