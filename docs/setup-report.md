# Laptop 1 environment audit

Audit date 25 November 2026. The selected workspace was empty and a local Git repository was initialized there. There is no configured remote.

| Item | Observed |
|---|---|
| Operating system | Windows 11 build 26200, x64 |
| CPU | AMD Ryzen 7 7445HS, 6 physical cores and 12 logical processors |
| Memory | 16,357,158,912 bytes visible to the OS, about 15.2 GiB |
| Storage | About 353.6 GB free on C: after dependency installation |
| GPUs | AMD Radeon 740M and NVIDIA GeForce RTX 3050 Laptop GPU with 6 GiB |
| GPU acceleration | NVIDIA driver 591.80 advertises CUDA 13.1 compatibility. CUDA runtime and inference were not exercised. |
| Python | Direct installation Python 3.13.12 AMD64. The `py` launcher returned no registered installations in the sandbox. |
| Git and Node | Git 2.54.0.windows.1, Node 24.14.1 |
| Arduino CLI | Version 1.5.1 verified from workspace-local `.tools/arduino/arduino-cli.exe`. The CLI was absent from PATH during the initial audit. |
| USB serial | Zero enumerated ports |
| Network | PyPI DNS failed inside the sandbox. Download succeeded with approved access. |

Installed into `.venv` from PyPI using the base interpreter's pip. The default `ensurepip` attempt could not write to sandbox temporary storage. The setup script uses a workspace temporary directory and pip's `--python` option. Dependency checks found no broken requirements.

Verified using `scripts/verify_environment.py`, `python -m pip --python .venv check`, `nvidia-smi`, and local API tests. Pinned dependencies are recorded in the requirements files. No system-wide dependencies or GPU packages were installed.

The portable CLI archive was downloaded from Arduino and checked against the release SHA-256 digest before extraction. [Arduino CLI v1.5.1 release](https://github.com/arduino/arduino-cli/releases/tag/v1.5.1)
