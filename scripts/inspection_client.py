"""Submit real evidence from Laptop 2 without exposing credentials in arguments."""

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--product")
    parser.add_argument("--lot")
    parser.add_argument("--resume", type=UUID, metavar="INSPECTION_ID")
    parser.add_argument("--view", choices=("front", "back"), help="Override the next requested view on resume")
    parser.add_argument("--lighting", choices=("manual_diffuse", "manual_left", "manual_right", "manual_top",
                                              "manual_front", "manual_back", "unknown"),
                        default="manual_diffuse")
    parser.add_argument("front", type=Path)
    parser.add_argument("back", type=Path, nargs="?")
    args = parser.parse_args()
    if args.resume and (args.product or args.lot or args.back):
        parser.error("--resume takes one image and uses the existing product and lot")
    if not args.resume and (not args.product or not args.lot or args.view):
        parser.error("A new inspection requires --product and --lot. Use --view with --resume.")
    token = os.getenv("LEO_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(base_url=args.url, timeout=30, headers=headers, trust_env=False) as client:
        metadata = {"product_id": args.product, "lot_id": args.lot, "profile": "leather"}
        endpoint = "/inspect"
        captures = (("front", args.front), ("back", args.back))
        if args.resume:
            base = f"/inspections/{args.resume}"
            result = client.get(base).raise_for_status().json()
            if result["status"] != "awaiting_capture":
                parser.error("This inspection is no longer accepting captures")
            view = args.view or result["actions"][0]["view"]
            captures = ((view, args.front),)
            endpoint = base + "/captures"
            metadata = {}
        for view, path in captures:
            if path is None:
                break
            kinds = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
            media = kinds.get(path.suffix.lower())
            if not media:
                parser.error("Images must have a .jpg, .jpeg or .png extension")
            with path.open("rb") as image:
                response = client.post(endpoint, data={**metadata, "view": view, "lighting": args.lighting,
                                                       "camera_source": "local_file"},
                                       files={"image": (path.name, image, media)})
            response.raise_for_status()
            result = response.json()
            print(json.dumps(result, indent=2))
            if result["status"] != "awaiting_capture":
                break
            if not args.resume and result["actions"][0]["view"] != "back":
                break
            endpoint = f"/inspections/{result['inspection_id']}/captures"
            metadata = {}


if __name__ == "__main__":
    main()
