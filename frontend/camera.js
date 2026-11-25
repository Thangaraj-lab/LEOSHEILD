let activeCamera = null;

function cameraMarkup() {
  return `<div class="camera-panel">
    <video class="camera-preview hidden" autoplay muted playsinline aria-label="Live product camera preview"></video>
    <div class="camera-controls">
      <button type="button" class="secondary" data-camera-open>Open local camera</button>
      <button type="button" class="primary hidden" data-camera-capture disabled>Capture photo</button>
      <button type="button" class="quiet hidden" data-camera-stop>Close camera</button>
    </div>
    <p class="detail-line" role="status" data-camera-status>Use a camera connected to this device, or choose a photo file.</p>
  </div>`;
}

function stopCamera() {
  activeCamera?.close();
}

function bindCamera(form) {
  if (!form) return;
  const video = form.querySelector('video');
  const open = form.querySelector('[data-camera-open]');
  const capture = form.querySelector('[data-camera-capture]');
  const stop = form.querySelector('[data-camera-stop]');
  const status = form.querySelector('[data-camera-status]');
  const input = form.querySelector('input[type=file]');

  open.onclick = async () => {
    stopCamera();
    if (!navigator.mediaDevices?.getUserMedia) {
      status.textContent = 'Camera access needs localhost or HTTPS and a supported browser. You can choose a photo file.';
      return;
    }
    const session = {
      stream: null,
      close() {
        session.stream?.getTracks().forEach(track => track.stop());
        video.srcObject = null;
        video.classList.add('hidden');
        capture.classList.add('hidden');
        stop.classList.add('hidden');
        open.disabled = false;
        if (activeCamera === session) activeCamera = null;
      },
    };
    activeCamera = session;
    open.disabled = true;
    stop.classList.remove('hidden');
    stop.onclick = () => {
      session.close();
      status.textContent = 'Camera closed.';
    };
    status.textContent = 'Waiting for camera access…';
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false,
      });
      if (activeCamera !== session || !form.isConnected) {
        stream.getTracks().forEach(track => track.stop());
        if (activeCamera === session) session.close();
        return;
      }
      session.stream = stream;
      stream.getVideoTracks()[0]?.addEventListener('ended', () => {
        if (activeCamera !== session) return;
        session.close();
        status.textContent = 'Camera disconnected. Reopen it or choose a photo file.';
      });
      video.srcObject = stream;
      video.classList.remove('hidden');
      await video.play();
      if (activeCamera !== session) return;
      capture.classList.remove('hidden');
      capture.disabled = false;
      status.textContent = 'Position the product in the live preview, then capture a photo.';
    } catch (error) {
      if (activeCamera !== session) return;
      session.close();
      status.textContent = error.name === 'NotAllowedError'
        ? 'Camera access was denied. Allow camera access in your browser or choose a photo file.'
        : 'The camera could not start. Check the connection or choose a photo file.';
    }
  };

  capture.onclick = async () => {
    const session = activeCamera;
    if (video.readyState < 2 || !video.videoWidth || !video.videoHeight) {
      status.textContent = 'The camera is starting. Wait for the preview and try again.';
      return;
    }
    capture.disabled = true;
    try {
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0);
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.92));
      if (activeCamera !== session || !form.isConnected) return;
      if (!blob) throw new Error('Camera frame encoding failed');
      const transfer = new DataTransfer();
      transfer.items.add(new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' }));
      input.files = transfer.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    } catch {
      status.textContent = 'The photo could not be captured. Try again or choose a photo file.';
    } finally {
      capture.disabled = false;
    }
  };

  input.addEventListener('change', () => {
    if (!input.files.length) return;
    stopCamera();
    status.textContent = 'Photo ready. Reopen the camera to retake it, or choose a different file.';
  });
}

window.addEventListener('pagehide', stopCamera);
