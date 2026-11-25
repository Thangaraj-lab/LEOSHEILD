from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import secrets
import statistics
import sqlite3
import time
import uuid
import inspect
from contextlib import closing
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import starlette.routing

# This managed image has FastAPI 0.115 paired with incompatible Starlette 1.8.
# Preserve FastAPI's callback attributes so the app remains importable; startup
# work is registered through lifespan below. Normal supported installs skip this.
if "on_startup" not in inspect.signature(starlette.routing.Router.__init__).parameters:
    _router_init = starlette.routing.Router.__init__

    def _router_init_compat(self, *args, on_startup=None, on_shutdown=None, **kwargs):
        _router_init(self, *args, **kwargs)
        self.on_startup = list(on_startup or [])
        self.on_shutdown = list(on_shutdown or [])

    starlette.routing.Router.__init__ = _router_init_compat

import httpx
from PIL import Image, UnidentifiedImageError
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from backend.app.integrations.ai_engine_client import AIEngineClient
from backend.app.reports.pdf_generator import inspection_report, lot_report

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT
STORAGE = Path(os.getenv("STORAGE_PATH", str(PROJECT / "storage")))
DB_PATH = Path(os.getenv("DATABASE_PATH", str(STORAGE / "database" / "leo_shield.sqlite3")))
FRONTEND = PROJECT / "frontend"
MAX_UPLOAD = 12 * 1024 * 1024
AI_URL = os.getenv("AI_ENGINE_URL", "http://127.0.0.1:8001").rstrip("/")
AI_MODE = os.getenv("AI_ENGINE_MODE", "real").lower()
if AI_MODE != "real":
    raise RuntimeError("AI_ENGINE_MODE=mock is not available; configure real mode or omit the setting")
AI_TOKEN = os.getenv("AI_ENGINE_TOKEN", "")
INDUSTRY_PROFILES = {"leather", "footwear", "auto_component"}
LIGHTING_MODES = {"normal", "top", "left", "right", "front", "back", "unknown"}

@asynccontextmanager
async def lifespan(_app):
    initialize()
    yield


app = FastAPI(title="LEO Shield Business API", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
# The managed desktop image pairs FastAPI 0.115 with Starlette 1.x, whose
# Application middleware builder expects this attribute from newer Starlette.
# Keep request-size policy in our upload validators and avoid a global package
# downgrade that would affect other Python apps on this machine.
if not hasattr(app, "max_body_size"):
    app.max_body_size = None
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def initialize() -> None:
    for name in ("database", "images", "evidence", "lab_reports", "passports", "reports", "backups", "logs"):
        (STORAGE / name).mkdir(parents=True, exist_ok=True)
    with closing(connect()) as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, salt BLOB NOT NULL, password_hash BLOB NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS lots(id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, buyer TEXT NOT NULL DEFAULT '', product_type TEXT NOT NULL, expected_quantity INTEGER NOT NULL CHECK(expected_quantity>0), created_at TEXT NOT NULL, is_mock INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY, lot_id TEXT NOT NULL REFERENCES lots(id), code TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(lot_id,code));
        CREATE TABLE IF NOT EXISTS inspections(id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(id), state TEXT NOT NULL, recommendation TEXT, execution_mode TEXT NOT NULL, ai_result TEXT, image_name TEXT, image_sha256 TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS inspection_events(id TEXT PRIMARY KEY, inspection_id TEXT NOT NULL REFERENCES inspections(id), event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS captures(id TEXT PRIMARY KEY, inspection_id TEXT NOT NULL REFERENCES inspections(id), sequence INTEGER NOT NULL, filename TEXT NOT NULL, sha256 TEXT NOT NULL, lighting_mode TEXT NOT NULL, source TEXT NOT NULL, engine_evidence_id TEXT, metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, UNIQUE(inspection_id, sequence));
        CREATE TABLE IF NOT EXISTS defects(id TEXT PRIMARY KEY, inspection_id TEXT NOT NULL REFERENCES inspections(id), source_ai_id TEXT, original_label TEXT, label TEXT NOT NULL, status TEXT NOT NULL, x REAL, y REAL, width REAL, height REAL, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY, inspection_id TEXT NOT NULL REFERENCES inspections(id), user_id TEXT NOT NULL REFERENCES users(id), outcome TEXT NOT NULL, grade TEXT, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS station_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS buyer_requirements(buyer TEXT PRIMARY KEY, profile TEXT NOT NULL, require_coverage INTEGER NOT NULL DEFAULT 1, required_measurements_json TEXT NOT NULL DEFAULT '[]', required_labs_json TEXT NOT NULL DEFAULT '[]', updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS measurements(id TEXT PRIMARY KEY, lot_id TEXT NOT NULL REFERENCES lots(id), product_id TEXT REFERENCES products(id), name TEXT NOT NULL, value REAL NOT NULL, unit TEXT NOT NULL, recorded_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS lab_reports(id TEXT PRIMARY KEY, lot_id TEXT NOT NULL REFERENCES lots(id), report_type TEXT NOT NULL, status TEXT NOT NULL, filename TEXT, sha256 TEXT, reviewed_by TEXT REFERENCES users(id), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS dispatches(id TEXT PRIMARY KEY, lot_id TEXT NOT NULL REFERENCES lots(id), quantity INTEGER NOT NULL, authorized_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY, user_id TEXT, event TEXT NOT NULL, entity_id TEXT, details TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        inspection_cols = {r["name"] for r in con.execute("PRAGMA table_info(inspections)")}
        if "request_key" not in inspection_cols:
            con.execute("ALTER TABLE inspections ADD COLUMN request_key TEXT")
        if "engine_evidence_json" not in inspection_cols:
            con.execute("ALTER TABLE inspections ADD COLUMN engine_evidence_json TEXT")
        for inspection in con.execute("SELECT id,image_name,image_sha256,created_at FROM inspections WHERE image_name IS NOT NULL"):
            if not con.execute("SELECT 1 FROM captures WHERE inspection_id=? LIMIT 1", (inspection["id"],)).fetchone():
                con.execute("INSERT OR IGNORE INTO captures(id,inspection_id,sequence,filename,sha256,lighting_mode,source,created_at) VALUES(?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), inspection["id"], 1, inspection["image_name"], inspection["image_sha256"] or "", "unknown", "legacy_upload", inspection["created_at"]))
        lot_cols = {r["name"] for r in con.execute("PRAGMA table_info(lots)")}
        if "supplier" not in lot_cols:
            con.execute("ALTER TABLE lots ADD COLUMN supplier TEXT NOT NULL DEFAULT ''")
        if "machine" not in lot_cols:
            con.execute("ALTER TABLE lots ADD COLUMN machine TEXT NOT NULL DEFAULT ''")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_inspection_request_key ON inspections(request_key) WHERE request_key IS NOT NULL")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_defects_engine_source ON defects(inspection_id,source_ai_id) WHERE source_ai_id IS NOT NULL")
        for orphan in con.execute("SELECT id,ai_result FROM inspections WHERE state='pending'"):
            if json.loads(orphan["ai_result"] or "{}" ).get("lifecycle") == "submitting":
                failed = {"integration_error": "Application restarted before the engine submission was finalized.", "note": "No synthetic inspection result was created."}
                con.execute("UPDATE inspections SET state='failed',ai_result=?,updated_at=? WHERE id=?", (json.dumps(failed), now(), orphan["id"]))
        con.commit()
        username, password = os.getenv("BOOTSTRAP_USERNAME", "owner"), os.getenv("BOOTSTRAP_PASSWORD", "")
        if password and not con.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            salt = secrets.token_bytes(16)
            digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
            con.execute("INSERT INTO users VALUES(?,?,?,?,?,?)", (str(uuid.uuid4()), username, salt, digest, "owner", now()))
            con.commit()


def audit(con: sqlite3.Connection, user: str | None, event: str, entity: str | None, details: dict) -> None:
    con.execute("INSERT INTO audit VALUES(?,?,?,?,?,?)", (str(uuid.uuid4()), user, event, entity, json.dumps(details, separators=(",", ":")), now()))


def engine_url() -> str:
    with closing(connect()) as con:
        row = con.execute("SELECT value FROM station_settings WHERE key='engine_url'").fetchone()
        return (row["value"] if row else AI_URL).rstrip("/")


def verify_image(payload: bytes, content_type: str) -> tuple[str, int, int]:
    expected = {"image/jpeg": "JPEG", "image/png": "PNG"}.get(content_type)
    if not expected:
        raise HTTPException(415, "Upload a JPEG or PNG image")
    try:
        with Image.open(io.BytesIO(payload)) as img:
            actual, width, height = img.format, img.width, img.height
            img.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(415, "Image file is invalid or unsafe") from exc
    if actual != expected:
        raise HTTPException(415, "File contents do not match the declared image type")
    if width < 64 or height < 64:
        raise HTTPException(415, "Image must be at least 64 by 64 pixels")
    if width * height > 40_000_000:
        raise HTTPException(413, "Image dimensions exceed the 40 megapixel limit")
    return expected, width, height


def validate_engine_result(value: object) -> dict:
    states = {"pending", "capturing", "analyzing", "awaiting_capture", "completed", "failed", "cancelled"}
    recommendations = {"no_defect_flagged", "review", "reject_recommended", "hold"}
    if not isinstance(value, dict):
        raise ValueError("Engine response must be a JSON object")
    if value.get("status") not in states:
        raise ValueError("Engine response has a missing or unsupported inspection state")
    if value.get("recommendation") not in recommendations:
        raise ValueError("Engine response has a missing or unsupported recommendation")
    version = value.get("contract_version")
    if version is not None and version != "1.0.0":
        raise ValueError("Engine contract version is not supported")
    if value.get("human_approval_required") is False:
        raise ValueError("Engine response cannot waive required human approval")
    if value.get("inspection_id") is not None:
        try:
            uuid.UUID(str(value["inspection_id"]))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("Engine inspection_id must be a UUID") from exc
    if "defects" in value and not isinstance(value["defects"], list):
        raise ValueError("Engine defects must be a JSON array")
    if "coverage" in value and not isinstance(value["coverage"], dict):
        raise ValueError("Engine coverage must be a JSON object")
    return value


def defect_geometry(defect: dict) -> tuple[float | None, float | None, float | None, float | None]:
    box = defect.get("bounding_box", defect.get("bbox"))
    if isinstance(box, (list, tuple)) and len(box) == 4:
        box = {"x": box[0], "y": box[1], "width": box[2], "height": box[3]}
    if not isinstance(box, dict):
        return None, None, None, None
    try:
        x = float(box.get("x", box.get("left")))
        y = float(box.get("y", box.get("top")))
        width = float(box.get("width", float(box["right"]) - x if "right" in box else None))
        height = float(box.get("height", float(box["bottom"]) - y if "bottom" in box else None))
    except (TypeError, ValueError, KeyError):
        return None, None, None, None
    if min(x, y, width, height) < 0 or max(x, y, width, height) > 1 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
        return None, None, None, None
    return x, y, width, height


def save_ai_defects(con: sqlite3.Connection, inspection_id: str, result: dict) -> None:
    defects = result.get("defects", [])
    if not isinstance(defects, list):
        return
    for index, defect in enumerate(defects):
        if not isinstance(defect, dict):
            continue
        label = str(defect.get("label", defect.get("type", defect.get("category", "Unlabeled AI defect"))))[:100]
        x, y, width, height = defect_geometry(defect)
        con.execute("INSERT OR IGNORE INTO defects VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), inspection_id, str(defect.get("defect_id", defect.get("id", index)))[:100], label, label, "ai", x, y, width, height, "", now(), now()))


def current_user(authorization: Annotated[str | None, Header()] = None) -> sqlite3.Row:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in required")
    token = authorization[7:]
    with closing(connect()) as con:
        row = con.execute("SELECT u.id,u.username,u.role,s.expires_at FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row or row["expires_at"] < time.time():
            raise HTTPException(401, "Session expired")
        return row


User = Annotated[sqlite3.Row, Depends(current_user)]


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class LotInput(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    product_type: str = Field(min_length=1, max_length=60)
    buyer: str = Field(default="", max_length=120)
    expected_quantity: int = Field(gt=0, le=100000)
    supplier: str = Field(default="", max_length=120)
    machine: str = Field(default="", max_length=120)


class ProductInput(BaseModel):
    code: str = Field(min_length=1, max_length=80)


class DecisionInput(BaseModel):
    outcome: str
    grade: str | None = Field(default=None, max_length=40)
    notes: str = Field(min_length=1, max_length=1000)


class StationSettingsInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    engine_url: str = Field(min_length=8, max_length=300)


class DefectInput(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    status: str = "manual"
    source_ai_id: str | None = None
    x: float | None = Field(default=None, ge=0, le=1)
    y: float | None = Field(default=None, ge=0, le=1)
    width: float | None = Field(default=None, gt=0, le=1)
    height: float | None = Field(default=None, gt=0, le=1)
    notes: str = Field(default="", max_length=500)


class DefectUpdate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    status: str
    notes: str = Field(default="", max_length=500)


class BuyerRequirementsInput(BaseModel):
    buyer: str = Field(min_length=1, max_length=120)
    profile: str
    require_coverage: bool = True
    required_measurements: list[str] = Field(default_factory=list, max_length=30)
    required_labs: list[str] = Field(default_factory=list, max_length=30)


class MeasurementInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    value: float
    unit: str = Field(min_length=1, max_length=24)
    product_id: str | None = None


class DispatchInput(BaseModel):
    quantity: int = Field(gt=0, le=100000)


class LabReviewInput(BaseModel):
    status: str


@app.get("/health")
def health():
    return {"status": "ok", "database": "sqlite", "engine_mode": AI_MODE}


@app.post("/api/v1/auth/login")
def login(body: Credentials):
    with closing(connect()) as con:
        row = con.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
        if row is None:
            raise HTTPException(503, "No local account exists. Set BOOTSTRAP_PASSWORD and restart once to create the first owner account.")
        candidate = hashlib.scrypt(body.password.encode(), salt=row["salt"], n=2**14, r=8, p=1)
        if not hmac.compare_digest(candidate, row["password_hash"]):
            raise HTTPException(401, "Invalid username or password")
        token = secrets.token_urlsafe(32)
        hours = max(1, min(24, int(os.getenv("SESSION_HOURS", "8"))))
        con.execute("INSERT INTO sessions VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), row["id"], time.time() + hours * 3600))
        audit(con, row["id"], "auth.login", row["id"], {})
        con.commit()
        return {"token": token, "user": {"id": row["id"], "username": row["username"], "role": row["role"]}, "expires_in": hours * 3600}


@app.get("/api/v1/auth/me")
def me(user: User):
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


@app.post("/api/v1/auth/logout")
def logout(user: User, authorization: Annotated[str, Header()]):
    token = authorization[7:]
    with closing(connect()) as con:
        con.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        audit(con, user["id"], "auth.logout", user["id"], {})
        con.commit()
    return {"ok": True}


@app.get("/api/v1/engine/status")
def engine_status(user: User):
    client = AIEngineClient(engine_url(), AI_TOKEN, timeout=2.5)
    result = {"mode": AI_MODE, "url": engine_url()}
    for key, endpoint in (("health", "/health"), ("hardware", "/hardware/status"), ("capabilities", "/engine/capabilities")):
        try:
            result[key] = client.get_json(endpoint)
            result[f"{key}_available"] = True
        except (httpx.HTTPError, ValueError) as exc:
            result[key] = None
            result[f"{key}_available"] = False
            result[f"{key}_error"] = str(exc)
    health = result.get("health")
    result["available"] = bool(result["health_available"] and isinstance(health, dict) and health.get("status") in {"ok", "healthy", "available"})
    return result


@app.get("/api/v1/settings/station")
def get_station_settings(user: User):
    with closing(connect()) as con:
        values = {r["key"]: r["value"] for r in con.execute("SELECT key,value FROM station_settings")}
    return {"name": values.get("name", "Inspection Station"), "engine_url": values.get("engine_url", AI_URL), "token_configured": bool(AI_TOKEN)}


@app.put("/api/v1/settings/station")
def put_station_settings(body: StationSettingsInput, user: User):
    from urllib.parse import urlparse
    parsed = urlparse(body.engine_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(422, "Enter an HTTP(S) base URL without embedded credentials or query strings")
    with closing(connect()) as con:
        con.execute("INSERT INTO station_settings(key,value,updated_at) VALUES('name',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at", (body.name.strip(), now()))
        con.execute("INSERT INTO station_settings(key,value,updated_at) VALUES('engine_url',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at", (body.engine_url.rstrip("/"), now()))
        audit(con, user["id"], "station.settings_updated", None, {"name": body.name, "engine_url": body.engine_url})
        con.commit()
    return get_station_settings(user)


@app.get("/api/v1/engine/capabilities")
def engine_capabilities(user: User):
    try:
        return AIEngineClient(engine_url(), AI_TOKEN, timeout=4).get_json("/engine/capabilities")
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, f"AI engine capabilities unavailable: {exc}") from exc


@app.get("/api/v1/lots")
def list_lots(user: User):
    with closing(connect()) as con:
        rows = con.execute("SELECT * FROM lots ORDER BY created_at DESC").fetchall()
        out = []
        for row in rows:
            lot = dict(row)
            lot.update(lot_summary(con, row["id"]))
            out.append(lot)
        return out


def lot_summary(con: sqlite3.Connection, lot_id: str) -> dict:
    rows = con.execute("""
        SELECT p.id,
          (SELECT i.id FROM inspections i WHERE i.product_id=p.id ORDER BY i.created_at DESC,i.rowid DESC LIMIT 1) inspection_id,
          (SELECT i.state FROM inspections i WHERE i.product_id=p.id ORDER BY i.created_at DESC,i.rowid DESC LIMIT 1) state,
          (SELECT d.outcome FROM decisions d WHERE d.inspection_id=(SELECT i.id FROM inspections i WHERE i.product_id=p.id ORDER BY i.created_at DESC,i.rowid DESC LIMIT 1) ORDER BY d.created_at DESC,d.rowid DESC LIMIT 1) outcome,
          (SELECT d.grade FROM decisions d WHERE d.inspection_id=(SELECT i.id FROM inspections i WHERE i.product_id=p.id ORDER BY i.created_at DESC,i.rowid DESC LIMIT 1) ORDER BY d.created_at DESC,d.rowid DESC LIMIT 1) grade
        FROM products p WHERE p.lot_id=?
    """, (lot_id,)).fetchall()
    grades: dict[str, int] = {}
    counts = {"accepted_quantity": 0, "rejected_quantity": 0, "held_quantity": 0, "pending_quantity": 0}
    for row in rows:
        if row["outcome"] in {"PASS", "GRADE"}:
            counts["accepted_quantity"] += 1
            if row["outcome"] == "GRADE" and row["grade"]:
                grades[row["grade"]] = grades.get(row["grade"], 0) + 1
        elif row["outcome"] == "REJECT":
            counts["rejected_quantity"] += 1
        elif row["outcome"] == "HOLD":
            counts["held_quantity"] += 1
        else:
            counts["pending_quantity"] += 1
    inspections = con.execute("SELECT count(*) n FROM inspections i JOIN products p ON p.id=i.product_id WHERE p.lot_id=?", (lot_id,)).fetchone()["n"]
    return {"product_count": len(rows), "inspections_count": inspections, **counts, "grade_distribution": grades}


@app.get("/api/v1/lots/{lot_id}/summary")
def get_lot_summary(lot_id: str, user: User):
    with closing(connect()) as con:
        lot = con.execute("SELECT * FROM lots WHERE id=?", (lot_id,)).fetchone()
        if not lot:
            raise HTTPException(404, "Lot not found")
        return {"lot": dict(lot), **lot_summary(con, lot_id)}


@app.post("/api/v1/lots")
def create_lot(body: LotInput, user: User):
    lot_id = str(uuid.uuid4())
    with closing(connect()) as con:
        try:
            con.execute("INSERT INTO lots(id,code,buyer,product_type,expected_quantity,created_at,supplier,machine) VALUES(?,?,?,?,?,?,?,?)", (lot_id, body.code, body.buyer, body.product_type, body.expected_quantity, now(), body.supplier, body.machine))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Lot code already exists")
        audit(con, user["id"], "lot.created", lot_id, body.model_dump())
        con.commit()
    return {"id": lot_id, **body.model_dump()}


@app.post("/api/v1/lots/{lot_id}/products")
def add_product(lot_id: str, body: ProductInput, user: User):
    product_id = str(uuid.uuid4())
    with closing(connect()) as con:
        lot = con.execute("SELECT * FROM lots WHERE id=?", (lot_id,)).fetchone()
        if not lot:
            raise HTTPException(404, "Lot not found")
        count = con.execute("SELECT count(*) n FROM products WHERE lot_id=?", (lot_id,)).fetchone()["n"]
        if count >= lot["expected_quantity"]:
            raise HTTPException(409, "Lot expected quantity already registered")
        try:
            con.execute("INSERT INTO products VALUES(?,?,?,?)", (product_id, lot_id, body.code, now()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Product code already exists in this lot")
        audit(con, user["id"], "product.registered", product_id, {"lot_id": lot_id})
        con.commit()
    return {"id": product_id, "lot_id": lot_id, "code": body.code}


@app.get("/api/v1/lots/{lot_id}/products")
def list_products(lot_id: str, user: User):
    with closing(connect()) as con:
        if not con.execute("SELECT 1 FROM lots WHERE id=?", (lot_id,)).fetchone():
            raise HTTPException(404, "Lot not found")
        rows = con.execute("""
            SELECT p.id,p.lot_id,p.code,p.created_at,
              (SELECT json_object('id',i.id,'state',i.state,'recommendation',i.recommendation,'created_at',i.created_at)
                 FROM inspections i WHERE i.product_id=p.id ORDER BY i.created_at DESC,i.rowid DESC LIMIT 1) inspection_json
            FROM products p WHERE p.lot_id=? ORDER BY p.created_at
        """, (lot_id,)).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["inspection"] = json.loads(item.pop("inspection_json")) if item["inspection_json"] else None
            if item["inspection"]:
                item["inspection"]["decision"] = con.execute("SELECT outcome,grade FROM decisions WHERE inspection_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (item["inspection"]["id"],)).fetchone()
                if item["inspection"]["decision"]:
                    item["inspection"]["decision"] = dict(item["inspection"]["decision"])
            items.append(item)
        return items


@app.post("/api/v1/products/{product_id}/inspections")
def inspect_product(
    product_id: str,
    user: User,
    image: UploadFile = File(...),
    industry_profile: str = Form(default="leather"),
    lighting_mode: str = Form(default="unknown"),
    request_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if industry_profile not in INDUSTRY_PROFILES:
        raise HTTPException(422, "Choose a supported industry profile")
    if lighting_mode not in LIGHTING_MODES:
        raise HTTPException(422, "Choose a supported lighting label")
    payload = image.file.read(MAX_UPLOAD + 1)
    if len(payload) > MAX_UPLOAD:
        raise HTTPException(413, "Image exceeds the 12 MiB limit")
    image_format, width_px, height_px = verify_image(payload, image.content_type or "")
    digest = hashlib.sha256(payload).hexdigest()
    request_key = (request_key or str(uuid.uuid4())).strip()
    if len(request_key) > 100:
        raise HTTPException(422, "Idempotency key is too long")
    inspection_id = str(uuid.uuid4())
    suffix = ".jpg" if image_format == "JPEG" else ".png"
    filename = f"{inspection_id}{suffix}"
    image_path = STORAGE / "images" / filename
    image_path.write_bytes(payload)
    created_at = now()
    mode = "real"
    with closing(connect()) as con:
        con.execute("BEGIN IMMEDIATE")
        product = con.execute("SELECT p.*,l.product_type FROM products p JOIN lots l ON l.id=p.lot_id WHERE p.id=?", (product_id,)).fetchone()
        if not product:
            image_path.unlink(missing_ok=True)
            raise HTTPException(404, "Product not found")
        lot_profile = {"Leather":"leather","Footwear":"footwear","Auto component":"auto_component"}.get(product["product_type"])
        if lot_profile and industry_profile != lot_profile:
            con.rollback()
            image_path.unlink(missing_ok=True)
            raise HTTPException(422, f"Selected profile must match this product lot ({lot_profile})")
        previous = con.execute("SELECT i.id,i.image_sha256,i.product_id,c.lighting_mode,c.metadata_json FROM inspections i LEFT JOIN captures c ON c.inspection_id=i.id AND c.sequence=1 WHERE i.request_key=?", (request_key,)).fetchone()
        if previous:
            con.rollback()
            image_path.unlink(missing_ok=True)
            prior_metadata=json.loads(previous["metadata_json"] or "{}") if previous["metadata_json"] else {}
            if previous["image_sha256"] != digest or previous["product_id"] != product_id or previous["lighting_mode"] != lighting_mode or prior_metadata.get("profile") != industry_profile:
                raise HTTPException(409, "This idempotency key was already used with a different product, image or capture setting")
            return get_inspection(previous["id"], user)
        con.execute("INSERT INTO inspections(id,product_id,state,recommendation,execution_mode,ai_result,image_name,image_sha256,created_at,updated_at,request_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (inspection_id, product_id, "pending", None, mode, json.dumps({"lifecycle": "submitting"}), filename, digest, created_at, created_at, request_key))
        con.execute("INSERT INTO captures VALUES(?,?,?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), inspection_id, 1, filename, digest, lighting_mode, "operator_upload", None, json.dumps({"profile": industry_profile, "width": width_px, "height": height_px, "content_type": image.content_type}), created_at))
        audit(con, user["id"], "inspection.submission_started", inspection_id, {"request_key": request_key, "sha256": digest})
        con.commit()
    result, state = None, "failed"
    evidence_metadata = None
    try:
        client = AIEngineClient(engine_url(), AI_TOKEN)
        result = validate_engine_result(client.inspect_image(payload, image.filename or filename, image.content_type or "", product["code"], product["lot_id"], industry_profile, lighting_mode))
        state = result["status"]
        if state == "completed" and result.get("inspection_id"):
            try:
                evidence_metadata = client.evidence_metadata(result["inspection_id"])
            except (httpx.HTTPError, ValueError) as exc:
                evidence_metadata = {"unavailable": str(exc), "note": "No image evidence was transferred; Laptop 1 exposes only this metadata endpoint contract so far."}
    except (httpx.HTTPError, ValueError) as exc:
        result = {"integration_error": str(exc), "note": "No synthetic inspection result was created."}
    with closing(connect()) as con:
        con.execute("UPDATE inspections SET state=?,recommendation=?,ai_result=?,engine_evidence_json=?,updated_at=? WHERE id=?", (state, (result or {}).get("recommendation"), json.dumps(result), json.dumps(evidence_metadata) if evidence_metadata is not None else None, now(), inspection_id))
        con.execute("INSERT INTO inspection_events VALUES(?,?,?,?,?)", (str(uuid.uuid4()), inspection_id, "initial_engine_result" if result and "integration_error" not in result else "submission_error", json.dumps(result), now()))
        if result and state == "completed":
            save_ai_defects(con, inspection_id, result)
        audit(con, user["id"], "inspection.created", inspection_id, {"execution_mode": mode, "state": state, "lighting_mode": lighting_mode, "profile": industry_profile, "image_sha256": digest})
        con.commit()
    return get_inspection(inspection_id, user)


@app.post("/api/v1/inspections/{inspection_id}/evidence")
def add_evidence(
    inspection_id: str,
    user: User,
    image: UploadFile = File(...),
    lighting_mode: str = Form(default="unknown"),
):
    if lighting_mode not in LIGHTING_MODES:
        raise HTTPException(422, "Choose a supported lighting label")
    payload = image.file.read(MAX_UPLOAD + 1)
    if len(payload) > MAX_UPLOAD:
        raise HTTPException(413, "Image exceeds the 12 MiB limit")
    image_format, width_px, height_px = verify_image(payload, image.content_type or "")
    digest = hashlib.sha256(payload).hexdigest()
    capture_id = str(uuid.uuid4())
    filename = f"{capture_id}.{'jpg' if image_format == 'JPEG' else 'png'}"
    with closing(connect()) as con:
        inspection = con.execute("SELECT * FROM inspections WHERE id=?", (inspection_id,)).fetchone()
        if not inspection:
            raise HTTPException(404, "Inspection not found")
        seq = con.execute("SELECT coalesce(max(sequence),0)+1 n FROM captures WHERE inspection_id=?", (inspection_id,)).fetchone()["n"]
        if seq > 20:
            raise HTTPException(409, "An inspection can store up to 20 captures")
        (STORAGE / "evidence" / filename).write_bytes(payload)
        created_at = now()
        con.execute("INSERT INTO captures VALUES(?,?,?,?,?,?,?,?,?,?)", (capture_id, inspection_id, seq, filename, digest, lighting_mode, "operator_additional", None, json.dumps({"width": width_px, "height": height_px, "content_type": image.content_type, "submitted_to_engine": False}), created_at))
        audit(con, user["id"], "inspection.evidence_added", inspection_id, {"capture_id": capture_id, "lighting_mode": lighting_mode, "submitted_to_engine": False, "sha256": digest})
        con.commit()
    return {"id": capture_id, "inspection_id": inspection_id, "sequence": seq, "lighting_mode": lighting_mode, "sha256": digest, "submitted_to_engine": False, "notice": "Saved for operator review. Laptop 1 additional-image submission is not yet defined in the shared contract."}


@app.get("/api/v1/inspections/{inspection_id}")
def get_inspection(inspection_id: str, user: User):
    with closing(connect()) as con:
        row = con.execute("SELECT i.*,p.code product_code,p.lot_id FROM inspections i JOIN products p ON p.id=i.product_id WHERE i.id=?", (inspection_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Inspection not found")
        decision = con.execute("SELECT d.outcome,d.grade,d.notes,d.created_at,u.username FROM decisions d JOIN users u ON u.id=d.user_id WHERE d.inspection_id=? ORDER BY d.created_at DESC LIMIT 1", (inspection_id,)).fetchone()
        out = dict(row)
        out["ai_result"] = json.loads(out["ai_result"] or "null")
        out["engine_evidence"] = json.loads(out["engine_evidence_json"] or "null")
        out["decision"] = dict(decision) if decision else None
        out["captures"] = [dict(r) for r in con.execute("SELECT id,sequence,sha256,lighting_mode,source,engine_evidence_id,metadata_json,created_at FROM captures WHERE inspection_id=? ORDER BY sequence", (inspection_id,))]
        for capture in out["captures"]:
            capture["metadata"] = json.loads(capture.pop("metadata_json") or "{}")
            capture["image_url"] = f"/api/v1/captures/{capture['id']}/image"
        out["defects"] = [dict(r) for r in con.execute("SELECT * FROM defects WHERE inspection_id=? ORDER BY created_at", (inspection_id,))]
        out["engine_events"] = [{"id":r["id"],"event_type":r["event_type"],"payload":json.loads(r["payload_json"]),"created_at":r["created_at"]} for r in con.execute("SELECT id,event_type,payload_json,created_at FROM inspection_events WHERE inspection_id=? ORDER BY created_at,rowid", (inspection_id,))]
        return out


@app.post("/api/v1/inspections/{inspection_id}/refresh")
def refresh_inspection(inspection_id: str, user: User):
    current=get_inspection(inspection_id,user)
    if current["state"] not in {"pending","capturing","analyzing"}:
        return {"state":current["state"],"pollable":False,"inspection":current}
    upstream_id=(current["ai_result"] or {}).get("inspection_id") if isinstance(current["ai_result"],dict) else None
    if not upstream_id:
        return {"state":current["state"],"pollable":False,"error":"Engine did not return a job UUID; status cannot be polled."}
    with closing(connect()) as con:
        row=con.execute("SELECT updated_at FROM inspections WHERE id=?",(inspection_id,)).fetchone()
    try:
        last=datetime.fromisoformat(row["updated_at"])
        if (datetime.now(timezone.utc)-last).total_seconds()<1.5:
            return {"state":current["state"],"pollable":True,"inspection":current}
    except (TypeError,ValueError):
        pass
    client=AIEngineClient(engine_url(),AI_TOKEN,timeout=8)
    try:
        result=validate_engine_result(client.get_json(f"/inspections/{upstream_id}"))
        evidence=None
        if result["status"]=="completed":
            try:evidence=client.evidence_metadata(upstream_id)
            except (httpx.HTTPError,ValueError) as exc:evidence={"unavailable":str(exc),"note":"No image bytes were transferred."}
        with closing(connect()) as con:
            con.execute("UPDATE inspections SET state=?,ai_result=?,engine_evidence_json=?,updated_at=? WHERE id=?",(result["status"],json.dumps(result),json.dumps(evidence) if evidence is not None else None,now(),inspection_id))
            con.execute("INSERT INTO inspection_events VALUES(?,?,?,?,?)",(str(uuid.uuid4()),inspection_id,"engine_status_update",json.dumps(result),now()))
            if result["status"]=="completed":save_ai_defects(con,inspection_id,result)
            audit(con,user["id"],"inspection.status_updated",inspection_id,{"state":result["status"]})
            con.commit()
        current=get_inspection(inspection_id,user)
        return {"state":current["state"],"pollable":current["state"] in {"pending","capturing","analyzing"},"inspection":current}
    except (httpx.HTTPError,ValueError) as exc:
        return {"state":current["state"],"pollable":True,"error":str(exc)}


@app.get("/api/v1/inspections/{inspection_id}/image")
def inspection_image(inspection_id: str, user: User):
    with closing(connect()) as con:
        row = con.execute("SELECT image_name FROM inspections WHERE id=?", (inspection_id,)).fetchone()
        if not row or not row["image_name"]:
            raise HTTPException(404, "Image not found")
    path = (STORAGE / "images" / row["image_name"]).resolve()
    if path.parent != (STORAGE / "images").resolve() or not path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(path)


@app.get("/api/v1/captures/{capture_id}/image")
def capture_image(capture_id: str, user: User):
    with closing(connect()) as con:
        row = con.execute("SELECT filename,source FROM captures WHERE id=?", (capture_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Capture not found")
    folder = "images" if row["source"] in {"operator_upload", "legacy_upload"} else "evidence"
    path = (STORAGE / folder / row["filename"]).resolve()
    if path.parent not in {(STORAGE / "images").resolve(), (STORAGE / "evidence").resolve()} or not path.is_file():
        raise HTTPException(404, "Capture image not found")
    return FileResponse(path)


@app.get("/api/v1/inspections/{inspection_id}/history")
def inspection_history(inspection_id: str, user: User):
    with closing(connect()) as con:
        if not con.execute("SELECT 1 FROM inspections WHERE id=?", (inspection_id,)).fetchone():
            raise HTTPException(404, "Inspection not found")
        return [dict(r) for r in con.execute("SELECT id,state,recommendation,execution_mode,created_at,updated_at FROM inspections WHERE product_id=(SELECT product_id FROM inspections WHERE id=?) ORDER BY created_at DESC,rowid DESC", (inspection_id,))]


@app.get("/api/v1/quality-rules/buyers")
def list_buyer_requirements(user: User):
    with closing(connect()) as con:
        rows = con.execute("SELECT * FROM buyer_requirements ORDER BY buyer").fetchall()
        return [{**dict(r), "required_measurements": json.loads(r["required_measurements_json"]), "required_labs": json.loads(r["required_labs_json"])} for r in rows]


@app.put("/api/v1/quality-rules/buyers")
def put_buyer_requirements(body: BuyerRequirementsInput, user: User):
    if body.profile not in INDUSTRY_PROFILES:
        raise HTTPException(422, "Unsupported buyer inspection profile")
    if len(set(body.required_measurements)) != len(body.required_measurements) or len(set(body.required_labs)) != len(body.required_labs):
        raise HTTPException(422, "Requirement names must be unique")
    with closing(connect()) as con:
        con.execute("INSERT INTO buyer_requirements VALUES(?,?,?,?,?,?) ON CONFLICT(buyer) DO UPDATE SET profile=excluded.profile,require_coverage=excluded.require_coverage,required_measurements_json=excluded.required_measurements_json,required_labs_json=excluded.required_labs_json,updated_at=excluded.updated_at", (body.buyer.strip(), body.profile, int(body.require_coverage), json.dumps(body.required_measurements), json.dumps(body.required_labs), now()))
        audit(con, user["id"], "quality.buyer_requirements_updated", None, body.model_dump())
        con.commit()
    return {"ok": True}


@app.post("/api/v1/lots/{lot_id}/measurements")
def record_measurement(lot_id: str, body: MeasurementInput, user: User):
    measurement_id = str(uuid.uuid4())
    with closing(connect()) as con:
        if not con.execute("SELECT 1 FROM lots WHERE id=?", (lot_id,)).fetchone():
            raise HTTPException(404, "Lot not found")
        if body.product_id and not con.execute("SELECT 1 FROM products WHERE id=? AND lot_id=?", (body.product_id, lot_id)).fetchone():
            raise HTTPException(404, "Product is not part of this lot")
        con.execute("INSERT INTO measurements VALUES(?,?,?,?,?,?,?,?)", (measurement_id, lot_id, body.product_id, body.name.strip(), body.value, body.unit.strip(), user["id"], now()))
        audit(con, user["id"], "quality.measurement_recorded", lot_id, {**body.model_dump(), "measurement_id": measurement_id})
        con.commit()
    return {"id": measurement_id, **body.model_dump()}


@app.post("/api/v1/lots/{lot_id}/lab-reports")
def attach_lab_report(lot_id: str, user: User, report_type: str = Form(..., min_length=1, max_length=80), file: UploadFile = File(...)):
    payload = file.file.read(15 * 1024 * 1024 + 1)
    if len(payload) > 15 * 1024 * 1024:
        raise HTTPException(413, "Lab report exceeds the 15 MiB limit")
    if file.content_type != "application/pdf" or not payload.startswith(b"%PDF-"):
        raise HTTPException(415, "Upload a valid PDF laboratory report")
    report_id = str(uuid.uuid4())
    filename = f"{report_id}.pdf"
    (STORAGE / "lab_reports" / filename).write_bytes(payload)
    with closing(connect()) as con:
        if not con.execute("SELECT 1 FROM lots WHERE id=?", (lot_id,)).fetchone():
            raise HTTPException(404, "Lot not found")
        con.execute("INSERT INTO lab_reports VALUES(?,?,?,?,?,?,?,?)", (report_id, lot_id, report_type.strip(), "pending_review", filename, hashlib.sha256(payload).hexdigest(), None, now()))
        audit(con, user["id"], "quality.lab_report_uploaded", lot_id, {"report_id": report_id, "report_type": report_type, "sha256": hashlib.sha256(payload).hexdigest()})
        con.commit()
    return {"id": report_id, "status": "pending_review", "sha256": hashlib.sha256(payload).hexdigest()}


@app.post("/api/v1/lab-reports/{report_id}/review")
def review_lab_report(report_id: str, body: LabReviewInput, user: User):
    if body.status not in {"accepted", "rejected"}:
        raise HTTPException(422, "Lab review status must be accepted or rejected")
    with closing(connect()) as con:
        report = con.execute("SELECT * FROM lab_reports WHERE id=?", (report_id,)).fetchone()
        if not report:
            raise HTTPException(404, "Lab report not found")
        con.execute("UPDATE lab_reports SET status=?,reviewed_by=? WHERE id=?", (body.status, user["id"], report_id))
        audit(con, user["id"], "quality.lab_report_reviewed", report["lot_id"], {"report_id": report_id, "status": body.status})
        con.commit()
    return {"id": report_id, "status": body.status}


@app.get("/api/v1/reports/inspections/{inspection_id}.pdf")
def download_inspection_report(inspection_id: str, user: User):
    try:
        with closing(connect()) as con:
            path = inspection_report(con, STORAGE, inspection_id)
    except KeyError as exc:
        raise HTTPException(404, "Inspection not found") from exc
    return FileResponse(path, media_type="application/pdf", filename=f"leo-inspection-{inspection_id[:8]}.pdf")


@app.get("/api/v1/reports/lots/{lot_id}.pdf")
def download_lot_report(lot_id: str, user: User):
    try:
        with closing(connect()) as con:
            gate = evaluate_export_gate(con, lot_id)
            stats = lot_summary(con, lot_id)
            path = lot_report(con, STORAGE, lot_id, gate, stats)
    except KeyError as exc:
        raise HTTPException(404, "Lot not found") from exc
    return FileResponse(path, media_type="application/pdf", filename=f"leo-lot-report-{lot_id[:8]}.pdf")


@app.post("/api/v1/inspections/{inspection_id}/defects")
def add_manual_defect(inspection_id: str, body: DefectInput, user: User):
    if body.status != "manual":
        raise HTTPException(422, "New defects must use the manual status")
    coords = (body.x, body.y, body.width, body.height)
    if any(value is not None for value in coords) and not all(value is not None for value in coords):
        raise HTTPException(422, "Provide all normalized box coordinates or omit the box")
    if body.x is not None and (body.x + (body.width or 0) > 1 or body.y + (body.height or 0) > 1):
        raise HTTPException(422, "Bounding box must fit within normalized image coordinates")
    defect_id = str(uuid.uuid4())
    with closing(connect()) as con:
        if not con.execute("SELECT 1 FROM inspections WHERE id=?", (inspection_id,)).fetchone():
            raise HTTPException(404, "Inspection not found")
        con.execute("INSERT INTO defects VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (defect_id, inspection_id, None, None, body.label, "manual", body.x, body.y, body.width, body.height, body.notes, now(), now()))
        audit(con, user["id"], "inspection.defect_added", inspection_id, body.model_dump())
        con.commit()
    return {"id": defect_id, "inspection_id": inspection_id, "status": "manual", **body.model_dump()}


@app.patch("/api/v1/inspections/{inspection_id}/defects/{defect_id}")
def update_defect(inspection_id: str, defect_id: str, body: DefectUpdate, user: User):
    if body.status not in {"confirmed", "corrected", "false_positive"}:
        raise HTTPException(422, "Status must be confirmed, corrected or false_positive")
    with closing(connect()) as con:
        row = con.execute("SELECT * FROM defects WHERE id=? AND inspection_id=?", (defect_id, inspection_id)).fetchone()
        if not row:
            raise HTTPException(404, "Defect annotation not found")
        con.execute("UPDATE defects SET label=?,status=?,notes=?,updated_at=? WHERE id=?", (body.label, body.status, body.notes, now(), defect_id))
        audit(con, user["id"], "inspection.defect_updated", inspection_id, {"defect_id": defect_id, **body.model_dump()})
        con.commit()
        return dict(con.execute("SELECT * FROM defects WHERE id=?", (defect_id,)).fetchone())


@app.post("/api/v1/inspections/{inspection_id}/decisions")
def decide(inspection_id: str, body: DecisionInput, user: User):
    if body.outcome not in {"PASS", "GRADE", "REJECT", "HOLD"}:
        raise HTTPException(422, "Outcome must be PASS, GRADE, REJECT or HOLD")
    if body.outcome == "GRADE" and not body.grade:
        raise HTTPException(422, "Grade is required for a GRADE decision")
    if not body.notes.strip():
        raise HTTPException(422, "A decision reason is required")
    with closing(connect()) as con:
        inspection = con.execute("SELECT * FROM inspections WHERE id=?", (inspection_id,)).fetchone()
        if not inspection:
            raise HTTPException(404, "Inspection not found")
        if inspection["state"] != "completed" and body.outcome in {"PASS", "GRADE"}:
            raise HTTPException(409, "Only completed inspections can receive PASS or GRADE")
        if body.outcome in {"PASS", "GRADE"}:
            ai_result = json.loads(inspection["ai_result"] or "null")
            coverage = ai_result.get("coverage") if isinstance(ai_result, dict) else None
            quality = ai_result.get("image_quality") if isinstance(ai_result, dict) else None
            if not isinstance(coverage, dict) or coverage.get("complete") is not True:
                raise HTTPException(409, "Mandatory inspection coverage is missing or incomplete")
            if not isinstance(quality, dict) or quality.get("acceptable") is not True:
                raise HTTPException(409, "Capture quality is missing or unacceptable")
        decision_id = str(uuid.uuid4())
        con.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?,?)", (decision_id, inspection_id, user["id"], body.outcome, body.grade, body.notes, now()))
        audit(con, user["id"], "inspection.decision", inspection_id, body.model_dump())
        con.commit()
    return {"id": decision_id, "inspection_id": inspection_id, **body.model_dump()}


def evaluate_export_gate(con: sqlite3.Connection, lot_id: str) -> dict:
    lot = con.execute("SELECT * FROM lots WHERE id=?", (lot_id,)).fetchone()
    if not lot:
        raise HTTPException(404, "Lot not found")
    summary_data = lot_summary(con, lot_id)
    blockers = []
    if summary_data["product_count"] != lot["expected_quantity"]:
        blockers.append(f"Registered quantity {summary_data['product_count']} does not match expected {lot['expected_quantity']}")
    requirements = con.execute("SELECT * FROM buyer_requirements WHERE buyer=?", (lot["buyer"].strip(),)).fetchone() if lot["buyer"].strip() else None
    if not requirements:
        blockers.append("Buyer quality requirements are not configured")
    else:
        product_profile = {"Leather": "leather", "Footwear": "footwear", "Auto component": "auto_component"}.get(lot["product_type"])
        if product_profile and requirements["profile"] != product_profile:
            blockers.append(f"Buyer rule profile {requirements['profile']} does not match lot profile {product_profile}")
    product_rows = con.execute("SELECT id,code FROM products WHERE lot_id=? ORDER BY created_at", (lot_id,)).fetchall()
    for p in product_rows:
        inspection = con.execute("SELECT * FROM inspections WHERE product_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (p["id"],)).fetchone()
        if not inspection:
            blockers.append(f"Product {p['code']} has no completed inspection")
            continue
        if inspection["state"] != "completed":
            blockers.append(f"Product {p['code']} latest inspection is {inspection['state']}; complete or re-inspect it")
        if inspection["execution_mode"] == "mock" or lot["is_mock"]:
            blockers.append(f"Product {p['code']} has a development mock record; real dispatch is blocked")
        decision = con.execute("SELECT outcome FROM decisions WHERE inspection_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (inspection["id"],)).fetchone()
        if not decision or decision["outcome"] not in {"PASS", "GRADE"}:
            why = decision["outcome"] if decision else "no human decision"
            blockers.append(f"Product {p['code']} requires a human PASS or GRADE decision (current: {why})")
        raw = json.loads(inspection["ai_result"] or "null")
        if requirements and requirements["require_coverage"]:
            coverage = raw.get("coverage") if isinstance(raw, dict) else None
            if not isinstance(coverage, dict) or coverage.get("complete") is not True:
                blockers.append(f"Product {p['code']} has missing or incomplete mandatory inspection coverage")
        quality = raw.get("image_quality") if isinstance(raw, dict) else None
        if not isinstance(quality, dict) or quality.get("acceptable") is not True:
            blockers.append(f"Product {p['code']} has missing or unacceptable capture quality evidence")
    if requirements:
        required_measurements = json.loads(requirements["required_measurements_json"])
        present = {r["name"] for r in con.execute("SELECT DISTINCT name FROM measurements WHERE lot_id=?", (lot_id,))}
        for name in required_measurements:
            if name not in present:
                blockers.append(f"Required measurement '{name}' is missing")
        for report_type in json.loads(requirements["required_labs_json"]):
            accepted = con.execute("SELECT 1 FROM lab_reports WHERE lot_id=? AND report_type=? AND status='accepted' AND reviewed_by IS NOT NULL LIMIT 1", (lot_id, report_type)).fetchone()
            if not accepted:
                blockers.append(f"Required laboratory report '{report_type}' is missing or not reviewed as accepted")
    if summary_data["accepted_quantity"] < 1:
        blockers.append("No human-accepted products are available for dispatch")
    return {
        "lot_id": lot_id,
        "ready": not blockers,
        "registered_quantity": summary_data["product_count"],
        "expected_quantity": lot["expected_quantity"],
        "accepted_quantity": summary_data["accepted_quantity"],
        "rejected_quantity": summary_data["rejected_quantity"],
        "held_quantity": summary_data["held_quantity"],
        "pending_quantity": summary_data["pending_quantity"],
        "blockers": blockers,
        "corrective_actions": blockers,
        "scope_note": "Readiness checks configured buyer profile, required coverage, image quality, external measurements, accepted lab reports, latest completed inspection and latest human decision. Dispatch quantity is checked when an owner authorizes dispatch.",
    }


@app.get("/api/v1/lots/{lot_id}/export-gate")
def export_gate(lot_id: str, user: User):
    with closing(connect()) as con:
        return evaluate_export_gate(con, lot_id)


@app.post("/api/v1/lots/{lot_id}/authorize-dispatch")
def authorize_dispatch(lot_id: str, body: DispatchInput, user: User):
    if user["role"] != "owner":
        raise HTTPException(403, "Only an authorized owner can approve dispatch")
    with closing(connect()) as con:
        gate_result = evaluate_export_gate(con, lot_id)
        if not gate_result["ready"]:
            raise HTTPException(409, {"message": "Export Ready Gate is blocked", "blockers": gate_result["blockers"]})
        if body.quantity != gate_result["accepted_quantity"]:
            raise HTTPException(409, f"Dispatch quantity {body.quantity} must equal accepted quantity {gate_result['accepted_quantity']}")
        if con.execute("SELECT 1 FROM dispatches WHERE lot_id=?", (lot_id,)).fetchone():
            raise HTTPException(409, "A dispatch has already been authorized for this lot")
        dispatch_id = str(uuid.uuid4())
        con.execute("INSERT INTO dispatches VALUES(?,?,?,?,?)", (dispatch_id, lot_id, body.quantity, user["id"], now()))
        audit(con, user["id"], "dispatch.authorized", lot_id, {"dispatch_id": dispatch_id, "quantity": body.quantity})
        con.commit()
    return {"id": dispatch_id, "lot_id": lot_id, "quantity": body.quantity, "authorized_by": user["username"], "status": "authorized"}


@app.get("/api/v1/analytics/summary")
def summary(user: User):
    with closing(connect()) as con:
        return {"lots": con.execute("SELECT count(*) n FROM lots").fetchone()["n"], "products": con.execute("SELECT count(*) n FROM products").fetchone()["n"], "inspections": con.execute("SELECT count(*) n FROM inspections").fetchone()["n"], "pending_reviews": con.execute("SELECT count(*) n FROM inspections i WHERE i.id=(SELECT i2.id FROM inspections i2 WHERE i2.product_id=i.product_id ORDER BY i2.created_at DESC,i2.rowid DESC LIMIT 1) AND NOT EXISTS(SELECT 1 FROM decisions d WHERE d.inspection_id=i.id)").fetchone()["n"], "engine_mode": AI_MODE}


@app.get("/api/v1/analytics/quality")
def quality_analytics(user: User):
    with closing(connect()) as con:
        latest = "i.id=(SELECT i2.id FROM inspections i2 WHERE i2.product_id=i.product_id ORDER BY i2.created_at DESC,i2.rowid DESC LIMIT 1)"
        annotations = con.execute(f"SELECT d.label,d.status,p.id product_id,p.lot_id,l.supplier,l.machine FROM defects d JOIN inspections i ON i.id=d.inspection_id JOIN products p ON p.id=i.product_id JOIN lots l ON l.id=p.lot_id WHERE {latest} AND d.status!='false_positive'").fetchall()
        freq: dict[str, set[str]] = {}
        by_lot: dict[str, set[str]] = {}
        by_supplier: dict[str, set[str]] = {}
        by_machine: dict[str, set[str]] = {}
        for row in annotations:
            freq.setdefault(row["label"], set()).add(row["product_id"])
            by_lot.setdefault(row["lot_id"], set()).add(row["product_id"])
            if row["supplier"]:
                by_supplier.setdefault(row["supplier"], set()).add(row["product_id"])
            if row["machine"]:
                by_machine.setdefault(row["machine"], set()).add(row["product_id"])
        supplier_total = {r["supplier"]: r["count"] for r in con.execute("SELECT l.supplier,count(DISTINCT p.id) count FROM lots l JOIN products p ON p.lot_id=l.id WHERE trim(l.supplier)!='' GROUP BY l.supplier")}
        machine_total = {r["machine"]: r["count"] for r in con.execute("SELECT l.machine,count(DISTINCT p.id) count FROM lots l JOIN products p ON p.lot_id=l.id WHERE trim(l.machine)!='' GROUP BY l.machine")}
        supplier_rates = {key: {"products_with_recorded_defects": len(by_supplier.get(key,set())), "product_count": total, "rate": len(by_supplier.get(key,set()))/total if total else None} for key,total in supplier_total.items()}
        machine_rates = {key: {"products_with_recorded_defects": len(by_machine.get(key,set())), "product_count": total, "rate": len(by_machine.get(key,set()))/total if total else None} for key,total in machine_total.items()}
        lot_rates = []
        for row in con.execute("SELECT id,code FROM lots ORDER BY created_at"):
            total = con.execute("SELECT count(*) n FROM products WHERE lot_id=?", (row["id"],)).fetchone()["n"]
            found = len(by_lot.get(row["id"], set()))
            lot_rates.append({"lot_id": row["id"], "lot_code": row["code"], "products_with_recorded_defects": found, "product_count": total, "rate": found / total if total else None})
        decision_rows = con.execute("SELECT i.recommendation,d.outcome FROM decisions d JOIN inspections i ON i.id=d.inspection_id").fetchall()
        divergences = sum(1 for d in decision_rows if (d["recommendation"] == "no_defect_flagged" and d["outcome"] in {"REJECT", "HOLD"}) or (d["recommendation"] == "reject_recommended" and d["outcome"] in {"PASS", "GRADE"}))
        grades = con.execute("SELECT d.grade,count(*) count FROM decisions d WHERE d.outcome='GRADE' AND d.grade IS NOT NULL GROUP BY d.grade").fetchall()
        processing = []
        for row in con.execute(f"SELECT i.ai_result FROM inspections i WHERE {latest}"):
            raw=json.loads(row["ai_result"] or "null")
            if isinstance(raw,dict) and isinstance(raw.get("processing_time_ms"),(int,float)) and raw["processing_time_ms"]>=0:
                processing.append(float(raw["processing_time_ms"]))
        return {
            "defect_frequency_by_label": [{"label": k, "distinct_products": len(v)} for k, v in sorted(freq.items(), key=lambda x: (-len(x[1]), x[0]))],
            "repeated_defect_patterns": [{"label":k,"distinct_products":len(v)} for k,v in sorted(freq.items(),key=lambda x:(-len(x[1]),x[0])) if len(v)>1],
            "defect_rate_by_lot": lot_rates,
            "defect_rate_by_supplier": supplier_rates,
            "defect_rate_by_machine": machine_rates,
            "grade_distribution": {r["grade"]: r["count"] for r in grades},
            "inspection_processing_time_ms": {"sample_count":len(processing),"mean":statistics.mean(processing) if processing else None,"median":statistics.median(processing) if processing else None},
            "human_decisions": {"count": len(decision_rows), "recorded_divergences": divergences, "interpretation": "Decision divergence is an operational review signal, not an AI accuracy measurement."},
            "possible_source_note": "Supplier and machine groupings are associations in recorded data; they do not establish root cause.",
            "data_state": "measured_records" if annotations else "insufficient_data",
        }


@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse(FRONTEND / "index.html")
