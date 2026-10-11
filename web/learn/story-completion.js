// Learner-facing celebrations use recorded interactions, never model proposals or transcripts.
export function completionRecap(observations = []) {
  const seen = new Set();
  const confirmed = observations.filter(event => {
    if (!event || typeof event.id !== 'string' || seen.has(event.id) || event.source !== 'teacher' ||
        !['introduce', 'identify', 'match'].includes(event.activity) ||
        !['independent', 'with_help', 'try_later'].includes(event.outcome) ||
        typeof event.target !== 'string' || !event.target.trim()) return false;
    seen.add(event.id); return true;
  });
  const completed = confirmed.filter(event => event.outcome !== 'try_later');
  const practice = completed.filter(event => event.activity !== 'introduce');
  const targets = [...new Set((practice.length ? practice : completed).map(event => event.target.toUpperCase()))];
  const targetLabel = targets.slice(0, 3).join(', ');
  const achievements = ['Finished the story.'];
  if (targets.length) achievements.push(`${practice.length ? 'Practised' : 'Explored'} ${targetLabel}${targets.length > 3 ? ' and more' : ''}.`);
  if (practice.some(event => event.outcome === 'independent' && !event.hint_used)) achievements.push('Answered on your own.');
  else if (practice.some(event => event.outcome === 'with_help' || event.hint_used)) achievements.push('Practised with help.');
  const moments = confirmed.map(event => ({eventId: event.id, text:
    event.outcome === 'try_later' ? `${event.target.toUpperCase()}: left for another time.` :
    event.activity === 'introduce' ? `Explored ${event.target.toUpperCase()} together.` :
    event.outcome === 'with_help' || event.hint_used ? `${event.target.toUpperCase()}: practised with ${event.hint_used ? 'a hint' : 'help'}.` :
    `${event.target.toUpperCase()}: answered independently.`}));
  return {achievements: achievements.slice(0, 3), moments};
}

export function demoCompletionRecap(events = []) {
  const seen = new Set();
  const recorded = events.filter(event => {
    if (!event || typeof event.event_id !== 'string' || seen.has(event.event_id) ||
        !['correct', 'incorrect', 'help'].includes(event.response) || event.target_letter !== 'P') return false;
    seen.add(event.event_id); return true;
  });
  return {achievements: ['Finished the story.', ...(recorded.length ? ['Practised P.'] : [])],
    moments: recorded.map(event => ({eventId: event.event_id, text: `P: ${
      event.response === 'correct' ? 'a correct response' : event.response === 'incorrect' ? 'another practice opportunity' : 'help noted'}.`}))};
}

export function mountStoryCompletion({parent, title}) {
  const dialog = document.createElement('dialog');
  dialog.className = 'story-completion';
  dialog.setAttribute('aria-labelledby', 'story-completion-title');
  dialog.innerHTML = `<div class="completion-mark" aria-hidden="true">✦</div><p class="completion-book"></p>
    <h2 id="story-completion-title">Lovely work!</h2><p class="completion-intro">This session, you…</p>
    <ul class="completion-achievements"></ul><details class="completion-recap"><summary>Your practice recap</summary><div></div></details>
    <button type="button" class="primary" autofocus>Continue</button>`;
  dialog.querySelector('.completion-book').textContent = title;
  parent.append(dialog);
  let returnFocus;
  dialog.querySelector('button').onclick = () => dialog.close();
  dialog.addEventListener('close', () => { if (returnFocus?.isConnected) returnFocus.focus(); });
  return {
    show(recap = completionRecap()) {
      if (dialog.open) return;
      const list = dialog.querySelector('.completion-achievements'); list.replaceChildren();
      recap.achievements.slice(0, 3).forEach(achievement => { const item = document.createElement('li'); item.textContent = achievement; list.append(item); });
      const details = dialog.querySelector('details'); details.open = false;
      const body = details.querySelector('div'); body.replaceChildren();
      if (recap.moments.length) {
        const moments = document.createElement('ol');
        recap.moments.forEach(moment => { const item = document.createElement('li'); item.textContent = moment.text; moments.append(item); });
        body.append(moments);
      } else { const empty = document.createElement('p'); empty.textContent = 'A story finished. No practice moments to recap this time.'; body.append(empty); }
      returnFocus = document.activeElement;
      dialog.showModal();
    },
    dispose() { dialog.close(); dialog.remove(); }
  };
}
