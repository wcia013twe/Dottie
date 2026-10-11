// Local shortcuts remain instant. The model only sees unknown navigation text
// and minimal page context; activity answers never enter this fallback.
import { interpretSpeech } from './voice-intents.js?v=conversational-navigation-2';

export function validModelIntent(intent, context) {
  if (!intent || typeof intent !== 'object' || Array.isArray(intent)) return false;
  const keys=Object.keys(intent).sort().join(',');
  if (intent.type==='navigate') return keys==='route,type' && ['home','explore','practice','stories','intelligence','guess','match','letters','connect'].includes(intent.route);
  if (['back','help','repeat','stopListening'].includes(intent.type)) return keys==='type';
  if (intent.type==='clarify') return keys==='message,type' && intent.message==='What would you like to do? You can explore, practice, read a story, or hear about your progress.';
  if (intent.type==='control') return keys==='name,type' && (intent.name==='stop audio' || context.storyReader && ['next page','previous page','read story','pause reading','resume reading'].includes(intent.name));
  return false;
}

export async function understandSpeech(text, context, {signal, request=fetch}={}) {
  const local=interpretSpeech(text,context);
  if (local.type!=='unknown' || context.awaitingStoryResponse || context.acceptingAnswer) return local;
  const response=await request('/api/voice-intent',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:String(text).trim().slice(0,500),route:context.route || 'home',story_reader:!!context.storyReader}),signal});
  if ([404,405,501].includes(response.status)) throw Error('Restart the local server to enable conversational navigation. Short navigation commands still work.');
  const result=await response.json();
  if (!response.ok) throw Error(result.error || 'Natural language interpretation is temporarily unavailable.');
  if (!result || Object.keys(result).sort().join(',')!=='intent,source' || result.source!=='model' || !validModelIntent(result.intent,context)) throw Error('I could not choose a safe navigation action. Where would you like to go?');
  return result.intent;
}
