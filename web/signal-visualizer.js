// Local demonstration of the harness DOTS/CLEAR protocol. No hardware transport.
const masks = [1,3,9,25,17,11,27,19,10,26,5,7,13,29,21,15,31,23,14,30,37,39,58,45,61,53];
export function mountSignalVisualizer() {
  document.body.classList.add('signal-visualizer');
  const css = document.createElement('link');
  css.rel = 'stylesheet'; css.href = 'signal-visualizer.css'; document.head.append(css);
  document.querySelector('#appHeader').hidden = true;
  const aside = document.querySelector('aside');
  [...aside.children].forEach(el => el.hidden = true);
  const panel = document.createElement('section');
  panel.className = 'signal-panel';
  panel.innerHTML = `<span class="sim-tag">SIMULATION</span><h1>One cell. Six signals.</h1><p>Follow a word through the Nano to the six servo channels.</p><form id="signal-form"><label for="signal-word">Word or letter</label><input id="signal-word" value="hello" maxlength="24" pattern="[A-Za-z ]+" required autocomplete="off"><div class="signal-actions"><button id="signal-send">Send to Nano</button><button id="signal-stop" type="button" disabled>Stop & clear</button></div></form><div class="signal-flow" aria-label="Signal path"><span data-stage="browser">App</span><b>→</b><span data-stage="nano">Nano</span><b>→</b><span data-stage="cell">Cell</span></div><p id="signal-status" role="status">Ready to simulate.</p><div class="signal-dots">${[1,4,2,5,3,6].map(n => `<span data-dot="${n}">${n}</span>`).join('')}</div><pre id="signal-log" aria-label="Simulated signal log"></pre><p class="signal-note">Local simulation · no commands are sent to hardware. Uses the harness’s DOTS / CLEAR commands and firmware CELL responses. CAD motion is illustrative; reset is shown mechanically.</p>`;
  aside.append(panel);
  document.querySelector('#status').textContent = 'Single-cell CAD · simulated signals';
  document.querySelector('.trackButton').hidden = true;
  const $ = id => document.getElementById(id);
  const log = line => { $('signal-log').textContent = ($('signal-log').textContent + line + '\n').split('\n').slice(-32).join('\n'); $('signal-log').scrollTop = $('signal-log').scrollHeight; };
  const stage = name => panel.querySelectorAll('[data-stage]').forEach(el => el.classList.toggle('active', el.dataset.stage === name));
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const idle = async () => { while (window.servoCellState().busy) await sleep(40); };
  let running = false, stopped = false;
  async function clear() {
    stage('nano'); log('Nano → serial: CLEAR');
    await idle(); $('reset').click(); await idle();
    panel.querySelectorAll('[data-dot]').forEach(el => el.classList.remove('raised'));
    log('Cell → Nano: CELL 00 - [simulated]');
  }
  $('signal-stop').onclick = () => { stopped = true; $('signal-stop').disabled = true; $('signal-status').textContent = 'Stopping and clearing the cell…'; };
  $('signal-form').onsubmit = async event => {
    event.preventDefault(); if (running) return;
    const text = $('signal-word').value.trim().toLowerCase();
    if (!/^[a-z ]{1,24}$/.test(text)) { $('signal-status').textContent = 'Enter 1–24 letters or spaces.'; return; }
    running = true; stopped = false; $('signal-send').disabled = true; $('signal-word').disabled = true; $('signal-stop').disabled = false;
    $('signal-log').textContent = ''; stage('browser'); log(`App → Nano: hold each letter of "${text}" [simulated]`);
    await sleep(400);
    for (const char of text) {
      if (stopped) break;
      await clear(); if (stopped) break;
      const mask = char === ' ' ? 0 : masks[char.charCodeAt(0) - 97];
      if (!mask) { $('signal-status').textContent = 'Word gap · blank cell'; await sleep(600); continue; }
      const dots = [1,2,3,4,5,6].filter(n => mask & (1 << (n - 1)));
      stage('nano'); $('signal-status').textContent = `Nano received ${char.toUpperCase()} · dots ${dots.join(', ')}`;
      log(`Nano → serial: DOTS ${dots.join(' ')}`); await sleep(350); if (stopped) break;
      stage('cell');
      window.servoCellState().selected.forEach((value, i) => { if (value !== dots.includes(i + 1)) $('dot-' + i).click(); });
      $('write').click(); await idle();
      dots.forEach(n => panel.querySelector(`[data-dot="${n}"]`).classList.add('raised'));
      const hex = mask.toString(16).toUpperCase().padStart(2, '0');
      log(`Cell → Nano: CELL ${hex} - [simulated]`);
      $('signal-status').textContent = `Simulated acknowledgement · ${char.toUpperCase()} held`;
      await sleep(1100);
    }
    await clear(); stage('browser');
    $('signal-status').textContent = stopped ? 'Stopped · cell cleared.' : 'Word complete · cell cleared.';
    running = false; $('signal-send').disabled = false; $('signal-word').disabled = false; $('signal-stop').disabled = true;
  };
}
