// Reading presentation for the bundled edition. The EPUB and its notices remain intact.
export const PETER_READING_VERSION = 'title-first-2';
export function preparePeterReading(content, checkpointMap) {
  const index = content.chapters.findIndex(chapter => {
    const root = new DOMParser().parseFromString(chapter.html, 'text/html').body;
    return [...root.querySelectorAll('p')].some(p => p.textContent.trim().startsWith('Once upon a time there were four little Rabbits'));
  });
  if (index < 0) throw Error('Peter Rabbit reading layout changed. Review the bundled edition.');
  const root = new DOMParser().parseFromString(content.chapters[index].html, 'text/html').body;
  const title = [...root.querySelectorAll('h1')].find(h => /THE TALE OF\s*PETER RABBIT/i.test(h.textContent));
  const opening = [...root.querySelectorAll('p')].find(p => p.textContent.trim().startsWith('Once upon a time there were four little Rabbits'));
  if (!title || title.parentElement !== root || opening.parentElement !== root) throw Error('Unexpected Peter Rabbit page structure.');
  const notices = document.createElement('div');
  let titleImage = title.previousElementSibling;
  while (titleImage && !titleImage.querySelector('img') && titleImage.tagName !== 'IMG') titleImage = titleImage.previousElementSibling;
  if (!titleImage) throw Error('Peter Rabbit title illustration is missing.');
  while (root.firstChild !== titleImage) notices.append(root.firstChild);
  // Retain the small rabbit illustration immediately before the first story paragraph.
  let storyImage = opening.previousElementSibling;
  while (storyImage && !storyImage.querySelector('img') && storyImage.tagName !== 'IMG') storyImage = storyImage.previousElementSibling;
  if (!storyImage || storyImage === titleImage) throw Error('Peter Rabbit story illustration is missing.');
  let next = storyImage.nextSibling;
  while (next && next !== opening) { const node = next; next = next.nextSibling; notices.append(node); }
  const invitation = document.createElement('p');
  invitation.textContent = 'A little rabbit. A very big adventure.';
  root.insertBefore(invitation, storyImage);
  if(checkpointMap?.schema_version!=='1.0' || checkpointMap.book_id!=='builtin-peter-rabbit')throw Error('Invalid Peter Rabbit checkpoint map.');
  const sourceImages=[...root.querySelectorAll('img')];
  const seen=new Set();
  for(const page of checkpointMap.pages){
    const matches=sourceImages.filter(img=>img.dataset.sourceImageId===page.source_image_id);
    if(matches.length!==1 || seen.has(page.id))throw Error('Peter Rabbit edition changed. Review stable page anchors.');
    matches[0].dataset.storyPageId=page.id;seen.add(page.id);
  }
  if(sourceImages.length!==seen.size || checkpointMap.checkpoints.some(c=>!seen.has(c.page_id)))throw Error('Checkpoint map does not match this edition.');
  const chapters = content.chapters.map((chapter, i) => i === index ? {...chapter, html:root.innerHTML} : chapter);
  chapters.push({title:'Publication details', html:notices.innerHTML});
  return {...content, chapters, readingStart:index, checkpoints:checkpointMap.checkpoints};
}
