// Only app-supported actions. Speech is input, never an executable instruction.
export function normalizeSpeech(text) {
  return String(text).toLowerCase().replace(/[.,!?]/g, '').replace(/\s+/g, ' ').trim();
}
const routes = {home:'home', explore:'explore', practice:'practice', 'story mode':'stories', stories:'stories', 'about me':'intelligence', 'feel and guess':'guess', 'feel & guess':'guess', 'guess':'guess', 'match':'match', 'letters':'letters', connections:'connect', 'grown-up corner':'connect'};
export function interpretSpeech(text, context) {
  let phrase = normalizeSpeech(text).replace(/^please /, '').replace(/ please$/, '');
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
  if (/^(read story|pause reading|resume reading|play|resume|pause|stop audio|next page|previous page|continue|continue story|continue the story|next word|try another word|start camera|stop camera|open peter rabbit)$/.test(phrase)) return {type:'control', name:phrase};
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
