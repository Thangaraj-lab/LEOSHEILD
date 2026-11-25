"""Report the tested Python environment without collecting serial identifiers."""

import json
import os
import platform
import shutil
import sys
from importlib.metadata import version
from pathlib import Path

from serial.tools import list_ports


if __name__ == "__main__":
    print(json.dumps({
        "os": platform.platform(),
        "architecture": platform.machine(),
        "logical_processors": os.cpu_count(),
        "workspace_free_bytes": shutil.disk_usage(".").free,
        "python": platform.python_version(),
        "virtual_environment": sys.prefix != sys.base_prefix,
        "git": shutil.which("git") is not None,
        "arduino_cli": shutil.which("arduino-cli") is not None or Path(".tools/arduino/arduino-cli.exe").is_file(),
        "serial_ports_detected": len(list_ports.comports()),
        "packages": {name: version(name) for name in (
            "fastapi", "opencv-python-headless", "numpy", "pillow", "pyserial", "uvicorn", "pytest",
        )},
    }, indent=2))
