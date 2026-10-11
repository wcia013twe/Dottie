import { reportCamera } from './device-status.js';
import { connectors } from './connectors.js';

let generation = 0, stream = null;
export function cleanupExplore() {
  generation++;
  stream?.getTracks().forEach(track => track.stop());
  stream = null;
  reportCamera('off');
}

export function exploreView() {
  return `<section class="panel explore-connections explore-preview" aria-label="Live camera">
    <iframe id="camera-preview" class="explore-camera-frame" src="camera-preview.html" title="Live camera preview" allow="camera"></iframe>
    <div class="explore-connection-row"><strong>Webcam</strong><span class="device-indicator" data-webcam-status data-state="off" role="status">Off</span><div class="choices"><button class="secondary" id="start-camera">Start camera</button><button class="secondary" id="stop-camera" disabled>Stop camera</button></div></div>
    <p id="camera-status" role="status">Allow camera access to see your live preview.</p>
    </section>`;
}

export function bindExplore(main) {
  const preview = main.querySelector('#camera-preview');
  let video;
  const previewReady = new Promise(resolve => {
    function loaded() {
      const camera = preview.contentDocument?.querySelector('#live-camera');
      if (!camera) return;
      video = camera; resolve();
    }
    preview.addEventListener('load', loaded, {once:true});
    loaded();
  });
  const status = main.querySelector('#camera-status');
  const start = main.querySelector('#start-camera');
  const stop = main.querySelector('#stop-camera');
  const active = id => id === generation && main.contains(preview);

  function reset() {
    cleanupExplore();
    if (video) video.srcObject = null;
    start.disabled = false;
    stop.disabled = true;
    status.textContent = 'Your camera is off.';
  }

  start.onclick = async () => {
    if (start.disabled) return;
    cleanupExplore();
    const id = generation;
    reportCamera('connecting');
    start.disabled = true; stop.disabled = false; status.textContent = 'Allow camera access when your browser asks.';
    try {
      const result = await connectors.camera.connect();
      if (!active(id)) { result.stream.getTracks().forEach(track => track.stop()); return; }
      stream = result.stream;
      await previewReady;
      if (!active(id)) return;
      video.srcObject = stream;
      await video.play();
      if (!active(id)) return;
      if (video.videoWidth && video.videoHeight) preview.style.aspectRatio = `${video.videoWidth} / ${video.videoHeight}`;
      stop.disabled = false;
      const track = stream.getVideoTracks()[0];
      reportCamera(track.muted ? 'muted' : 'live', track.label);
      track.addEventListener('mute', () => { if (active(id)) reportCamera('muted', track.label); });
      track.addEventListener('unmute', () => { if (active(id)) reportCamera('live', track.label); });
      status.textContent = 'Camera is live.';
      stream.getVideoTracks()[0].addEventListener('ended', () => { if (active(id)) reset(); });
    } catch (error) {
      if (!active(id)) return;
      reset();
      reportCamera(error.name === 'NotAllowedError' ? 'blocked' : 'unavailable');
      status.textContent = error.name === 'NotAllowedError' ? 'Camera access was blocked. Allow camera access in your browser, then try again.' : error.name === 'NotFoundError' ? 'No camera found. Connect a webcam and try again.' : error.name === 'NotReadableError' ? 'Camera unavailable. Close other apps using it and try again.' : 'Could not start the camera. Use a supported browser on localhost or HTTPS and try again.';
    }
  };
  stop.onclick = reset;
  // One request per Explore entry. Denial leaves an explicit Start camera retry.
  start.onclick();
}
