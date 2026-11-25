import json
import logging
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from threading import Lock
from time import perf_counter
from uuid import uuid4

from ai_engine.acquisition.image_loader import decode_image
from ai_engine.api.schemas import Action, Candidate, Coverage, Evidence, InspectionResult, Quality, Region
from ai_engine.leo_eve.cross_light import compare
from ai_engine.leo_eve.policy import DIRECTIONAL_REQUEST, directional_action
from ai_engine.preprocessing.vision import analyze

JOB_WINDOW = timedelta(minutes=10)
LOG = logging.getLogger("uvicorn.error")


class ClosedInspection(ValueError):
    pass


class Engine:
    def __init__(self, store, rules, publish_status=None):
        self.store = store
        self.rules = rules
        self.write_lock = Lock()
        self.publish_status = publish_status

    def _announce(self, state):
        if self.publish_status is not None:
            self.publish_status(state)

    def start(self, request, capture, data, content_type):
        result = InspectionResult(
            **request.model_dump(), inspection_id=uuid4(), status="analyzing",
            recommendation="hold",
            coverage=Coverage(required_regions=len(self.rules.required_views),
                              inspected_regions=0, complete=False,
                              regions=[Region(view=view, region_id=view) for view in self.rules.required_views]),
            image_quality=Quality(), defects=[], uncertain_regions=[], lighting_modes_used=[],
            actions=[], action_history=[], processing_time_ms=0, evidence=[],
            warnings=["experimental_classical_vision", "manual_capture_metadata", "uncalibrated"],
        )
        with self.write_lock:
            return self._add_capture(result, capture, data, content_type)

    def get(self, inspection_id):
        with self.write_lock:
            return self._read_current(inspection_id)

    def add_capture(self, inspection_id, capture, data, content_type):
        with self.write_lock:
            result = self._read_current(inspection_id)
            if result.status != "awaiting_capture":
                raise ClosedInspection("Inspection is closed")
            return self._add_capture(result, capture, data, content_type)

    def finish(self, inspection_id):
        with self.write_lock:
            result = self._read_current(inspection_id)
            if result.status == "awaiting_capture":
                self._close_incomplete(result, "operator_ended_capture")
            return result

    def _read_current(self, inspection_id):
        result = self.store.read(inspection_id)
        if (result.status == "awaiting_capture"
                and datetime.now(UTC) >= result.evidence[0].received_at + JOB_WINDOW):
            self._close_incomplete(result, "capture_window_expired")
        return result

    def _close_incomplete(self, result, reason):
        result.status = "completed"
        if result.coverage.complete:
            result.recommendation = "review"
            result.warnings.append("directional_evidence_unresolved")
        result.warnings.append(reason)
        result.action_history.extend(result.actions)
        result.actions = [Action(kind="human_review", reason=reason)]
        self.store.write(result)
        self._announce("COMPLETED")

    def _add_capture(self, result, capture, data, content_type):
        start = perf_counter()
        received_at = datetime.now(UTC)
        region = next((region for region in result.coverage.regions if region.view == capture.view), None)
        if region is None:
            raise ValueError("View is outside the profile")
        pending = result.actions[0] if result.actions else None
        directional = pending is not None and pending.reason == DIRECTIONAL_REQUEST
        if directional and (capture.view != pending.view or capture.lighting != pending.lighting):
            raise ClosedInspection("Submit the requested view under the requested manual lighting")
        if not directional and region.completed_lighting is not None:
            raise ClosedInspection("This view already satisfied the mandatory check")
        digest = sha256(data).hexdigest()
        if any(item.sha256 == digest for item in result.evidence):
            raise ClosedInspection("This image is already recorded for the inspection")
        self._announce("ANALYZING")
        mask = BytesIO()
        try:
            image, media_type, orientation = decode_image(data, content_type)
            quality, box, candidates = analyze(image, orientation, self.rules, save_mask=lambda image: image.save(mask, "PNG"))
        except (OSError, ValueError):
            self._announce("ERROR")
            raise
        capture_id = uuid4()
        assessment = None
        if directional and quality.acceptable:
            assessment = self._compare_directional(result, region, image, orientation, box, candidates)
        elapsed = round((perf_counter() - start) * 1000, 3)
        evidence = Evidence(
            capture_id=capture_id, view=capture.view, lighting=capture.lighting,
            captured_at=capture.captured_at, received_at=received_at, sha256=digest,
            media_type=media_type, quality=quality, processing_time_ms=elapsed,
            camera_source=capture.camera_source, algorithm_version="0.2.0",
            image_url=f"/inspections/{result.inspection_id}/evidence/{capture_id}/image",
        )
        result.action_history.extend(result.actions)
        result.evidence.append(evidence)
        result.algorithm_version = evidence.algorithm_version
        result.processing_time_ms = round(result.processing_time_ms + elapsed, 3)
        if capture.lighting not in result.lighting_modes_used:
            result.lighting_modes_used.append(capture.lighting)
        if not directional:
            region.box = box
            region.quality = quality
            if quality.acceptable and capture.lighting == region.required_lighting:
                region.completed_lighting = capture.lighting
                region.state = "SUSPICIOUS" if candidates else "INSPECTED"
            else:
                region.state = "INSUFFICIENT_QUALITY"
        result.uncertain_regions.extend(Candidate(evidence_id=capture_id, region_id=region.region_id, box=item)
                                        for item in candidates)
        if directional:
            self._resolve_directional(result, pending, quality, assessment)
        else:
            self._schedule(result, quality)
        self.store.write(result, evidence, data, mask.getvalue() or None)
        self._announce("AWAITING_CAPTURE" if result.status == "awaiting_capture" else "COMPLETED")
        LOG.info("%s", json.dumps({
            "event": "capture_processed", "inspection_id": str(result.inspection_id),
            "capture_id": str(capture_id), "status": result.status, "recommendation": result.recommendation,
            "inspected_regions": result.coverage.inspected_regions, "processing_time_ms": elapsed,
        }))
        return result

    def _compare_directional(self, result, region, image, orientation, box, candidates):
        baseline = next(item for item in reversed(result.evidence)
                        if item.view == region.view and item.lighting == region.required_lighting and item.quality.acceptable)
        path = self.store.image_path(result.inspection_id, baseline.capture_id)
        try:
            previous, _, previous_orientation = decode_image(path.read_bytes(), baseline.media_type)
        except (OSError, ValueError):
            return None
        boxes = [candidate.box for candidate in result.uncertain_regions if candidate.evidence_id == baseline.capture_id]
        matches = compare(previous, previous_orientation, region.box, boxes, image, orientation, box, candidates)
        return None if matches is None else (len(matches), len(boxes))

    def _resolve_directional(self, result, action, quality, assessment):
        if not quality.acceptable:
            result.warnings.append("directional_capture_quality_insufficient")
        elif assessment is None:
            result.warnings.append("cross_light_registration_unverified")
        else:
            matched, total = assessment
            if matched:
                result.warnings.append("cross_light_persistent_candidates")
            if matched < total:
                result.warnings.append("cross_light_unmatched_baseline_candidates")
        if assessment is None and len(result.evidence) < self.rules.maximum_capture_attempts:
            result.actions = [action]
        else:
            if assessment is None:
                result.warnings.append("directional_evidence_unresolved")
            result.status = "completed"
            result.recommendation = "review"
            result.actions = [Action(kind="human_review", reason="review")]

    def _schedule(self, result, latest_quality):
        missing = [region for region in result.coverage.regions if region.completed_lighting is None]
        result.coverage.inspected_regions = result.coverage.required_regions - len(missing)
        result.coverage.complete = not missing
        warnings = list(dict.fromkeys(
            warning for region in result.coverage.regions if region.quality is not None
            for warning in region.quality.warnings
        ))
        if missing:
            warnings.append("mandatory_coverage_incomplete")
        result.image_quality = latest_quality.model_copy(
            update={"acceptable": not missing, "warnings": warnings}
        )
        if not missing:
            extra = directional_action(result, self.rules)
            if extra is not None:
                result.status = "awaiting_capture"
                result.recommendation = "hold"
                result.actions = [extra]
                return
            result.status = "completed"
            result.recommendation = "review" if result.uncertain_regions else "no_defect_flagged"
            result.actions = [Action(kind="human_review", reason=result.recommendation)]
        elif len(result.evidence) >= self.rules.maximum_capture_attempts:
            result.status = "completed"
            result.warnings.append("capture_budget_exhausted")
            result.actions = [Action(kind="human_review", reason="mandatory_coverage_incomplete")]
        else:
            result.status = "awaiting_capture"
            target = missing[0]
            retry = target.quality is not None
            reason = "required_view_missing"
            if retry:
                reason = "baseline_lighting_required" if target.quality.acceptable else "capture_quality_insufficient"
            result.actions = [Action(kind="recapture" if retry else "capture_required_view",
                                     view=target.view, lighting=target.required_lighting, reason=reason)]
