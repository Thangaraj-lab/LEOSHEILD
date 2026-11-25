# Risk register

| Risk | Impact | Next step |
|---|---|---|
| Laptop 1 OpenAPI and multipart fields unconfirmed | Real submission may be rejected or profile/lighting metadata ignored | Exchange OpenAPI; validate request, job lifecycle and response schema on both laptops. |
| Additional image resubmission/file evidence undefined | Operator evidence is only local and cannot complete an awaiting-capture engine job | Agree resubmit endpoint/body and actual evidence download mechanism. |
| No actual Laptop 1/hardware validation | No verified detection, lighting, coverage or hardware-ready capability | Connect laptops on authorized network; test engine and physical sample. |
| Host FastAPI/Starlette mismatch and blocked loopback | Browser/API startup and upload integration were not verified | Install compatible manifest dependencies when package source is reachable; run app and HTTP tests. |
| No React/Vite bundle or frontend browser tests | Visual/function regressions could persist | Restore package-source access, build local frontend toolchain, run browser QA. |
| Single-owner authentication | No inspector/QA role separation | Add user administration and backend role policy before factory deployment. |
| Local DB and audit trail editable by administrator | Hashes do not provide independent tamper resistance | Design protected backup and signing-key trust model; add verification. |
| Buyer rule model is narrow | No complete AQL, measurement tolerances or buyer acceptance plan | Collect actual buyer requirements and implement versioned criteria. |
| PDFs are unsigned, QR/public verification absent | PDF is a local report, not a certified digital passport | Implement signatures and verification only after key custody and URL model are agreed. |
