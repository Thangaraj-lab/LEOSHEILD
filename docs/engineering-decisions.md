# Engineering decisions

- Use installed Python 3.13 and a workspace virtual environment. The available NVIDIA GPU is unnecessary for the classical baseline; CPU execution minimizes dependency and deployment overhead.
- Start with manual, operator-described diffuse lighting and two leather views. This enables traceable inspection while exact electronics and station geometry are pending.
- Use a transparent local-contrast baseline. Preserve candidate evidence for review and keep confirmed defect claims gated on representative ground truth.
- Use atomic file replacement and a single server process for the prototype. Shared multi-process writes would require stronger coordination.
- Default to localhost. Require a configured bearer token in the supported launcher for LAN binding, with network isolation because HTTP is unencrypted.
