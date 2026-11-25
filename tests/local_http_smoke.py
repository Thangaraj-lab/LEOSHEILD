"""Run an offline loopback smoke test with labeled synthetic software fixtures."""

import ipaddress
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from time import monotonic, sleep

import httpx
import uvicorn

from ai_engine.api.app import create_app
from scripts.inspection_client import main as inspection_client
from tests.conftest import synthetic_image


def restrict_network(event, args):
    if event == "socket.connect":
        address = args[1]
        if not isinstance(address, tuple) or not ipaddress.ip_address(address[0]).is_loopback:
            raise PermissionError("Smoke test permits only loopback connections")
    if event in {"socket.gethostbyname", "socket.gethostbyname_ex", "socket.getaddrinfo"}:
        host = args[0]
        if host not in (None, "127.0.0.1", "::1"):
            raise PermissionError("Smoke test permits only numeric loopback addresses")


def serve(storage):
    sys.addaudithook(restrict_network)
    uvicorn.run(create_app(Path(storage)), host="127.0.0.1", port=8001, access_log=False)


def verify_client_resume(storage, image):
    front = Path(storage) / "front.png"
    back = Path(storage) / "back.png"
    retake = Path(storage) / "retake.png"
    front.write_bytes(image(size=300))
    back.write_bytes(image(mark=True))
    retake.write_bytes(image())
    command = [sys.executable, "-m", "tests.local_http_smoke", "--client"]
    environment = {**os.environ, "LEO_API_TOKEN": ""}

    def run(*arguments):
        output = subprocess.check_output([*command, *map(str, arguments)], text=True, env=environment)
        return json.loads(output)

    initial = run("--product", "retake-fixture", "--lot", "smoke-test", front, back)
    assert len(initial["evidence"]) == 1 and initial["actions"][0]["view"] == "front"
    corrected = run("--resume", initial["inspection_id"], retake)
    assert corrected["coverage"]["inspected_regions"] == 1 and corrected["actions"][0]["view"] == "back"
    result = run("--resume", initial["inspection_id"], back)
    assert result["coverage"]["complete"] and result["recommendation"] == "hold"
    assert result["actions"][0]["lighting"] == "manual_right"


def main():
    sys.addaudithook(restrict_network)
    with tempfile.TemporaryDirectory(dir=".venv", prefix="offline-smoke-") as storage:
        with subprocess.Popen([sys.executable, "-m", "tests.local_http_smoke", storage],
                              env={**os.environ, "LEO_API_TOKEN": ""}) as server:
            try:
                with httpx.Client(base_url="http://127.0.0.1:8001", trust_env=False, timeout=5) as client:
                    deadline = monotonic() + 15
                    while monotonic() < deadline and server.poll() is None:
                        try:
                            client.get("/health").raise_for_status()
                            break
                        except httpx.ConnectError:
                            sleep(0.2)
                    else:
                        raise RuntimeError("Loopback server could not start")
                    image = synthetic_image.__wrapped__()
                    start = monotonic()
                    front = client.post("/inspect", files={"image": ("front.png", image(), "image/png")},
                                        data={"profile": "leather", "product_id": "synthetic",
                                              "lot_id": "smoke-test", "view": "front", "lighting": "manual_diffuse"})
                    front.raise_for_status()
                    initial = front.json()
                    assert initial["status"] == "awaiting_capture" and initial["recommendation"] == "hold"
                    base = f"/inspections/{initial['inspection_id']}"
                    back = client.post(base + "/captures",
                                       files={"image": ("back.png", image(mark=True), "image/png")},
                                       data={"view": "back", "lighting": "manual_diffuse"})
                    back.raise_for_status()
                    result = client.get(base).raise_for_status().json()
                    assert result["status"] == "awaiting_capture" and result["coverage"]["complete"]
                    assert result["actions"][0]["lighting"] == "manual_right"
                    result = client.post(base + "/finish").raise_for_status().json()
                    assert result["recommendation"] == "review" and result["human_approval_required"]
                    original = client.get(result["evidence"][1]["image_url"]).raise_for_status()
                    assert original.content == image(mark=True)
                    print(json.dumps({"data": "synthetic_software_fixture", "http_port": 8001,
                                      "outbound_network": "loopback_only", "coverage": [0.5, 1.0],
                                      "recommendations": ["hold", "review"],
                                      "decode_and_analysis_ms": result["processing_time_ms"],
                                      "http_sequence_ms": round((monotonic() - start) * 1000, 3)}, indent=2))
                    verify_client_resume(storage, image)
                    print("Manual upload and requested retakes verified over HTTP.")
            finally:
                server.terminate()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--client":
        sys.addaudithook(restrict_network)
        del sys.argv[1]
        inspection_client()
    elif len(sys.argv) == 2:
        serve(sys.argv[1])
    else:
        main()
