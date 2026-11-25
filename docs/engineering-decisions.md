# Engineering decisions

- Use installed Python 3.13 and a workspace virtual environment. The available NVIDIA GPU is unnecessary for the classical baseline; CPU execution minimizes dependency and deployment overhead.
- Start with manual, operator-described diffuse lighting and two leather views. This enables traceable inspection while exact electronics and station geometry are pending.
- Use a transparent local-contrast baseline. Preserve candidate evidence for review and keep confirmed defect claims gated on representative ground truth.
- Use atomic file replacement and a single server process for the prototype. Shared multi-process writes would require stronger coordination.
- Default to localhost. Require a configured bearer token in the supported launcher for LAN binding, with network isolation because HTTP is unencrypted.

## Adaptive evidence and indicator

- Require accepted diffuse front and back views before considering a directional follow-up. Restrict automatic follow-up to a bounded number of contrast candidates so heavily textured samples can go directly to human review.
- Compare candidates only after a surface-feature transform passes geometric checks. Keep both source images and discard no candidate based on absence in a second view.
- Store the analysis mask beside the original bytes. Generate a derived overlay when requested so evidence hashes continue to refer to the original files.
- Keep the optional GPIO23 status indicator on its own serial worker. Versioned acknowledgments establish availability, and the firmware turns the indicator off if the host stops sending valid commands.
- Preserve existing contract 1.0.0 routes and field meanings. Publish additive schema updates and separate capability, finding and surface-artifact routes for Laptop 2.
