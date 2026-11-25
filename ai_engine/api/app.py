import asyncio
import os
from hmac import compare_digest
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from serial.tools import list_ports
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import ClientDisconnect

from ai_engine import ROOT
from ai_engine.acquisition.image_loader import MAX_IMAGE_BYTES
from ai_engine.api.schemas import (
    BenchmarkResult, Capabilities, CaptureInput, Evidence, HardwareStatus, Health, InspectionInput, InspectionResult,
    LightingInput, StationInput,
)
from ai_engine.evidence.artifact_store import ArtifactStore
from ai_engine.leo_eve.engine import ClosedInspection, Engine
from ai_engine.preprocessing.vision import load_leather_rules

MAX_REQUEST_BYTES = MAX_IMAGE_BYTES + 64 * 1024
AUTH = HTTPBearer(auto_error=False)


class BoundedMultipartParser(MultiPartParser):
    spool_max_size = MAX_REQUEST_BYTES


def multipart_schema(*, initial):
    properties = {
        "image": {"type": "string", "format": "binary"},
        "view": {"type": "string", "enum": ["front", "back"]},
        "lighting": {"type": "string", "enum": ["manual_diffuse", "manual_left", "manual_right", "unknown"]},
        "captured_at": {"type": "string", "format": "date-time"},
    }
    required = ["image", "view", "lighting"]
    if initial:
        properties.update(InspectionInput.model_json_schema()["properties"])
        required.extend(["product_id", "lot_id", "profile"])
    content = {"multipart/form-data": {"schema": {
        "type": "object", "properties": properties, "required": required, "additionalProperties": False,
    }}}
    if initial:
        content["application/json"] = {"schema": StationInput.model_json_schema()}
    return {"requestBody": {"required": True, "content": content}}


def json_schema(model):
    return {"requestBody": {"required": True, "content": {
        "application/json": {"schema": model.model_json_schema()},
    }}}


def validate(model, values):
    try:
        return model.model_validate(values)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors(include_context=False, include_input=False)) from exc


async def read_body(request, limit):
    body = bytearray()
    try:
        async with asyncio.timeout(20):
            async for chunk in request.stream():
                if len(body) + len(chunk) > limit:
                    raise HTTPException(413, "Request exceeds size limit")
                body.extend(chunk)
    except TimeoutError as exc:
        raise HTTPException(408, "Request body timeout") from exc
    except ClientDisconnect as exc:
        raise HTTPException(400, "Request body interrupted") from exc
    return bytes(body)


async def read_json(request, model):
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        raise HTTPException(415, "Expected application/json")
    try:
        return model.model_validate_json(await read_body(request, 4096))
    except ValidationError as exc:
        raise RequestValidationError(exc.errors(include_context=False, include_input=False)) from exc


async def upload(request, *, initial):
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "multipart/form-data":
        raise HTTPException(415, "Expected multipart/form-data")
    body = await read_body(request, MAX_REQUEST_BYTES)

    async def stream():
        yield body
        yield b""

    try:
        form = await BoundedMultipartParser(request.headers, stream(), max_files=1, max_fields=6,
                                            max_part_size=2048).parse()
    except (MultiPartException, ValueError) as exc:
        raise HTTPException(400, "Malformed multipart input") from exc
    try:
        items = dict(form)
        if len(items) != len(form.multi_items()):
            raise HTTPException(422, "Multipart fields must be unique")
        image = items.pop("image", None)
        if not isinstance(image, UploadFile):
            raise HTTPException(422, "Image file is required")
        if image.content_type not in ("image/jpeg", "image/png"):
            raise HTTPException(415, "Expected image/jpeg or image/png")
        capture_fields = {key: items.pop(key) for key in CaptureInput.model_fields if key in items}
        capture = validate(CaptureInput, capture_fields)
        inspection = validate(InspectionInput, items) if initial else None
        if not initial and items:
            raise HTTPException(422, "Unexpected capture fields")
        data = await image.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Image exceeds 10 MiB")
        return inspection, capture, data, image.content_type
    finally:
        await form.close()


async def engine_call(operation, *args):
    try:
        return await run_in_threadpool(operation, *args)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Inspection not found") from exc
    except ClosedInspection as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def station_unavailable():
    raise HTTPException(503, "Station acquisition is unavailable. Submit a manual image.")


def create_app(storage_root=None, token=None, benchmark_path=None):
    if token is not None and (len(token) < 32 or not token.isascii() or any(c.isspace() for c in token)):
        raise ValueError("LEO_API_TOKEN must contain at least 32 non-whitespace ASCII characters")

    def authorize(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(AUTH)]):
        if token is not None and (credentials is None or not compare_digest(credentials.credentials.encode(), token.encode())):
            raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})

    rules = load_leather_rules()
    engine = Engine(ArtifactStore(storage_root or ROOT / "storage/inspections"), rules)
    benchmark_path = benchmark_path or ROOT / "storage/benchmarks/latest.json"
    app = FastAPI(title="LEO Shield inspection API", version="1.0.0", dependencies=[Depends(authorize)],
                  responses={401: {"description": "Bearer token required when authentication is configured"}})

    @app.get("/health", response_model=Health)
    def health():
        return {"status": "ok", "contract_version": "1.0.0"}

    @app.get("/hardware/status", response_model=HardwareStatus)
    def hardware():
        try:
            port_count = len(list_ports.comports())
        except OSError:
            port_count = None
        return {"esp32_verified": False, "station_camera_verified": False, "external_lighting_verified": False,
                "serial_ports_detected": port_count, "manual_upload_available": True}

    @app.get("/engine/capabilities", response_model=Capabilities, response_model_exclude_none=True)
    def capabilities():
        return {"contract_version": "1.0.0", "profiles": {
            "leather": {"status": "experimental", "required_views": rules.required_views},
            "footwear": {"status": "unsupported"}, "auto_component": {"status": "unsupported"},
        }, "manual_upload": True, "classical_candidates": True, "trained_model": False,
            "physical_measurements": False, "station_acquisition": False}

    json_errors = {
        400: {"description": "Request body interrupted"}, 408: {"description": "Request body timed out"},
        413: {"description": "Request exceeds size limit"}, 415: {"description": "Expected application/json"},
        422: {"description": "Invalid fields"},
    }

    @app.post("/lighting/set", openapi_extra=json_schema(LightingInput),
              responses={**json_errors, 503: {"description": "Lighting hardware unavailable"}})
    async def set_lighting(request: Request):
        await read_json(request, LightingInput)
        raise HTTPException(503, "External lighting has not been verified")

    @app.post("/capture", openapi_extra=json_schema(CaptureInput),
              responses={**json_errors, 503: {"description": "Station camera unavailable"}})
    async def request_capture(request: Request):
        await read_json(request, CaptureInput)
        station_unavailable()

    upload_errors = {
        400: {"description": "Malformed multipart request"}, 408: {"description": "Upload timed out"},
        413: {"description": "Upload too large"}, 415: {"description": "Unsupported media type"},
        422: {"description": "Invalid fields, unsupported profile or undecodable image"},
    }

    @app.post("/inspect", response_model=InspectionResult, status_code=202,
              openapi_extra=multipart_schema(initial=True),
              responses={**upload_errors, 503: {"description": "Station acquisition unavailable"}})
    async def start(request: Request):
        if request.headers.get("content-type", "").split(";", 1)[0].lower() == "application/json":
            settings = await read_json(request, StationInput)
            if settings.profile != "leather":
                raise HTTPException(422, "Profile is unsupported")
            station_unavailable()
        settings, capture, data, content_type = await upload(request, initial=True)
        if settings.profile != "leather":
            raise HTTPException(422, "Profile is unsupported")
        return await engine_call(engine.start, settings, capture, data, content_type)

    @app.get("/inspections/{inspection_id}", response_model=InspectionResult,
             responses={404: {"description": "Inspection not found"}})
    def get(inspection_id: UUID):
        try:
            return engine.get(inspection_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, "Inspection not found") from exc

    @app.post("/inspections/{inspection_id}/captures", response_model=InspectionResult, status_code=202,
              openapi_extra=multipart_schema(initial=False),
              responses={**upload_errors, 404: {"description": "Inspection not found"},
                         409: {"description": "Duplicate capture, completed view or closed inspection"}})
    async def add(inspection_id: UUID, request: Request):
        _, capture, data, content_type = await upload(request, initial=False)
        return await engine_call(engine.add_capture, inspection_id, capture, data, content_type)

    @app.post("/inspections/{inspection_id}/finish", response_model=InspectionResult,
              responses={404: {"description": "Inspection not found"}})
    async def finish(inspection_id: UUID):
        return await engine_call(engine.finish, inspection_id)

    @app.get("/inspections/{inspection_id}/evidence", response_model=list[Evidence],
             responses={404: {"description": "Inspection not found"}})
    def evidence(inspection_id: UUID):
        return get(inspection_id).evidence

    @app.get("/inspections/{inspection_id}/evidence/{capture_id}/image", response_class=FileResponse,
             responses={200: {"content": {
                 media: {"schema": {"type": "string", "format": "binary"}} for media in ("image/jpeg", "image/png")
             }}, 404: {"description": "Evidence not found"}})
    def original(inspection_id: UUID, capture_id: UUID):
        entry = next((item for item in evidence(inspection_id) if item.capture_id == capture_id), None)
        path = engine.store.image_path(inspection_id, capture_id)
        if entry is None or not path.is_file():
            raise HTTPException(404, "Evidence not found")
        return FileResponse(path, media_type=entry.media_type, headers={"Cache-Control": "no-store"})

    @app.get("/benchmarks/latest", response_model=BenchmarkResult,
             responses={404: {"description": "No measured physical benchmark available"}})
    def latest_benchmark():
        try:
            benchmark = BenchmarkResult.model_validate_json(benchmark_path.read_bytes())
        except FileNotFoundError as exc:
            raise HTTPException(404, "No measured physical benchmark available") from exc
        if benchmark.source != "physical":
            raise HTTPException(404, "No measured physical benchmark available")
        return benchmark

    return app


app = create_app(token=os.environ.get("LEO_API_TOKEN") or None)
