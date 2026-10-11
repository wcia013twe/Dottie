/** Actual browser camera state and a bounded read-only Jetson identity check. */
let camera = {state:'off', name:''};
let nano = {state:'unknown', message:'Nano not checked.'};
const cameraNames = {off:'Off', connecting:'Starting', live:'Live', muted:'Paused', blocked:'Blocked', unavailable:'Unavailable'};
const nanoNames = {not_configured:'Not configured', connected:'SSH connected', unverified:'Unverified', invalid:'Invalid address', wrong_device:'Different device', unknown:'Unchecked', checking:'Checking'};
export function syncDeviceStatus() {
  document.querySelectorAll('#webcam-connection, [data-webcam-status]').forEach(value => {
    value.textContent = cameraNames[camera.state] || 'Unknown';
    value.dataset.state = camera.state;
    value.title = camera.name || 'Webcam state in this app';
  });
  document.querySelectorAll('#nano-connection, [data-nano-status]').forEach(value => {
    value.textContent = nanoNames[nano.state] || 'Unchecked';
    value.dataset.state = nano.state; value.title = nano.message;
  });
}
export function reportCamera(state, name='') {
  camera = {state, name};
  syncDeviceStatus();
  window.dispatchEvent(new CustomEvent('magneto-camera-status', {detail:camera}));
}

export function mountDeviceStatus() {
  const panel = document.querySelector('#device-status');
  const detail = panel?.querySelector('#device-status-detail');
  const check = panel?.querySelector('#check-devices');
  const updateCamera = syncDeviceStatus;
  updateCamera();
  let busy = false;
  async function refresh() {
    if (busy) return;
    busy = true; if (check) check.disabled = true;
    nano = {state:'checking', message:'Checking Nano connection.'}; syncDeviceStatus();
    try {
      const response = await fetch('/api/nano-status', {cache:'no-store', signal:AbortSignal.timeout(7000)});
      if (!response.ok) throw new Error();
      const result = await response.json();
      if (!nanoNames[result.state]) throw new Error();
      nano = result; syncDeviceStatus();
      if (detail) detail.textContent = result.message;
    } catch {
      nano = {state:'unknown', message:'Nano check unavailable.'}; syncDeviceStatus();
      if (detail) detail.textContent = 'Nano check unavailable. Use the updated local server.';
    } finally {
      updateCamera(); busy = false; if (check) check.disabled = false;
    }
  }
  if (check) check.onclick = refresh;
  window.addEventListener('magneto-check-devices', refresh);
  refresh();
  const timer = setInterval(() => {if (!document.hidden) refresh();}, 30000);
  window.addEventListener('pagehide', () => clearInterval(timer), {once:true});
}
