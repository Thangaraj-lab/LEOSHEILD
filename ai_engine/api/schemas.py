from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Profile = Literal["leather", "footwear", "auto_component"]
View = Literal["front", "back"]
Lighting = Literal["manual_diffuse", "manual_left", "manual_right", "unknown"]
Status = Literal["pending", "capturing", "analyzing", "awaiting_capture", "completed", "failed", "cancelled"]
Recommendation = Literal["no_defect_flagged", "review", "reject_recommended", "hold"]


class InspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    product_id: str = Field(min_length=1, max_length=128)
    lot_id: str = Field(min_length=1, max_length=128)
    profile: Profile


class StationInput(InspectionInput):
    source: Literal["station"]


class CaptureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    view: View
    lighting: Lighting
    captured_at: AwareDatetime | None = None


class LightingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["OFF", "ALL_WHITE", "TOP", "LEFT", "RIGHT", "FRONT", "BACK"]
    brightness: int = Field(default=0, ge=0, le=255)


class Box(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)


class Quality(BaseModel):
    acceptable: bool = False
    warnings: list[str] = Field(default_factory=list)
    width: int | None = None
    height: int | None = None
    sharpness: float | None = None
    dark_fraction: float | None = None
    glare_fraction: float | None = None


class Region(BaseModel):
    region_id: str
    view: View
    box: Box | None = None
    required_lighting: Lighting = "manual_diffuse"
    completed_lighting: Lighting | None = None
    quality: Quality | None = None
    state: Literal["NOT_INSPECTED", "INSUFFICIENT_QUALITY", "INSPECTED", "SUSPICIOUS"] = "NOT_INSPECTED"


class Coverage(BaseModel):
    required_regions: int
    inspected_regions: int
    complete: bool
    regions: list[Region]


class Candidate(BaseModel):
    evidence_id: UUID
    region_id: str
    kind: Literal["local_contrast_candidate"] = "local_contrast_candidate"
    box: Box


class Action(BaseModel):
    kind: Literal["capture_required_view", "recapture", "human_review"]
    reason: str
    view: View | None = None
    lighting: Lighting | None = None


class Evidence(BaseModel):
    capture_id: UUID
    view: View
    lighting: Lighting
    captured_at: datetime | None = None
    received_at: datetime
    sha256: str
    media_type: Literal["image/jpeg", "image/png"]
    image_url: str
    calibration_status: Literal["uncalibrated"] = "uncalibrated"
    quality: Quality
    processing_time_ms: float


class InspectionResult(InspectionInput):
    contract_version: Literal["1.0.0"] = "1.0.0"
    algorithm_version: Literal["0.1.0"] = "0.1.0"
    inspection_id: UUID
    execution_mode: Literal["real"] = "real"
    status: Status
    recommendation: Recommendation
    coverage: Coverage
    image_quality: Quality
    defects: list[Candidate]
    uncertain_regions: list[Candidate]
    lighting_modes_used: list[Lighting]
    actions: list[Action]
    action_history: list[Action]
    processing_time_ms: float
    capture_time_ms: float | None = None
    model_version: None = None
    warnings: list[str]
    evidence: list[Evidence]
    human_approval_required: Literal[True] = True


class Health(BaseModel):
    status: Literal["ok"]
    contract_version: Literal["1.0.0"]


class HardwareStatus(BaseModel):
    esp32_verified: bool
    station_camera_verified: bool
    external_lighting_verified: bool
    serial_ports_detected: int | None
    manual_upload_available: bool


class ProfileCapability(BaseModel):
    status: Literal["experimental", "unsupported", "validated"]
    required_views: list[View] | None = None


class Capabilities(BaseModel):
    contract_version: Literal["1.0.0"]
    profiles: dict[Profile, ProfileCapability]
    manual_upload: bool
    classical_candidates: bool
    trained_model: bool
    physical_measurements: bool
    station_acquisition: bool


class BenchmarkResult(BaseModel):
    measured_at: datetime
    dataset_id: str
    source: Literal["physical", "synthetic"]
    method: Literal["manual_diffuse_two_view"] = "manual_diffuse_two_view"
    algorithm_version: Literal["0.1.0"] = "0.1.0"
    pieces: int
    captures: int
    holds: int
    missed_critical_pieces: int
    piece_recall: float | None
    piece_precision: float | None
    piece_false_positive_rate: float | None
    required_view_coverage: float
    median_decode_and_analysis_ms: float
