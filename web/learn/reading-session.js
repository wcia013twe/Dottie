// Browser-local reading lifecycle; coach sessions remain owned by the local server.
export function ensureReadingSession(book) {
  if (book.finished === undefined) book.finished = book.current === book.total;
  if (!book.readingSessionId) {
    book.readingSessionId = crypto.randomUUID();
    book.startedAt = new Date().toISOString();
  }
  return book.readingSessionId;
}
export function finishReadingSession(book) {
  ensureReadingSession(book);
  book.finished = true;
  book.completedAt ||= new Date().toISOString();
  book.current = book.total;
}
export function restartReadingSession(book, start = 0) {
  ensureReadingSession(book);
  book.readingSessions ||= [];
  book.readingSessions.push({id:book.readingSessionId, startedAt:book.startedAt,
    completedAt:book.completedAt || null, finished:book.finished,
    position:book.position || 0, page:book.page || 0, coachSessionId:book.coachSessionId || null});
  Object.assign(book, {readingSessionId:crypto.randomUUID(), startedAt:new Date().toISOString(),
    completedAt:null, coachSessionId:null, finished:false, current:start,
    position:start, page:0, pageFraction:0, scroll:0});
}
export const readingLabel = book => book.finished || book.current === book.total ? 'Completed · Review book' :
  book.readingSessionId || book.current > 0 ? 'Continue reading' : 'Start reading';

export async function restoreCoachSession({sessionId, api, history}) {
  if (sessionId) {
    try { return await api('action', {session_id:sessionId, name:'get_story_context'}); }
    catch (error) {
      // Only server-confirmed expiry permits a replacement; an outage must not fork a session.
      if (!error.message.startsWith('Session expired')) throw error;
    }
  }
  return api('session', {history});
}
