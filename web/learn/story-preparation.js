// Cache only a server-issued handle. Preparing never applies a tool or plays audio.
export function createPreparation(api, changed = () => {}) {
  let generation = 0, current = null;
  function invalidate() { generation++; current = null; changed(); }
  function prepare(state) {
    const key = `${state.session_id}:${state.revision}`;
    if (current?.key === key && current.status !== 'failed') return current.promise;
    const token = ++generation;
    const entry = current = {key, status: 'preparing'};
    entry.promise = api('prepare', {session_id: state.session_id, revision: state.revision})
      .then(result => {
        if (token !== generation) throw Error('Story context changed.');
        if (result.status !== 'ready' || result.revision !== state.revision || typeof result.preparation_id !== 'string') throw Error('Invalid prepared decision.');
        entry.status = 'ready'; changed(); return result;
      }).catch(error => {
        if (token === generation) { entry.status = 'failed'; changed(); }
        throw error;
      });
    // Background requests may have no waiting caller until the interaction point.
    entry.promise.catch(() => {});
    changed(); return entry.promise;
  }
  async function apply(state) {
    const pending = prepare(state), token = generation;
    const result = await pending;
    if (token !== generation) throw Error('Story context changed.');
    try {
      return await api('apply-prepared', {session_id: state.session_id, revision: state.revision, preparation_id: result.preparation_id});
    } finally {
      if (token === generation) invalidate();
    }
  }
  return {prepare, apply, invalidate, get status() { return current?.status || 'idle'; }};
}
