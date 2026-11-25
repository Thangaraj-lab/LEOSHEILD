"""Submit real evidence from Laptop 2 without exposing credentials in arguments."""

import argparse
import json
import os
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--product", required=True)
    parser.add_argument("--lot", required=True)
    parser.add_argument("front", type=Path)
    parser.add_argument("back", type=Path, nargs="?")
    args = parser.parse_args()
    token = os.getenv("LEO_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(base_url=args.url, timeout=30, headers=headers, trust_env=False) as client:
        metadata = {"product_id": args.product, "lot_id": args.lot, "profile": "leather"}
        endpoint = "/inspect"
        for view, path in (("front", args.front), ("back", args.back)):
            if path is None:
                break
            kinds = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
            media = kinds.get(path.suffix.lower())
            if not media:
                parser.error("Images must have a .jpg, .jpeg or .png extension")
            with path.open("rb") as image:
                response = client.post(endpoint, data={**metadata, "view": view, "lighting": "manual_diffuse"},
                                       files={"image": (path.name, image, media)})
            response.raise_for_status()
            result = response.json()
            print(json.dumps(result, indent=2))
            if result["status"] != "awaiting_capture":
                break
            endpoint = f"/inspections/{result['inspection_id']}/captures"
            metadata = {}


if __name__ == "__main__":
    main()
