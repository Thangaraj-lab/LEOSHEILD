"""Choose a manual follow-up from the evidence and remaining capture budget."""

from ai_engine.api.schemas import Action

DIRECTIONAL_REQUEST = "directional_evidence_requested"


def directional_action(result, rules):
    if len(result.evidence) >= rules.maximum_capture_attempts:
        return None
    for region in result.coverage.regions:
        baseline = next(item for item in reversed(result.evidence)
                        if item.view == region.view and item.lighting == region.required_lighting
                        and item.quality.acceptable)
        candidates = [item for item in result.uncertain_regions if item.evidence_id == baseline.capture_id]
        if 0 < len(candidates) <= rules.maximum_directional_candidates:
            return Action(
                kind="recapture", reason=DIRECTIONAL_REQUEST, view=region.view, lighting="manual_right",
                target_box=candidates[0].box,
                instruction="Switch off the white light before moving it to the right. Keep the phone and sample "
                            "fixed. Turn the light on, then capture and submit this side as Right directional.",
            )
    return None
