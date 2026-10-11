import { storyVoiceContext, performStoryVoice } from './story-coach.js?v=nano-story-4';
import { stopNavigationVoice } from './navigation-voice.js?v=conversational-navigation-2';

export function voiceContext() {
  const route = location.hash.slice(1) || 'home';
  const form = document.querySelector('#answer-form');
  return {
    route, storyReader:!!document.querySelector('.book-player'), title:document.querySelector('main h1')?.textContent,
    question:document.querySelector('.braille-word')?.innerHTML,
    acceptingAnswer:!!form && !form.querySelector('button')?.disabled,
    objects:[...document.querySelectorAll('[data-object], #camera-objects [data-label]')].map(node => node.dataset.object || node.dataset.label),
    page:document.querySelector('#ebook-content')?.getAttribute('aria-label'),
    ...storyVoiceContext()
  };
}

function activate(selector, unavailable = 'That action is not available here.') {
  const control = document.querySelector(selector);
  if (!control || control.disabled || control.getAttribute('aria-disabled') === 'true' || control.hidden) return unavailable;
  control.click(); return '';
}

export async function performVoiceAction(intent, {speak}) {
  const route = location.hash.slice(1) || 'home';
  switch (intent.type) {
    case 'clarify': return intent.message;
    case 'guidance': {
      const control=document.querySelector('#navigation-guidance');
      if (!control) return 'Spoken navigation is unavailable.';
      if (control.checked !== intent.enabled) control.click();
      return intent.enabled ? 'Spoken navigation is on.' : '';
    }
    case 'navigate': location.hash = intent.route; return '';
    case 'back':
      return activate('#story-close, main .back') || '';
    case 'answer': {
      const form = document.querySelector('#answer-form'), input = form?.querySelector('#answer');
      if (!input || form.querySelector('button').disabled) return 'This question has already been answered.';
      input.value = intent.text; form.requestSubmit(); return '';
    }
    case 'object': {
      const selector = route === 'explore' ? '#camera-objects [data-label]' : '[data-object]';
      const options = [...document.querySelectorAll(selector)].filter(node => (node.dataset.label || node.dataset.object) === intent.label);
      if (options.length !== 1) return 'That object is no longer available. Try another object.';
      options[0].click(); return '';
    }
    case 'letter': {const error=activate(`[data-letter="${intent.letter}"]`);return error || `Letter ${intent.letter.toUpperCase()} selected. Say repeat to hear its dots.`;}
    case 'storyResponse': return performStoryVoice('submit_response', intent.text);
    case 'repeat': {
      if (storyVoiceContext().awaitingStoryResponse) return performStoryVoice('speak_prompt');
      if(document.querySelector('#page-text'))return activate('#story-reading');
      const text = document.querySelector('main')?.innerText;
      speak(text || 'Choose an experience to begin.', true); return '';
    }
    case 'help': {
      if (storyVoiceContext().awaitingStoryResponse) return performStoryVoice('give_hint');
      return route === 'guess' ? 'Tell me your guess, or ask to try another word.' : route === 'explore' ? 'Your camera preview opens here. You can stop the camera, or ask to go somewhere else.' : 'What would you like to do? You can explore, practice, read a story, or hear about your progress.';
    }
    case 'control': {
      const name = intent.name;
      if (name === 'open peter rabbit') {
        if (route !== 'stories') return 'Open Story mode first, then say “Open Peter Rabbit”.';
        return activate('#open-peter');
      }
      if (['continue', 'continue story', 'continue the story'].includes(name)) {
        if (storyVoiceContext().storyPhase && storyVoiceContext().storyPhase !== 'reading') return performStoryVoice('resume_story');
        return activate('#demo-next, #reader-next');
      }
      if (name === 'read story') return activate('#story-reading');
      if (name === 'pause reading' || name === 'resume reading') {
        if (!document.querySelector('.book-player')) return 'Open a book first.';
        const paused=window.speechSynthesis?.paused;
        if ((name === 'pause reading') !== !!paused) return activate('#pause-reading');
        return '';
      }
      if (name === 'stop audio') { stopNavigationVoice(); window.speechSynthesis?.cancel(); return ''; }
      if (name === 'play' || name === 'resume' || name === 'pause') {
        const play = document.querySelector('#reader-play');
        if (!play || play.disabled) return 'Page playback is not available right now.';
        const playing = play.getAttribute('aria-label')?.startsWith('Pause');
        if ((name === 'pause') === playing) play.click();
        return name === 'pause' ? 'Page turns paused.' : 'Automatic page turns started.';
      }
      const selectors = {'next page':'#reader-next','previous page':'#reader-prev','next word':'#next-word','try another word':'#next-word','start camera':'#start-camera','stop camera':'#stop-camera'};
      return selectors[name] ? activate(selectors[name]) : 'That action is unavailable here.';
    }
    default: return 'What would you like to do? You can explore, practice, read a story, or hear about your progress.';
  }
}
