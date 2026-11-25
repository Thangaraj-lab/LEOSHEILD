"use strict";

const element = id => document.getElementById(id);
const form = element("setup");
const product = element("product");
const lot = element("lot");
const token = element("token");
const lighting = element("lighting");
const automatic = element("automatic");
const stopCamera = element("stop-camera");
const nativeCamera = element("native");
const choose = element("choose");
const preview = element("preview");
const heading = element("next");
const status = element("status");
const restart = element("restart");

let inspection = null;
let view = "front";
let busy = false;
let cameraController = null;

const reasonText = {
  required_view_missing: "Capture the requested side.",
  capture_quality_insufficient: "Retake this side with the whole item in frame and even light.",
  baseline_lighting_required: "Use diffuse, even lighting for the requested view.",
  directional_evidence_requested: "Switch off the white light before moving it to the right. Leave the camera and item in place. Turn the light on, select Right directional, then capture again.",
};

function renderControls() {
  const ended = inspection !== null && inspection.status !== "awaiting_capture";
  automatic.hidden = !window.isSecureContext || !navigator.mediaDevices?.getUserMedia;
  for (const control of [automatic, nativeCamera, choose, lighting, token, restart]) {
    control.disabled = busy || (ended && control !== restart);
  }
  product.disabled = busy || inspection !== null;
  lot.disabled = busy || inspection !== null;
  restart.hidden = !ended;
  stopCamera.hidden = cameraController === null;
}

function validSetup() {
  if (inspection === null && (!product.value.trim() || !lot.value.trim())) {
    status.textContent = "Enter a product ID and lot ID first.";
    form.reportValidity();
    return false;
  }
  return true;
}

function authHeaders() {
  const secret = token.value.trim();
  return secret ? { Authorization: `Bearer ${secret}` } : {};
}

async function submitImage(file, capturedAt) {
  if (!["image/jpeg", "image/png"].includes(file.type)) {
    throw new Error("Choose a JPEG or PNG photo.");
  }
  if (file.size > 10 * 1024 * 1024) {
    throw new Error("Choose an image under 10 MiB, or use the automatic camera.");
  }
  const data = new FormData();
  data.set("view", view);
  data.set("lighting", lighting.value);
  data.set("image", file);
  data.set("camera_source", capturedAt ? "phone_live" : "phone_file");
  if (capturedAt) data.set("captured_at", capturedAt);
  const path = inspection ? `/inspections/${inspection.inspection_id}/captures` : "/inspect";
  if (!inspection) {
    data.set("product_id", product.value.trim());
    data.set("lot_id", lot.value.trim());
    data.set("profile", "leather");
  }
  status.textContent = "Uploading and inspecting…";
  const response = await fetch(path, { method: "POST", headers: authHeaders(), body: data, cache: "no-store" });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : `Upload failed (HTTP ${response.status}).`);
  }
  inspection = await response.json();
  const action = inspection.actions[0];
  const coverage = `${inspection.coverage.inspected_regions}/${inspection.coverage.required_regions} views accepted.`;
  if (inspection.status === "awaiting_capture") {
    view = action.view;
    heading.textContent = `${action.kind === "recapture" ? "Retake" : "Capture"} ${view} view`;
    status.textContent = `${coverage} ${action.instruction || reasonText[action.reason] || "Follow the requested view."}`;
  } else {
    heading.textContent = inspection.recommendation.replaceAll("_", " ").toUpperCase();
    status.textContent = `${coverage} Human approval is required. Inspection ID: ${inspection.inspection_id}`;
  }
}

async function run(operation) {
  if (busy || !validSetup()) return;
  busy = true;
  renderControls();
  try {
    await operation();
  } catch (error) {
    status.textContent = error.name === "AbortError" ? "Camera stopped." : error.message || "Capture failed. Try again.";
  } finally {
    busy = false;
    renderControls();
  }
}

for (const [button, input] of [[nativeCamera, element("camera-file")], [choose, element("image-file")]]) {
  button.addEventListener("click", () => { if (validSetup()) input.click(); });
  input.addEventListener("change", () => {
    const file = input.files[0];
    input.value = "";
    if (file) run(() => submitImage(file));
  });
}

function steady(previous, current) {
  return previous && current && ["x", "y", "width", "height"].every(
    key => Math.abs(previous[key] - current[key]) <= 0.035
  );
}

async function findPhoto(signal) {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 } },
    });
    signal.throwIfAborted();
    preview.srcObject = stream;
    preview.hidden = false;
    await preview.play();
    if (!preview.videoWidth || !preview.videoHeight) throw new Error("Camera frame unavailable.");
    const canvas = document.createElement("canvas");
    const scale = Math.min(1, 1600 / Math.max(preview.videoWidth, preview.videoHeight));
    canvas.width = Math.round(preview.videoWidth * scale);
    canvas.height = Math.round(preview.videoHeight * scale);
    const context = canvas.getContext("2d");
    let previous = null;
    while (!signal.aborted) {
      context.drawImage(preview, 0, 0, canvas.width, canvas.height);
      const capturedAt = new Date().toISOString();
      const frame = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.92));
      if (!frame) throw new Error("Unable to create a JPEG from the camera frame.");
      const file = new File([frame], `${view}.jpg`, { type: "image/jpeg" });
      const data = new FormData();
      data.set("image", file);
      data.set("view", view);
      data.set("lighting", lighting.value);
      const response = await fetch("/mobile-frame", {
        method: "POST", headers: authHeaders(), body: data, cache: "no-store", signal,
      });
      if (!response.ok) throw new Error(response.status === 401 ? "Check the local access token." : "Unable to check the camera frame.");
      const result = await response.json();
      if (result.state === "ready" && steady(previous, result.box)) return { file, capturedAt };
      previous = result.state === "ready" ? result.box : null;
      status.textContent = {
        empty: "Place object",
        adjust: "Keep the whole object in frame on a plain background with even light.",
        ready: "Hold still…",
      }[result.state];
      await new Promise(resolve => setTimeout(resolve, 850));
    }
    signal.throwIfAborted();
  } finally {
    stream?.getTracks().forEach(track => track.stop());
    preview.srcObject = null;
    preview.hidden = true;
  }
}

automatic.addEventListener("click", () => run(async () => {
  cameraController = new AbortController();
  renderControls();
  status.textContent = "Looking for an object…";
  try {
    const { file, capturedAt } = await findPhoto(cameraController.signal);
    cameraController.signal.throwIfAborted();
    stopCamera.hidden = true;
    await submitImage(file, capturedAt);
  } finally {
    cameraController = null;
  }
}));
stopCamera.addEventListener("click", () => cameraController?.abort());

restart.addEventListener("click", () => {
  inspection = null;
  view = "front";
  heading.textContent = "Front view";
  status.textContent = "Ready for a new front photo.";
  renderControls();
});
form.addEventListener("submit", event => event.preventDefault());
renderControls();
