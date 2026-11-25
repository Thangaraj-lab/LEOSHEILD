"""Laptop 1 client. Endpoints match the supplied contract; request bodies remain provisional."""
from __future__ import annotations

from typing import Any

import httpx


class AIEngineClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def get_json(self, path: str) -> Any:
        response = httpx.get(f"{self.base_url}{path}", headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def evidence_metadata(self, inspection_id: str) -> Any:
        return self.get_json(f"/inspections/{inspection_id}/evidence")

    def inspect_image(self, image: bytes, filename: str, content_type: str, product_id: str, lot_id: str, profile: str, lighting: str) -> Any:
        # Provisional multipart fields until Laptop 1 publishes its authoritative OpenAPI.
        response = httpx.post(
            f"{self.base_url}/inspect",
            headers=self.headers,
            files={"image": (filename, image, content_type)},
            data={"product_id": product_id, "lot_id": lot_id, "profile": profile, "lighting_mode": lighting},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
