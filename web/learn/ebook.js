// Local-only EPUB/TXT reader. EPUB scripts, styles, and network resources are omitted.
const decoder = new TextDecoder();
const esc = text => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const xml = text => { const doc = new DOMParser().parseFromString(text, 'application/xml'); if (doc.querySelector('parsererror')) throw Error('This EPUB contains invalid XML.'); return doc; };
const nodes = (doc, name) => [...doc.getElementsByTagNameNS('*', name)];
const resolve = (base, href) => { const url = new URL(href, 'https://ebook.invalid/' + base); if (url.origin !== 'https://ebook.invalid') return ''; return decodeURIComponent(url.pathname.slice(1)); };
async function unzip(buffer) {
  const view = new DataView(buffer), bytes = new Uint8Array(buffer), entries = new Map();
  let end = bytes.length - 22;
  while (end >= Math.max(0, bytes.length - 65557) && view.getUint32(end, true) !== 0x06054b50) end--;
  if (end < 0 || view.getUint32(end, true) !== 0x06054b50) throw Error('This file is not a readable EPUB archive.');
  const count = view.getUint16(end + 10, true); let offset = view.getUint32(end + 16, true), total = 0;
  if (count > 4000) throw Error('This EPUB has too many files.');
  for (let i = 0; i < count; i++) {
    if (view.getUint32(offset, true) !== 0x02014b50) throw Error('Invalid EPUB archive.');
    const flags = view.getUint16(offset+8,true), method = view.getUint16(offset+10,true), size = view.getUint32(offset+20,true), unpacked = view.getUint32(offset+24,true);
    const length = view.getUint16(offset+28,true), extra = view.getUint16(offset+30,true), comment = view.getUint16(offset+32,true), local = view.getUint32(offset+42,true);
    const name = decoder.decode(bytes.slice(offset+46,offset+46+length));
    total += unpacked;
    if (total > 80*1024*1024 || unpacked > 12*1024*1024) throw Error('This EPUB is too large after decompression.');
    entries.set(name, async () => {
      if (flags & 1) throw Error('Encrypted ebooks are not supported. Import a DRM-free EPUB.');
      if (view.getUint32(local,true) !== 0x04034b50) throw Error('Invalid EPUB entry.');
      const start = local + 30 + view.getUint16(local+26,true) + view.getUint16(local+28,true);
      if (start+size > bytes.length) throw Error('Incomplete EPUB entry.');
      const raw = bytes.slice(start,start+size);
      if (method === 0) return raw;
      if (method !== 8) throw Error('Unsupported EPUB compression.');
      let stream;
      try { stream = new Blob([raw]).stream().pipeThrough(new DecompressionStream('deflate-raw')); }
      catch { throw Error('This browser cannot decompress EPUB files. Try a current browser or import plain text.'); }
      const reader = stream.getReader(), chunks = []; let length = 0;
      while (true) { const {value, done} = await reader.read(); if (done) break; length += value.length; if (length > unpacked || length > 12*1024*1024) { await reader.cancel(); throw Error('Invalid EPUB entry size.'); } chunks.push(value); }
      return new Uint8Array(await new Blob(chunks).arrayBuffer());
    });
    offset += 46+length+extra+comment;
  }
  return entries;
}
export async function importEbook(file) {
  if (file.size > 25*1024*1024) throw Error('Choose a book smaller than 25 MB.');
  if (/\.txt$/i.test(file.name)) {
    const text = await file.text(); if (!text.trim()) throw Error('This text file is empty.');
    const paragraphs = text.split(/\n\s*\n/), chapters = []; let chunk = '';
    for (const paragraph of paragraphs) { chunk += paragraph + '\n\n'; if (chunk.length > 5000) { chapters.push({title:`Reading section ${chapters.length+1}`,html:`<p>${esc(chunk).replace(/\n/g,'<br>')}</p>`}); chunk=''; } }
    if (chunk) chapters.push({title:`Reading section ${chapters.length+1}`,html:`<p>${esc(chunk).replace(/\n/g,'<br>')}</p>`});
    return {title:file.name.replace(/\.txt$/i,''),author:'',chapters,cover:''};
  }
  if (!/\.epub$/i.test(file.name)) throw Error('Choose a DRM-free .epub or .txt file.');
  const archive = await unzip(await file.arrayBuffer());
  const read = async path => { if (!archive.has(path)) throw Error('A required EPUB file is missing.'); return decoder.decode(await archive.get(path)()); };
  const container = xml(await read('META-INF/container.xml'));
  const packagePath = nodes(container,'rootfile')[0]?.getAttribute('full-path');
  const packageDoc = xml(await read(packagePath));
  const items = new Map(nodes(packageDoc,'item').map(el=>[el.getAttribute('id'),el]));
  const images = new Map();
  async function image(path) {
    if (images.has(path)) return images.get(path);
    const type = /\.png$/i.test(path)?'image/png':/\.jpe?g$/i.test(path)?'image/jpeg':/\.gif$/i.test(path)?'image/gif':/\.webp$/i.test(path)?'image/webp':'';
    if (!type || !archive.has(path)) return '';
    const bytes = await archive.get(path)();
    const data = await new Promise((resolve,reject)=>{ const reader = new FileReader(); reader.onload=()=>resolve(reader.result); reader.onerror=reject; reader.readAsDataURL(new Blob([bytes],{type})); });
    images.set(path,data); return data;
  }
  const allowed = new Set('p div span h1 h2 h3 h4 h5 h6 em strong b i u s blockquote ul ol li br hr figure figcaption table thead tbody tr th td sub sup pre code'.split(' '));
  async function clean(node, path) {
    if (node.nodeType === 3) return esc(node.textContent);
    if (node.nodeType !== 1) return '';
    const tag = node.localName.toLowerCase();
    if (['script','style','iframe','object','embed','form','input','button','audio','video','link'].includes(tag)) return '';
    if (tag === 'img' || tag === 'image') {
      const href = node.getAttribute('src') || node.getAttribute('href') || node.getAttribute('xlink:href');
      const src = href ? await image(resolve(path,href)) : '';
      return src ? `<img src="${src}" alt="${esc(node.getAttribute('alt')||'Book illustration')}" data-source-image-id="${esc(node.getAttribute('id')||'')}">` : '';
    }
    const content = (await Promise.all([...node.childNodes].map(child=>clean(child,path)))).join('');
    if (!allowed.has(tag)) return content;
    return ['br','hr'].includes(tag) ? `<${tag}>` : `<${tag}>${content}</${tag}>`;
  }
  const chapters = [];
  for (const ref of nodes(packageDoc,'itemref')) {
    if (ref.getAttribute('linear') === 'no') continue;
    const item = items.get(ref.getAttribute('idref')); if (!item) continue;
    const path = resolve(packagePath,item.getAttribute('href'));
    const doc = xml(await read(path)), body = nodes(doc,'body')[0]; if (!body) continue;
    const html = await clean(body,path);
    if (html.trim()) chapters.push({title:(nodes(doc,'h1')[0]||nodes(doc,'h2')[0]||nodes(doc,'title')[0])?.textContent.trim()||`Reading section ${chapters.length+1}`,html});
  }
  if (!chapters.length) throw Error('No readable chapters found. The book may be protected or unsupported.');
  const coverId = nodes(packageDoc,'meta').find(el=>el.getAttribute('name') === 'cover')?.getAttribute('content');
  const coverItem = [...items.values()].find(el=>(el.getAttribute('properties')||'').split(' ').includes('cover-image')) || items.get(coverId);
  const cover = coverItem ? await image(resolve(packagePath,coverItem.getAttribute('href'))) : '';
  return {title:nodes(packageDoc,'title')[0]?.textContent||file.name,author:nodes(packageDoc,'creator')[0]?.textContent||'',chapters,cover};
}
export function ebookStore(action, id, data) {
  return new Promise((resolve,reject)=>{
    const request = indexedDB.open('magneto-ebooks-v1',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('books');
    request.onerror=()=>reject(Error('Book storage is unavailable.'));
    request.onsuccess=()=>{
      const db=request.result, transaction=db.transaction('books',action==='get'?'readonly':'readwrite'), store=transaction.objectStore('books');
      const operation=action==='get'?store.get(id):action==='put'?store.put(data,id):store.delete(id);
      transaction.oncomplete=()=>{ db.close(); resolve(operation.result); };
      transaction.onabort=transaction.onerror=()=>{ db.close(); reject(Error('Could not save this ebook. Browser storage may be full.')); };
    };
  });
}
