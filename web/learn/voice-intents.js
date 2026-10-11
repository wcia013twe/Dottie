// Only app-supported actions. Speech is input, never an executable instruction.
export function normalizeSpeech(text) {
  return String(text).toLowerCase().replace(/[’‘]/g, "'").replace(/[.,!?;:]/g, '').replace(/\s+/g, ' ').trim();
}
const routes = {home:'home', explore:'explore', practice:'practice', 'story mode':'stories', stories:'stories', 'about me':'intelligence', 'feel and guess':'guess', 'feel & guess':'guess', 'guess':'guess', 'match':'match', 'letters':'letters', connections:'connect', 'grown-up corner':'connect'};
const routeNames = {home:'Home',explore:'Explore',practice:'Practice',stories:'Story mode',intelligence:'About me',guess:'Feel and guess',match:'Match',letters:'Letters',connect:'Connections'};

function requestPhrase(text) {
  return normalizeSpeech(text)
    .replace(/^(?:(?:hey|okay|ok|well|m+|hm+|um+|uh+|erm|you know)\s+)+/, '')
    .replace(/^please /, '')
    .replace(/^(?:(?:can|could|would|will) (?:you|we) |(?:i want|i'd like|i would like|i need) to |i wanna |let's |let us )/, '')
    .replace(/^please /, '')
    .replace(/ (?:please|for me|now)$/, '').replace(/ please$/, '');
}

function destination(text) {
  const name = text.replace(/^(?:the|my) /, '').replace(/ (?:page|screen|section|area|activity)$/, '');
  if (routes[name]) return routes[name];
  const aliases = {'homepage':'home','home page':'home','main menu':'home','exploration':'explore','practice braille':'practice','practice my letters':'practice','practice letters':'practice','practice the alphabet':'practice','read a story':'stories','read a book':'stories','read stories':'stories','read books':'stories','story':'stories','books':'stories','library':'stories','story library':'stories','learn about me':'intelligence','progress':'intelligence','learning progress':'intelligence','profile':'intelligence','guessing game':'guess','play a guessing game':'guess','matching game':'match','alphabet':'letters'};
  return aliases[name] || null;
}

function naturalIntent(phrase, context) {
  if (/^(?:go|take me|bring me|head|return|get me) (?:back )?home$/.test(phrase)) return {type:'navigate',route:'home'};
  if (/^(?:go|take me|bring me|head|return|get me) back(?: to (?:the )?(?:previous page|last page))?$/.test(phrase)) return {type:'back'};
  if (/^(?:what can i (?:say|do)|how (?:do i|can i) (?:navigate|use this)|help me (?:navigate|get started))$/.test(phrase)) return {type:'help'};
  if (/^(?:say (?:that|it) again|repeat (?:that|it) again)$/.test(phrase)) return {type:'repeat'};
  if (/^(?:turn|switch) (?:the |my )?(?:microphone|mic) off$/.test(phrase) || /^(?:stop|quit) listening(?: to me)?$/.test(phrase)) return {type:'stopListening'};
  if (/^(?:stop|pause) (?:the )?(?:voice|speech|audio|talking)$/.test(phrase) || phrase === 'be quiet') return {type:'control',name:'stop audio'};
  if (context.storyReader && /^(?:read (?:a|the|this|my) (?:story|book|page)|read (?:it|to me))$/.test(phrase)) return {type:'control',name:'read story'};
  if (/^(?:turn (?:to )?|go to |show me )?(?:the )?next page$/.test(phrase)) return {type:'control',name:'next page'};
  if (/^(?:turn (?:to )?|go to |show me )?(?:the )?previous page$/.test(phrase)) return {type:'control',name:'previous page'};
  const target = phrase.replace(/^(?:open|go(?: (?:back )?to)?|show me|show|take me (?:back )?to|bring me (?:back )?to|head to|return to|switch to|start|begin|try) /, '');
  // Match a whole supported destination, never a keyword buried in an answer.
  const choices = target.split(/\s+(?:or|and|then)\s+/).map(destination);
  if (choices.length > 1 && choices.every(Boolean)) {
    return {type:'clarify',message:`Which would you like to open: ${[...new Set(choices)].map(route => routeNames[route]).join(' or ')}? Say one destination.`};
  }
  const route = destination(target);
  if (route) return {type:'navigate',route};
  return null;
}

export function interpretSpeech(text, context = {}) {
  const intent = interpretPhrase(text, context);
  if (intent.type !== 'unknown') return intent;
  // Scribe may put a short request and subsequent conversation in one segment.
  // Only a complete leading sentence can stand alone; never scan arbitrary text.
  const sentences = String(text).split(/[.!?;]\s+/);
  const first = sentences[0];
  if (first !== String(text)) {
    const leading = interpretPhrase(first, context);
    const destinations = [...new Set(sentences.map(sentence => interpretPhrase(sentence, context)).filter(candidate => candidate.type === 'navigate').map(candidate => candidate.route))];
    if (destinations.length > 1) return {type:'clarify',message:`Which would you like to open: ${destinations.map(route => routeNames[route]).join(' or ')}? Say one destination.`};
    if (['navigate','back','control'].includes(leading.type) && sentences.slice(1).some(sentence => /^(?:no\b|actually\b|don't\b|do not\b|never mind\b)/.test(normalizeSpeech(sentence)))) return {type:'clarify',message:'What would you like to do instead? Say one destination, or ask for help.'};
    if (!['unknown','answer','storyResponse','object','letter'].includes(leading.type)) return leading;
  }
  return intent;
}

function interpretPhrase(text, context) {
  let phrase = requestPhrase(text);
  if (/^(stop listening|microphone off|turn off microphone)$/.test(phrase)) return {type:'stopListening'};
  if (/^(enable|turn on) spoken navigation$/.test(phrase)) return {type:'guidance',enabled:true};
  if (/^(disable|turn off) spoken navigation$/.test(phrase)) return {type:'guidance',enabled:false};
  if (/^(go back|back)$/.test(phrase)) return {type:'back'};
  const route = phrase.replace(/^(open|go to|show|take me to) /, '');
  if (routes[route]) return {type:'navigate', route:routes[route]};
  if (phrase === 'go home') return {type:'navigate', route:'home'};
  if (/^(repeat|repeat that|read this page|read the page)$/.test(phrase)) return {type:'repeat'};
  if (/^(help|help me|give me a hint|hint)$/.test(phrase)) return {type:'help'};
  if (/^(stop speech|stop speaking|mute)$/.test(phrase)) return {type:'control',name:'stop audio'};
  if (phrase === 'read story' && !context.storyReader) return {type:'navigate',route:'stories'};
  if (/^(read story|pause reading|resume reading|play|resume|pause|stop audio|next page|previous page|continue|continue story|continue the story|next word|try another word|start camera|stop camera|open peter rabbit)$/.test(phrase)) return {type:'control', name:phrase};
  const natural = naturalIntent(phrase, context);
  if (natural) return natural;
  if (context.awaitingStoryResponse) return {type:'storyResponse', text:String(text).trim().slice(0,300)};
  if (context.route === 'guess' && context.acceptingAnswer) {
    phrase = phrase.replace(/^(my answer is|the answer is|i think it is|i think it's|it is|it's) /, '');
    return {type:'answer', text:phrase.slice(0,30)};
  }
  const selection = phrase.replace(/^(select|choose|pick|show me) /, '').replace(/^(the|a) /, '');
  const objects = context.objects || [];
  if (objects.includes(selection)) return {type:'object', label:selection};
  const letter = selection.replace(/^letter /, '');
  const aliases = {ay:'a',aye:'a',bee:'b',see:'c',sea:'c',dee:'d',ee:'e',gee:'g',eye:'i',jay:'j',kay:'k',pea:'p',pee:'p',cue:'q',are:'r',tee:'t',you:'u',vee:'v',why:'y',zee:'z'};
  const resolved = aliases[letter] || letter;
  if (['practice','letters'].includes(context.route) && /^[a-z]$/.test(resolved)) return {type:'letter', letter:resolved};
  return {type:'unknown'};
}
