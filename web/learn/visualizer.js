const trigger = document.querySelector('#open-visualizer');
const profile = document.querySelector('#profile-button');
const options = document.querySelector('#profile-options');
function closeProfileOptions() {
  options.hidden = true;
  profile.setAttribute('aria-expanded', 'false');
}
profile.onclick = () => {
  const opening = options.hidden;
  options.hidden = !opening;
  profile.setAttribute('aria-expanded', String(opening));
};
document.addEventListener('click', event => {
  if (!event.target.closest('.profile-dropdown')) closeProfileOptions();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !options.hidden) {
    closeProfileOptions();
    profile.focus();
  }
});
document.addEventListener('focusin', event => {
  if (!event.target.closest('.profile-dropdown')) closeProfileOptions();
});
window.addEventListener('hashchange', closeProfileOptions);
const dialog = document.createElement('dialog');
dialog.className = 'visualizer-dialog';
dialog.setAttribute('aria-labelledby', 'visualizer-title');
dialog.innerHTML = '<header><h2 id="visualizer-title">Visualizer · Nano signal simulation</h2><button type="button" autofocus>Close</button></header><iframe title="Single-cell CAD and simulated Nano signals"></iframe>';
document.body.append(dialog);
trigger.onclick = () => {
  closeProfileOptions();
  dialog.querySelector('iframe').src = '../servo-cell.html?visualizer';
  dialog.showModal();
};
dialog.querySelector('button').onclick = () => dialog.close();
dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
dialog.addEventListener('close', () => {
  dialog.querySelector('iframe').removeAttribute('src');
  profile.focus();
});
