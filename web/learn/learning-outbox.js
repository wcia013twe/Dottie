/** Bounded upload queues. Reading progress remains local and independent. */
import {ACTIVITY_CATALOG} from './activity-catalog.js';
export const INTELLIGENCE_KEY = 'magneto-intelligence-v2';
export const ATTEMPTS_KEY = 'magneto-attempts-v3';
export const PROFILE_KEY = 'magneto-learning-profile-v1';
const isId = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
const supports = ['none', 'hint', 'modeled_answer', 'unknown'];
const results = ['correct', 'incorrect', 'help_requested', 'unconfirmed'];

export class LearningOutbox {
  constructor({storage = globalThis.localStorage, fetcher = (...args) => globalThis.fetch(...args), uuid = () => crypto.randomUUID(), clock = () => new Date().toISOString()} = {}) {
    this.storage = storage; this.fetcher = fetcher; this.uuid = uuid; this.clock = clock;
    this.events = []; this.attempts = []; this.profile = null; this.storageOK = true;
    this.error = ''; this.pending = null; this.profileReady = false; this.generation = 0;
    try {
      const legacy = JSON.parse(storage.getItem(INTELLIGENCE_KEY) || '[]');
      const attempts = JSON.parse(storage.getItem(ATTEMPTS_KEY) || '[]');
      const profile = JSON.parse(storage.getItem(PROFILE_KEY) || 'null');
      if (!Array.isArray(legacy) || !Array.isArray(attempts)) throw Error('Invalid saved queue');
      this.events = legacy; this.attempts = attempts;
      if (profile && isId(profile.profile_id) && typeof profile.uploads_enabled === 'boolean') this.profile = profile;
    } catch { this.storageOK = false; this.error = 'Saved learning uploads could not be read.'; this.corrupt = true; }
  }
  profileId(preferred = null) {
    if (!this.profile) {
      this.profile = {profile_id: isId(preferred) ? preferred : this.uuid(), uploads_enabled: false};
      this.saveProfile();
    }
    return this.profile.profile_id;
  }
  get uploadsEnabled() { return this.profile?.uploads_enabled === true; }
  get queuedCount() { return this.events.length + this.attempts.length; }
  saveProfile() {
    try { this.storage.setItem(PROFILE_KEY, JSON.stringify(this.profile)); }
    catch { this.storageOK = false; }
  }
  save() {
    if (this.corrupt) return;
    try {
      this.storage.setItem(INTELLIGENCE_KEY, JSON.stringify(this.events));
      this.storage.setItem(ATTEMPTS_KEY, JSON.stringify(this.attempts));
    } catch { this.storageOK = false; this.error = 'Browser storage is unavailable; keep this page open to retry uploads.'; }
  }
  async post(path, payload) {
    const response = await this.fetcher(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    let result; try { result = await response.json(); } catch { throw Error('Learning service returned invalid JSON.'); }
    if (!response.ok) throw Error(result.error || 'Learning upload failed.');
    return result;
  }
  async createProfile({profile_id, consent, audio_enabled = false}) {
    if (!isId(profile_id) || !['granted','revoked'].includes(consent)) throw Error('Invalid learning profile.');
    const result = await this.post('/api/learning/profile', {schema_version:'2.0', profile_id, consent, preferences:{audio_enabled}});
    if (result.profile_id !== profile_id || result.consent !== consent) throw Error('Profile acknowledgement does not match.');
    return result;
  }
  async setUploadsEnabled(enabled) {
    this.profileId(); this.profile.uploads_enabled = Boolean(enabled);
    this.generation++; this.profileReady = false; this.profile.consent_pending = true; this.saveProfile();
    const generation = this.generation;
    try {
      await this.createProfile({profile_id:this.profile.profile_id, consent:enabled ? 'granted' : 'revoked'});
      if (generation === this.generation) { this.profileReady = enabled; this.profile.consent_pending = false; this.saveProfile(); this.error = ''; }
    } catch (error) { this.error = error.message; throw error; }
    if (enabled && generation === this.generation) return this.flush();
  }
  enqueueAttempt({attempt_id = this.uuid(), profile_id, session_id, activity_ref, result, support = 'unknown', assessment = 'teacher_confirmed'}) {
    if (this.corrupt) throw Error('Repair the saved learning queue before adding records.');
    if (!isId(attempt_id) || !isId(profile_id) || !isId(session_id) || !Object.hasOwn(ACTIVITY_CATALOG, activity_ref) ||
        !results.includes(result) || !supports.includes(support) || !['teacher_confirmed','unconfirmed'].includes(assessment) ||
        ((assessment === 'unconfirmed') !== (result === 'unconfirmed'))) throw Error('Invalid learning attempt.');
    const attempt = {attempt_id, observed_at:this.clock(), activity_ref, result, support, assessment};
    const previous = this.attempts.find(row => row.attempt.attempt_id === attempt_id);
    if (previous) {
      const content = {...attempt, observed_at:previous.attempt.observed_at};
      if (previous.profile_id !== profile_id || previous.session_id !== session_id || JSON.stringify(previous.attempt) !== JSON.stringify(content)) throw Error('Attempt ID conflict.');
      return previous.attempt;
    }
    this.attempts.push({profile_id, session_id, attempt}); this.save(); return attempt;
  }
  acknowledge(result, key, sent) {
    const ids = result[key], allowed = new Set(sent);
    if (!Array.isArray(ids) || !ids.length || new Set(ids).size !== ids.length || ids.some(id => !allowed.has(id))) throw Error('Invalid learning acknowledgement; records kept.');
    return new Set(ids);
  }
  flush() {
    if (this.pending) return this.pending;
    this.pending = this.drain().catch(error => { this.error = error.message; throw error; }).finally(() => { this.pending = null; });
    return this.pending;
  }
  async drain() {
    if (this.corrupt || !this.profile) return;
    if (!this.uploadsEnabled) {
      if (this.profile.consent_pending) {
        await this.createProfile({profile_id:this.profile.profile_id, consent:'revoked'});
        this.profile.consent_pending = false; this.saveProfile(); this.error = '';
      }
      return;
    }
    const generation = this.generation, profile_id = this.profile.profile_id;
    if (!this.profileReady) {
      await this.createProfile({profile_id, consent:'granted'});
      if (generation !== this.generation || !this.uploadsEnabled) return;
      this.profileReady = true; this.profile.consent_pending = false; this.saveProfile();
    }
    const pending = this.attempts.filter(row => row.profile_id === profile_id);
    while (pending.length && this.uploadsEnabled && generation === this.generation) {
      const session_id = pending[0].session_id;
      const rows = pending.filter(row => row.session_id === session_id).slice(0, 50);
      const attempts = rows.map(row => row.attempt);
      const result = await this.post('/api/learning/attempts', {schema_version:'3.0', profile_id, session_id, attempts});
      if (result.schema_version !== '3.0' || result.profile_id !== profile_id || result.session_id !== session_id) throw Error('Learning acknowledgement belongs to another session.');
      const ack = this.acknowledge(result, 'attempt_ids', attempts.map(a => a.attempt_id));
      this.attempts = this.attempts.filter(row => !ack.has(row.attempt.attempt_id)); this.save();
      for (const row of rows) pending.splice(pending.indexOf(row), 1);
    }
    const legacy = this.events.filter(event => event.profile_id === profile_id);
    while (legacy.length && this.uploadsEnabled && generation === this.generation) {
      const rows = legacy.splice(0, 50);
      const result = await this.post('/api/learning/events', {schema_version:'2.0', events:rows});
      const ack = this.acknowledge(result, 'event_ids', rows.map(e => e.event_id));
      this.events = this.events.filter(event => !ack.has(event.event_id)); this.save();
    }
    if (this.storageOK) this.error = '';
  }
}
