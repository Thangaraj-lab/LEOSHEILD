import json

from ai_engine import ROOT
from ai_engine.api.app import create_app
from ai_engine.api.schemas import InspectionResult


def main():
    spec = create_app().openapi()
    shared = ROOT / "shared"
    contract = {
        "version": spec["info"]["version"],
        "engine_port": 8001,
        "business_backend_port": 8000,
        "transport": "local HTTP",
        "image_media_types": ["image/jpeg", "image/png"],
        "coordinates": "normalized original encoded pixel grid; origin at upper left",
        "endpoints": {path: sorted(method.upper() for method in methods) for path, methods in spec["paths"].items()},
        "openapi": "openapi.json",
        "inspection_schema": "inspection-schema.json",
    }
    for name, payload in {"openapi": spec, "inspection-schema": InspectionResult.model_json_schema(),
                          "api-contract": contract}.items():
        (shared / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
