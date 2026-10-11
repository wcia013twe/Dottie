import {caterpillarActivities, mountCaterpillarActivities} from './caterpillar-activities.js';
import { ensureReadingSession, finishReadingSession } from './reading-session.js';
import { completionRecap, mountStoryCompletion } from './story-completion.js';
import { createPageTurnSound } from './page-turn-sound.js';
import { mountNarration } from './narration.js?v=audio-progress-1';
import { mountStoryCoach } from './story-coach.js?v=nano-story-4';
// Pair each illustration with the following passage in the EPUB reading order.
function illustrationSpreads(html) {
  const root = new DOMParser().parseFromString(html, 'text/html').body;
  const spreads = []; let passage = '', image = '', pageId = null;
  function visit(node) {
    if (node.nodeType === 3) { if (node.textContent.trim()) { const p=document.createElement('p');p.textContent=node.textContent;passage+=p.outerHTML; } return; }
    if (node.nodeType !== 1) return;
    if (node.tagName === 'IMG') { if(image || passage.trim())spreads.push({image,html:passage,pageId});image=node.outerHTML;pageId=node.dataset.storyPageId||null;passage='';return; }
    if (node.querySelector('img') || ['DIV','SECTION','ARTICLE','FIGURE'].includes(node.tagName)) { [...node.childNodes].forEach(visit);return; }
    passage += node.outerHTML;
  }
  [...root.childNodes].forEach(visit);
  if (image || passage.trim()) spreads.push({image,html:passage,pageId});
  return spreads.length ? spreads : [{image:'',html:html}];
}
// Browser-native pagination; the imported chapter remains accessible text.
export function mountFlipbook({main, book, content, save, announce}) {
  ensureReadingSession(book);
  const reader=main.querySelector('#ebook-content'), sheet=main.querySelector('#book-sheet');
  const windowEl=main.querySelector('#page-window'), text=main.querySelector('#page-text');
  const previous=main.querySelector('#reader-prev'), next=main.querySelector('#reader-next');
  const status=main.querySelector('#reader-feedback'), chapterSelect=main.querySelector('#reader-chapter');
  const seek=main.querySelector('#reader-seek'), play=main.querySelector('#reader-play'), player=main.querySelector('.book-player');
  let spreads=[], paintedPage=-1;
  reader.classList.add('spread-reader');
  const imageOnly = content.chapters.every(chapter => chapter.html.includes('<img ') && !chapter.html.replace(/<[^>]*>/g, '').trim());
  reader.classList.toggle('image-only-reader', imageOnly);
  let audioFraction = 0;
  function paintTimeline(){
    if(!imageOnly)return;
    seek.min='0';seek.max=String(content.chapters.length);seek.step='0.001';
    seek.value=String(chapter+audioFraction);
    seek.setAttribute('aria-label','Book playback progress');
    const seekLabel=main.querySelector('label[for="reader-seek"]');
    if(seekLabel)seekLabel.textContent='Book playback progress';
    seek.setAttribute('aria-valuetext',`Page ${chapter+1} of ${content.chapters.length}, narration ${Math.round(audioFraction*100)} percent`);
    seek.style.setProperty('--progress',`${(chapter+audioFraction)/content.chapters.length*100}%`);
  }
  const illustration=document.createElement('div');illustration.className='spread-illustration';sheet.prepend(illustration);
  const pageTurnSound=createPageTurnSound();
  let playTimer=null, narration=null;
  function stopPlaying(pauseAudio=true){if(pauseAudio)narration?.pause();clearInterval(playTimer);playTimer=null;play.textContent='▶';play.title='Resume automatic page turns';play.setAttribute('aria-label','Play automatic page turns');main.querySelector('#player-mode').textContent='Read at your own pace';}
  let chapter=Math.min(book.position||0,content.chapters.length-1), page=0, count=1, stride=0;
  let turning=false, disposed=false, animation=null, overlay=null, resizeFrame=0, generation=0;
  if (book.finished === undefined) book.finished = book.current === book.total;
  let legacyScroll = book.pageFraction === undefined ? (book.scroll || 0) : 0;
  narration=mountNarration({player,bookId:book.id,onPlay:()=>{if(coach.isPaused())narration.pause();else coach.stopSpeech?.();},onEnded:()=>coach.offerQuestion?.(),onProgress:fraction=>{audioFraction=fraction;paintTimeline();}});
  const caterpillarDemo=book.id==='local-very-hungry-caterpillar';
  if(caterpillarDemo)content.checkpoints=caterpillarActivities.map(a=>({...a,page_id:String(a.page)}));
  let questionStops=[];
  const markerArea=main.querySelector('#question-markers'), markerLabel=main.querySelector('#question-stop-label');
  function paintQuestionMarker(){
    markerArea.replaceChildren();markerLabel.hidden=true;
    const labels=[];
    const appearances={visited:['◦','Saved activity'],planned:['?','Planned question'],solved:['✓','Solved'],assisted:['✓','Solved with help'],skipped:['–','Skipped']};
    for(const stop of questionStops){
      const checkpoint=content.checkpoints?.find(c=>c.id===stop.id);
      const target=checkpoint?(caterpillarDemo?checkpoint.page-1:spreads.findIndex(s=>s.pageId===checkpoint.page_id)):-1;
      if(target<0)continue;
      const [glyph,markerStatus]=appearances[stop.status];
      const marker=document.createElement('button');
      marker.type='button';
      marker.onclick=async()=>{
        stopPlaying();
        try{await coach.leaveForReview?.();}catch{status.textContent='Could not stop the cell. Try Continue story before reviewing.';return;}
        cancelTurn();if(caterpillarDemo)await loadChapter(target,0);else{page=target;paint();persist();}stopPlaying();coach.review?.(stop.id);
      };
      marker.className='question-marker question-marker--'+stop.status;
      marker.textContent=glyph;
      const label=`${markerStatus} · page ${target+1}${stop.planned&&stop.status!=='planned'?' · new question planned':''}`;
      marker.title=label;marker.setAttribute('aria-label',label);
      if(stop.planned&&stop.status!=='planned')marker.classList.add('question-marker--revisit');
      marker.style.left=`${caterpillarDemo?target/content.chapters.length*100:count>1?target/(count-1)*100:0}%`;
      markerArea.append(marker);labels.push(label);
    }
    markerLabel.textContent=labels.join(' / ');markerLabel.hidden=!labels.length;
  }
  const coach=(caterpillarDemo?mountCaterpillarActivities:mountStoryCoach)({player,book,save,enabled:book.bundled,checkpoints:content.checkpoints||[],pause:stopPlaying,onResume:()=>turn(1),onQuestionStops:stops=>{questionStops=stops;paintQuestionMarker();}});
  const completion=mountStoryCompletion({parent:player,title:book.title});
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  function persist() {
    book.position=chapter;book.page=page;book.pageFraction=count>1?page/(count-1):0;
    book.current=book.finished?book.total:chapter;book.scroll=0;save();
  }
  function paint() {
    if(paintedPage!==page){
      const spread=spreads[page];
      illustration.innerHTML=spread?.image || '<span class="spread-no-art" aria-hidden="true">⠿</span>';
      text.innerHTML=spread?.html || '<p class="spread-caption"></p>';
      if(!spread?.html)text.querySelector('.spread-caption').textContent=content.chapters[chapter].title;
      windowEl.scrollTop=0;paintedPage=page;const upcoming=[];
      for(let c=chapter;c<content.chapters.length && upcoming.length<3;c++){
        const pages=c===chapter?spreads:illustrationSpreads(content.chapters[c].html);
        for(let p=c===chapter?page:0;p<pages.length && upcoming.length<3;p++)upcoming.push(pages[p].pageId);
      }
      coach.context(caterpillarDemo?String(chapter+1):spread?.pageId||null,upcoming);narration.context(text.textContent);
    }
    paintQuestionMarker();
    previous.disabled=coach.isPaused() || (chapter===0 && page===0);
    next.disabled=coach.isPaused();
    previous.setAttribute('aria-disabled',String(turning || previous.disabled));
    next.setAttribute('aria-disabled',String(turning));
    next.textContent=chapter===content.chapters.length-1 && page===count-1?'✓':'❯';
    next.setAttribute('aria-label',chapter===content.chapters.length-1 && page===count-1?'Finish book':'Next page');
    seek.max=String(count);seek.value=String(page+1);seek.setAttribute('aria-valuetext',`Page ${page+1} of ${count}`);seek.style.setProperty('--progress',`${count>1?page/(count-1)*100:0}%`);
    paintTimeline();
    status.textContent=book.finished?'Completed · Review book · ' + `Page ${page+1} of ${count}`:`Page ${page+1} of ${count} · ${content.chapters[chapter].title}`;
    reader.setAttribute('aria-label',`${content.chapters[chapter].title}, page ${page+1} of ${count}`);
  }
  function layout(fraction=book.pageFraction||0) {
    count=Math.max(1,spreads.length);
    page=Math.min(count-1,Math.max(0,Math.round(fraction*(count-1))));legacyScroll=0;paint();persist();
  }
  async function loadChapter(index, fraction=0) {
    chapter=index;chapterSelect.value=String(chapter);
    spreads=illustrationSpreads(content.chapters[chapter].html);paintedPage=-1;
    layout(fraction);
  }

  function cancelTurn() { animation?.cancel();animation=null;overlay?.remove();overlay=null;turning=false; }
  async function turn(direction) {
    if(turning||disposed||coach.isPaused())return;
    if(direction<0 && page===0 && chapter===0)return;
    if(direction>0 && page===count-1 && chapter===content.chapters.length-1) {
      const justFinished=!book.finished;
      finishReadingSession(book);stopPlaying();persist();paint();announce('Book finished. Well done!');
      if(justFinished)completion.show(completionRecap(coach.observations()));
      return;
    }
    pageTurnSound.play();
    turning=true;paint();
    // A visual copy turns above the real text; it is excluded from accessibility.
    overlay=sheet.cloneNode(true);overlay.removeAttribute('id');
    overlay.querySelectorAll('[id]').forEach(el=>el.removeAttribute('id'));
    overlay.setAttribute('aria-hidden','true');overlay.inert=true;overlay.classList.add('turning-sheet');
    reader.append(overlay);
    if(direction>0) {
      if(page<count-1){page++;paint();persist();}else await loadChapter(chapter+1,0);
    } else {
      if(page>0){page--;paint();persist();}else await loadChapter(chapter-1,1);
    }
    if(disposed)return;
    if(!reduced.matches) {
      if(direction<0){overlay.remove();overlay=sheet.cloneNode(true);overlay.removeAttribute('id');overlay.querySelectorAll('[id]').forEach(el=>el.removeAttribute('id'));overlay.setAttribute('aria-hidden','true');overlay.inert=true;overlay.classList.add('turning-sheet');reader.append(overlay);}
      animation=overlay.animate(direction>0 ? [
        {transform:'rotateY(0deg)',filter:'brightness(1)',opacity:1},
        {transform:'rotateY(-105deg)',filter:'brightness(.75)',opacity:0}
      ] : [
        {transform:'rotateY(-105deg)',filter:'brightness(.75)',opacity:0},
        {transform:'rotateY(0deg)',filter:'brightness(1)',opacity:1}
      ],{duration:520,easing:'cubic-bezier(.3,.1,.25,1)',fill:'forwards'});
      try{await animation.finished;}catch{/* Resizing or leaving cancels the turn. */}
    }
    cancelTurn();if(!disposed)paint();
  }
  main.querySelector('#reader-finish').onclick=()=>{finishReadingSession(book);stopPlaying();persist();paint();completion.show(completionRecap(coach.observations()));announce('Book completed and saved.');};
  function startPlaying(){
    if(playTimer || disposed || coach.isPaused())return;
    narration.resume?.();
    play.textContent='Ⅱ';play.setAttribute('aria-label','Pause automatic page turns');play.title='Pause automatic page turns';
    main.querySelector('#player-mode').textContent='Auto-turn · waits for narration';
    playTimer=setInterval(()=>{if(!narration.isPlaying?.())turn(1);},12000);
  }
  play.onclick=()=>{if(playTimer)stopPlaying();else startPlaying();};
  seek.oninput=()=>{
    if(imageOnly){
      const position=Math.max(0,Math.min(content.chapters.length-0.001,Number(seek.value)));
      const target=Math.floor(position);stopPlaying();cancelTurn();
      if(target!==chapter){pageTurnSound.play();loadChapter(target,0);}else narration.seek?.(position-target);
      return;
    }
    if(Number(seek.value)-1!==page)pageTurnSound.play();stopPlaying();cancelTurn();page=Number(seek.value)-1;paint();persist();};
  const fullscreen=main.querySelector('#reader-fullscreen');
  fullscreen.hidden=!document.fullscreenEnabled;
  fullscreen.onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await player.closest('.workspace').requestFullscreen();}catch{announce('Fullscreen is unavailable in this browser.');}};
  const fullscreenChanged=()=>fullscreen.setAttribute('aria-label',document.fullscreenElement?'Exit fullscreen':'Enter fullscreen');
  document.addEventListener('fullscreenchange',fullscreenChanged);
  previous.onclick=()=>{stopPlaying();turn(-1);};next.onclick=()=>{stopPlaying();turn(1);};
  chapterSelect.onchange=()=>{pageTurnSound.play();stopPlaying();cancelTurn();loadChapter(Number(chapterSelect.value),0);};
  main.querySelector('#reader-size').onchange=event=>{
    cancelTurn();book.textSize=Number(event.target.value);reader.style.fontSize=book.textSize+'px';layout(book.pageFraction||0);
  };
  reader.onkeydown=event=>{if(event.key==='ArrowRight'||event.key==='ArrowLeft'){event.preventDefault();stopPlaying();turn(event.key==='ArrowRight'?1:-1);}};
  let start=null;
  reader.addEventListener('pointerdown',event=>{if(event.pointerType==='touch')start={x:event.clientX,y:event.clientY};});
  reader.addEventListener('pointerup',event=>{if(!start)return;const dx=event.clientX-start.x,dy=event.clientY-start.y;start=null;if(Math.abs(dx)>60&&Math.abs(dx)>Math.abs(dy)*1.5){stopPlaying();turn(dx<0?1:-1);}});
  reader.addEventListener('pointercancel',()=>{start=null;});
  let lastWidth=0,lastHeight=0;
  const observer=new ResizeObserver(()=>{
    if(windowEl.clientWidth===lastWidth&&windowEl.clientHeight===lastHeight)return;
    lastWidth=windowEl.clientWidth;lastHeight=windowEl.clientHeight;
    cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>{if(!disposed){cancelTurn();layout(book.pageFraction||0);}});
  });
  // Decode before measuring columns so illustrations cannot move the bookmark.
  const initialFraction=book.pageFraction||0;
  loadChapter(chapter,initialFraction).then(()=>{if(!disposed){observer.observe(windowEl);startPlaying();}});
  return ()=>{persist();completion.dispose();pageTurnSound.dispose();coach.dispose();stopPlaying();narration.dispose();document.removeEventListener('fullscreenchange',fullscreenChanged);disposed=true;generation++;observer.disconnect();cancelAnimationFrame(resizeFrame);cancelTurn();};
}
