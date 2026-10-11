import { reportCamera, syncDeviceStatus } from './device-status.js';
import { connectors } from './connectors.js';

let generation = 0, stream = null, timer = null, pending = null;
export function cleanupExplore() {
  generation++;
  clearTimeout(timer);
  pending?.abort();
  pending = null;
  stream?.getTracks().forEach(track => track.stop());
  stream = null;
  reportCamera('off');
}

export function exploreView() {
  return `<section class="panel explore-connections" aria-label="Connection checks"><h2>Connections</h2>
    <div class="explore-connection-row"><strong>Webcam</strong><span class="device-indicator" data-webcam-status data-state="off" role="status">Off</span><div class="choices"><button class="secondary" id="start-camera">Start camera</button><button class="secondary" id="stop-camera" disabled>Stop camera</button></div></div>
    <div class="explore-connection-row"><strong>Jetson Nano</strong><span class="device-indicator" data-nano-status data-state="unknown" role="status">Unchecked</span><button class="secondary" id="check-nano">Check connection</button></div>
    <video id="live-camera" autoplay muted playsinline hidden aria-hidden="true"></video><canvas id="camera-boxes" hidden aria-hidden="true"></canvas><p id="camera-status" class="sr-only" role="status">Your camera is off.</p>
    </section><section class="panel"><h2>What can you find?</h2><p id="detection-status" role="status">Start the camera to look for objects.</p><button class="secondary" id="retry-recognition" hidden>Try recognition again</button><div id="camera-objects" class="choices" aria-label="Detected objects"></div><div id="camera-discovery" aria-live="polite"></div></section>`;
}

export function bindExplore(main, speak) {
  syncDeviceStatus();
  main.querySelector('#check-nano').onclick = () => window.dispatchEvent(new Event('magneto-check-devices'));
  const video = main.querySelector('#live-camera');
  const overlay = main.querySelector('#camera-boxes');
  const status = main.querySelector('#camera-status');
  const detectionStatus = main.querySelector('#detection-status');
  const objects = main.querySelector('#camera-objects');
  const discovery = main.querySelector('#camera-discovery');
  const start = main.querySelector('#start-camera');
  const stop = main.querySelector('#stop-camera');
  const retry = main.querySelector('#retry-recognition');
  let lastLabels = '', selected = '';
  const active = id => id === generation && main.contains(video);

  function reset() {
    cleanupExplore();
    video.srcObject = null;
    start.disabled = false;
    stop.disabled = true;
    retry.hidden = true;
    overlay.getContext('2d').clearRect(0, 0, overlay.width, overlay.height);
    objects.replaceChildren();
    discovery.replaceChildren();
    lastLabels = selected = '';
    status.textContent = 'Your camera is off.';
    detectionStatus.textContent = 'Start the camera to look for objects.';
  }

  function choose(item) {
    selected = item.label;
    discovery.replaceChildren();
    const heading = document.createElement('h3');
    heading.textContent = `Let’s explore ${item.label.toLowerCase()}`;
    const text = document.createElement('p');
    text.textContent = 'The camera suggested this object. Check it together, then feel the real object or a tactile model.';
    const braille = document.createElement('div');
    braille.className = 'braille-word';
    const masks = {a:1,b:3,c:9,d:25,e:17,f:11,g:27,h:19,i:10,j:26,k:5,l:7,m:13,n:29,o:21,p:15,q:31,r:23,s:14,t:30,u:37,v:39,w:58,x:45,y:61,z:53};
    for (const letter of item.braille) {
      const tile = document.createElement('div');
      tile.className = 'braille-letter';
      const dots = document.createElement('span');
      dots.className = 'explore-braille';
      dots.textContent = String.fromCodePoint(0x2800 + (masks[letter] || 0));
      dots.setAttribute('aria-label', letter === ' ' ? 'Space' : `Braille ${letter}`);
      const caption = document.createElement('span');
      caption.className = 'caption'; caption.textContent = letter;
      tile.append(dots, caption); braille.append(tile);
    }
    const hint = document.createElement('p');
    hint.className = 'hint'; hint.textContent = 'Uncontracted English Braille · On-screen spelling · Physical Braille device not connected.';
    discovery.append(heading, text, braille, hint);
    objects.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.label === selected)));
    speak(`${item.label}. Its Braille spelling is shown on screen.`, true);
  }

  async function scan(id) {
    if (!active(id) || !stream) return;
    if (!video.videoWidth || video.readyState < 2) { timer = setTimeout(() => scan(id), 300); return; }
    const snapshot = document.createElement('canvas');
    const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
    snapshot.width = Math.round(video.videoWidth * scale);
    snapshot.height = Math.round(video.videoHeight * scale);
    snapshot.getContext('2d').drawImage(video, 0, 0, snapshot.width, snapshot.height);
    const controller = new AbortController(); pending = controller;
    try {
      const result = await connectors.camera.observe(snapshot.toDataURL('image/jpeg', .8).split(',')[1], controller.signal);
      if (!active(id)) return;
      retry.hidden = true;
      status.textContent = 'Camera is live. Looking for objects.';
      const items = result.detections;
      detectionStatus.textContent = items.length ? 'Possible objects below. Choose one to hear its name and discover its Braille.' : 'No object found yet. Try moving closer or improving the light.';
      const unique = [...new Map(items.map(item => [item.label, item])).values()];
      const key = JSON.stringify(unique.map(item => [item.label, item.braille]));
      if (key !== lastLabels) {
        lastLabels = key;
        const existing = new Map([...objects.querySelectorAll('button')].map(button => [button.dataset.label, button]));
        const labels = new Set(unique.map(item => item.label));
        for (const [label, button] of existing) if (!labels.has(label)) button.remove();
        for (const item of unique) {
          let button = existing.get(item.label);
          if (!button) {
            button = document.createElement('button');
            button.className = 'secondary'; button.dataset.label = item.label;
            button.textContent = item.label; objects.append(button);
          }
          button.setAttribute('aria-pressed', String(selected === item.label));
          button.onclick = () => choose(item);
        }
      }
      overlay.width = result.width; overlay.height = result.height;
      const ctx = overlay.getContext('2d');
      ctx.strokeStyle = '#f3cd61'; ctx.lineWidth = 3;
      ctx.font = '16px sans-serif';
      for (const item of items) {
        const [x1,y1,x2,y2] = item.box;
        ctx.strokeRect(x1,y1,x2-x1,y2-y1);
        ctx.fillStyle = '#184f47'; ctx.fillRect(x1, Math.max(0,y1-24), ctx.measureText(item.label).width+12, 24);
        ctx.fillStyle = '#fff'; ctx.fillText(item.label, x1+6, Math.max(18,y1-6));
      }
      timer = setTimeout(() => scan(id), 1500);
    } catch (error) {
      if (!active(id) || error.name === 'AbortError') return;
      status.textContent = 'Camera is live. Recognition is paused.';
      detectionStatus.textContent = error.message;
      objects.replaceChildren(); lastLabels = '';
      overlay.getContext('2d').clearRect(0,0,overlay.width,overlay.height);
      retry.hidden = false;
    } finally {
      if (pending === controller) pending = null;
    }
  }

  start.onclick = async () => {
    cleanupExplore();
    const id = generation;
    reportCamera('connecting');
    start.disabled = true; status.textContent = 'Connecting to your camera…';
    try {
      const result = await connectors.camera.connect();
      if (!active(id)) { result.stream.getTracks().forEach(track => track.stop()); return; }
      stream = result.stream; video.srcObject = stream;
      await video.play();
      if (!active(id)) return;
      stop.disabled = false;
      const track = stream.getVideoTracks()[0];
      reportCamera(track.muted ? 'muted' : 'live', track.label);
      track.addEventListener('mute', () => { if (active(id)) reportCamera('muted', track.label); });
      track.addEventListener('unmute', () => { if (active(id)) reportCamera('live', track.label); });
      status.textContent = 'Camera is live. Starting object recognition…';
      detectionStatus.textContent = 'Looking for objects. First recognition can take a moment.';
      stream.getVideoTracks()[0].addEventListener('ended', () => { if (active(id)) reset(); });
      scan(id);
    } catch (error) {
      if (!active(id)) return;
      reset();
      reportCamera(error.name === 'NotAllowedError' ? 'blocked' : 'unavailable');
      status.textContent = error.name === 'NotAllowedError' ? 'Camera access was blocked. Allow camera access in your browser, then try again.' : error.name === 'NotFoundError' ? 'No camera found. Connect a webcam and try again.' : error.name === 'NotReadableError' ? 'Camera unavailable. Close other apps using it and try again.' : 'Could not start the camera. Use a supported browser on localhost or HTTPS and try again.';
    }
  };
  stop.onclick = reset;
  retry.onclick = () => { retry.hidden = true; detectionStatus.textContent = 'Looking for objects…'; scan(generation); };
}
