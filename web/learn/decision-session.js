/** Complete snapshots and transport state only; teaching choices come from Databricks. */
import {LearningOutbox} from './learning-outbox.js';
export const CONNECTED_KEY = 'magneto-connected-demo-v1';
export const PASSAGE_IDS = ['monday_apple', 'tuesday_pear', 'wednesday_plum'];
const letters = ['A', 'P', 'P'];
const isId = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);

export function validateResult(result, request) {
  const d = result?.decision;
  const target = letters[PASSAGE_IDS.indexOf(request.passage_id)];
  const event = request.events.at(-1)?.event_id ?? null;
  if (result?.request_id !== request.request_id || result?.session_id !== request.session_id ||
      !Number.isFinite(result.elapsed_ms) || result.elapsed_ms < 0 || typeof result.model !== 'string' ||
      !d || Object.keys(d).sort().join(',') !== 'action,based_on_event_id,passage_id,prompt,reason,target_letter' ||
      !['continue', 'teach'].includes(d.action) || d.passage_id !== request.passage_id ||
      d.based_on_event_id !== event || typeof d.reason !== 'string' || !d.reason.trim() || d.reason.length > 400 ||
      (d.action === 'continue' && (d.prompt !== null || d.target_letter !== null)) ||
      (d.action === 'teach' && (d.target_letter !== target || typeof d.prompt !== 'string' || !d.prompt.trim() || d.prompt.length > 240))) {
    throw new Error('The service returned an invalid or outdated decision. No activity was started.');
  }
  return result;
}

export class DecisionSession {
  constructor({storage = globalThis.localStorage, fetcher = (...args) => globalThis.fetch(...args), uuid = () => crypto.randomUUID(), timeoutMs = 15000, outbox = null} = {}) {
    this.storage = storage; this.fetcher = fetcher; this.uuid = uuid; this.timeoutMs = timeoutMs; this.outbox = outbox || new LearningOutbox({storage, fetcher, uuid});
    this.pending = null; this.error = ''; this.storageOK = true; this.generation = 0;
    let savedProfile = null;
    try { savedProfile = JSON.parse(storage.getItem(CONNECTED_KEY) || 'null')?.profile_id; } catch {}
    this.profileId = this.outbox.profileId(savedProfile);
    this.state = this.fresh();
    try {
      const s = JSON.parse(storage.getItem(CONNECTED_KEY) || 'null');
       if (s && isId(s.session_id) && Number.isInteger(s.step) && s.step >= 0 && s.step <= 3 &&
          Array.isArray(s.events) && s.events.length <= 2 && s.events.every(e => isId(e.event_id) &&
            ['tuesday_pear', 'wednesday_plum'].includes(e.passage_id) && e.target_letter === 'P' && ['correct', 'incorrect', 'help'].includes(e.response)) &&
          s.decisions && typeof s.decisions === 'object' && !Array.isArray(s.decisions) && Array.isArray(s.skipped)) {
        // Revalidate saved results against the events that existed at their passage boundary.
        for (const [passage_id, result] of Object.entries(s.decisions)) {
          if (!PASSAGE_IDS.includes(passage_id) || !isId(result.request_id)) throw Error('Invalid saved decision');
          validateResult(result, {request_id: result.request_id, session_id: s.session_id, passage_id,
            events: s.events.filter(e => PASSAGE_IDS.indexOf(e.passage_id) < PASSAGE_IDS.indexOf(passage_id))});
        }
        if (s.skipped.some(p => !PASSAGE_IDS.includes(p))) throw Error('Invalid saved skip');
        this.state = {...s, profile_id: this.profileId};
      }
    } catch { this.storageOK = false; }
  }
  fresh() { return {session_id: this.uuid(), profile_id: this.profileId, step: 0, events: [], decisions: {}, skipped: []}; }
  get passage() { return PASSAGE_IDS[this.state.step]; }
  get result() { return this.state.decisions[this.passage]; }
  get skipped() { return this.state.skipped.includes(this.passage); }
  save() {
    try { this.storage.setItem(CONNECTED_KEY, JSON.stringify(this.state)); this.storageOK = true; }
    catch { this.storageOK = false; }
  }
  cancel() {
    this.generation++;
    if (this.pending) { this.pending.abort(); this.pending = null; this.error = 'Decision request cancelled. Retry when ready.'; }
  }
  restart() { this.cancel(); this.state = this.fresh(); this.error = ''; this.save(); }
  advance() {
    if (this.pending || (!this.result && !this.skipped)) return;
    this.generation++; this.state.step = Math.min(3, this.state.step + 1); this.error = ''; this.save();
  }
  record(response, support = 'unknown') {
    if (this.pending || this.result?.decision.action !== 'teach' || ![1, 2].includes(this.state.step) ||
        !['correct', 'incorrect', 'help'].includes(response)) return;
    if (this.state.events.some(e => e.passage_id === this.passage)) return;
    if (!['none','hint','modeled_answer','unknown'].includes(support)) return;
    const event_id = this.uuid();
    this.state.events.push({event_id, passage_id: this.passage, target_letter: 'P', response});
    if (this.outbox.uploadsEnabled) {
      try {
        this.outbox.enqueueAttempt({attempt_id:event_id, profile_id:this.profileId, session_id:this.state.session_id,
          activity_ref:this.passage === 'tuesday_pear' ? 'caterpillar/tuesday-pear/identify-p@1' : 'caterpillar/wednesday-plum/identify-p@1',
          result:response === 'help' ? 'help_requested' : response, support, assessment:'teacher_confirmed'});
        void this.outbox.flush().catch(() => {});
      } catch (error) { this.outbox.error = error.message; }
    }
    this.save(); // The actual response is saved before any later request is created.
    this.advance();
  }
  skip() {
    if (this.pending) return;
    if (!this.skipped) this.state.skipped.push(this.passage);
    this.error = ''; this.save();
  }
  async request(onChange = () => {}) {
    if (this.pending || !this.passage || this.result || this.skipped) return;
    const request = {request_id: this.uuid(), session_id: this.state.session_id, passage_id: this.passage,
      events: structuredClone(this.state.events)};
    const generation = ++this.generation;
    const controller = new AbortController();
    this.pending = controller; this.error = '';
    const started = performance.now();
    let timer;
    const expired = new Promise((_, reject) => { timer = setTimeout(() => {
      controller.abort(); reject(new Error('Databricks did not respond within 15 seconds. No activity was started.'));
    }, this.timeoutMs); });
    onChange();
    try {
      const work = (async () => {
        const response = await this.fetcher('/api/decision', {method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(request), signal: controller.signal});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'The decision service is unavailable.');
        return validateResult(result, request);
      })();
      const result = await Promise.race([work, expired]);
      if (generation !== this.generation || request.session_id !== this.state.session_id || request.passage_id !== this.passage) return;
      this.state.decisions[this.passage] = {...result, round_trip_ms: Math.round(performance.now() - started)};
      this.save();
    } catch (error) {
      if (generation === this.generation) this.error = controller.signal.aborted ?
        'Databricks did not respond within 15 seconds. No activity was started.' : error.message;
    } finally {
      clearTimeout(timer);
      if (generation === this.generation) { this.pending = null; onChange(); }
    }
  }
}
