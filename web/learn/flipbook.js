import { mountNarration } from './narration.js?v=restored-narration-1';
import { mountStoryCoach } from './story-coach.js?v=restored-narration-1';
import { completionRecap, mountStoryCompletion } from './story-completion.js';
// Pair each illustration with the following passage in the EPUB reading order.
function illustrationSpreads(html) {
  const root = new DOMParser().parseFromString(html, 'text/html').body;
  const spreads = []; let passage = '', image = ''; 
  function visit(node) {
    if (node.nodeType === 3) { if (node.textContent.trim()) { const p=document.createElement('p');p.textContent=node.textContent;passage+=p.outerHTML; } return; }
    if (node.nodeType !== 1) return;
    if (node.tagName === 'IMG') { if(image || passage.trim())spreads.push({image,html:passage});image=node.outerHTML;passage='';return; }
    if (node.querySelector('img') || ['DIV','SECTION','ARTICLE','FIGURE'].includes(node.tagName)) { [...node.childNodes].forEach(visit);return; }
    passage += node.outerHTML;
  }
  [...root.childNodes].forEach(visit);
  if (image || passage.trim()) spreads.push({image,html:passage});
  return spreads.length ? spreads : [{image:'',html:html}];
}
// Browser-native pagination; the imported chapter remains accessible text.
export function mountFlipbook({main, book, content, save, announce}) {
  const reader=main.querySelector('#ebook-content'), sheet=main.querySelector('#book-sheet');
  const windowEl=main.querySelector('#page-window'), text=main.querySelector('#page-text');
  const previous=main.querySelector('#reader-prev'), next=main.querySelector('#reader-next');
  const status=main.querySelector('#reader-feedback'), chapterSelect=main.querySelector('#reader-chapter');
  const seek=main.querySelector('#reader-seek'), play=main.querySelector('#reader-play'), player=main.querySelector('.book-player');
  let spreads=[], paintedPage=-1;
  reader.classList.add('spread-reader');
  const illustration=document.createElement('div');illustration.className='spread-illustration';sheet.prepend(illustration);
  let playTimer=null, narration=null;
  function stopPlaying(pauseAudio=true){if(pauseAudio)narration?.pause();clearInterval(playTimer);playTimer=null;play.textContent='▶';play.setAttribute('aria-label','Play automatic page turns');main.querySelector('#player-mode').textContent='Read at your own pace';}
  let chapter=Math.min(book.position||0,content.chapters.length-1), page=0, count=1, stride=0;
  let turning=false, disposed=false, animation=null, overlay=null, resizeFrame=0, generation=0;
  if (book.finished === undefined) book.finished = book.current === book.total;
  let legacyScroll = book.pageFraction === undefined ? (book.scroll || 0) : 0;
  const coach=mountStoryCoach({player,enabled:book.bundled,pause:()=>{stopPlaying();window.speechSynthesis?.pause();}});
  narration=mountNarration({player,bookId:book.id,onPlay:()=>stopPlaying(false)});
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
      windowEl.scrollTop=0;paintedPage=page;coach.context(text.textContent);narration.context(text.textContent);
    }
    previous.disabled=coach.isPaused() || (chapter===0 && page===0);
    next.disabled=coach.isPaused();
    previous.setAttribute('aria-disabled',String(turning || previous.disabled));
    next.setAttribute('aria-disabled',String(turning));
    next.textContent=chapter===content.chapters.length-1 && page===count-1?'✓':'❯';
    next.setAttribute('aria-label',chapter===content.chapters.length-1 && page===count-1?'Finish book':'Next page');
    seek.max=String(count);seek.value=String(page+1);seek.setAttribute('aria-valuetext',`Page ${page+1} of ${count}`);seek.style.setProperty('--progress',`${count>1?page/(count-1)*100:0}%`);
    status.textContent=book.finished?'Book finished.':`Page ${page+1} of ${count} · ${content.chapters[chapter].title}`;
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
      book.finished=true;stopPlaying();persist();paint();announce('Book finished. Well done!');
      if(justFinished)completion.show(completionRecap(coach.observations()));
      return;
    }
    book.finished=false;turning=true;paint();
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
  play.onclick=()=>{narration.pause();if(playTimer){stopPlaying();return;}play.textContent='Ⅱ';play.setAttribute('aria-label','Pause automatic page turns');main.querySelector('#player-mode').textContent='Auto-turn · 12 seconds per page';playTimer=setInterval(()=>turn(1),12000);};
  seek.oninput=()=>{stopPlaying();cancelTurn();page=Number(seek.value)-1;book.finished=false;paint();persist();};
  const fullscreen=main.querySelector('#reader-fullscreen');
  fullscreen.hidden=!document.fullscreenEnabled;
  fullscreen.onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await player.closest('.workspace').requestFullscreen();}catch{announce('Fullscreen is unavailable in this browser.');}};
  const fullscreenChanged=()=>fullscreen.setAttribute('aria-label',document.fullscreenElement?'Exit fullscreen':'Enter fullscreen');
  document.addEventListener('fullscreenchange',fullscreenChanged);
  previous.onclick=()=>{stopPlaying();turn(-1);};next.onclick=()=>{stopPlaying();turn(1);};
  chapterSelect.onchange=()=>{stopPlaying();cancelTurn();book.finished=false;loadChapter(Number(chapterSelect.value),0);};
  main.querySelector('#reader-size').onchange=event=>{
    cancelTurn();book.textSize=Number(event.target.value);reader.style.fontSize=book.textSize+'px';layout(book.pageFraction||0);
  };
  reader.onkeydown=event=>{if(event.key==='ArrowRight'||event.key==='ArrowLeft'){event.preventDefault();stopPlaying();turn(event.key==='ArrowRight'?1:-1);}};
  let start=null;
  reader.addEventListener('pointerdown',event=>{if(event.pointerType==='touch')start={x:event.clientX,y:event.clientY};});
  reader.addEventListener('pointerup',event=>{if(!start)return;const dx=event.clientX-start.x,dy=event.clientY-start.y;start=null;if(Math.abs(dx)>60&&Math.abs(dx)>Math.abs(dy)*1.5)turn(dx<0?1:-1);});
  reader.addEventListener('pointercancel',()=>{start=null;});
  let lastWidth=0,lastHeight=0;
  const observer=new ResizeObserver(()=>{
    if(windowEl.clientWidth===lastWidth&&windowEl.clientHeight===lastHeight)return;
    lastWidth=windowEl.clientWidth;lastHeight=windowEl.clientHeight;
    cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>{if(!disposed){cancelTurn();layout(book.pageFraction||0);}});
  });
  // Decode before measuring columns so illustrations cannot move the bookmark.
  const initialFraction=book.pageFraction||0;
  loadChapter(chapter,initialFraction).then(()=>{if(!disposed)observer.observe(windowEl);});
  return ()=>{completion.dispose();coach.dispose();stopPlaying();narration.dispose();document.removeEventListener('fullscreenchange',fullscreenChanged);disposed=true;generation++;observer.disconnect();cancelAnimationFrame(resizeFrame);cancelTurn();};
}
