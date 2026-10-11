"""Fetch the curated local library; preserve each complete Gutenberg EPUB and notices."""
import hashlib
import html
import json
import posixpath
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'web/learn/books/catalog'
BOOKS = [
    (17104, 'rocket-book', 'The Rocket Book', 'Peter Newell', 'A mischievous rocket zooms upstairs through one surprising scene after another.'),
    (10607, 'real-mother-goose', 'The Real Mother Goose', 'Traditional nursery rhymes', 'A collection of playful nursery rhymes.'),
    (11757, 'velveteen-rabbit', 'The Velveteen Rabbit', 'Margery Williams', 'A toy rabbit discovers the meaning of being loved.'),
    (67098, 'winnie-the-pooh', 'Winnie-the-Pooh', 'A. A. Milne', 'Visit Pooh and his friends in the Hundred Acre Wood.'),
    (11, 'alice-in-wonderland', "Alice’s Adventures in Wonderland", 'Lewis Carroll', 'Follow Alice down the rabbit hole into a curious world.'),
    (55, 'wizard-of-oz', 'The Wonderful Wizard of Oz', 'L. Frank Baum', 'Join Dorothy and her companions on the road to Oz.'),
    (289, 'wind-in-the-willows', 'The Wind in the Willows', 'Kenneth Grahame', 'Riverbank adventures with Mole, Rat, Badger and Toad.'),
    (113, 'secret-garden', 'The Secret Garden', 'Frances Hodgson Burnett', 'Discover a hidden garden and a growing friendship.'),
]


def build_hey_diddle(source):
    """Extract one complete rhyme; keep its illustration and original license."""
    with zipfile.ZipFile(source) as archive:
        poem = None
        notices = []
        for name in archive.namelist():
            if not name.endswith('.xhtml'):
                continue
            document = ET.fromstring(archive.read(name))
            for node in document.iter():
                if node.get('id') in ('pg-header', 'pg-footer'):
                    notices.append(''.join(node.itertext()))
                if node.get('id') == 'a128':
                    poem = node
                    poem_path = name
        if poem is None or not notices:
            raise ValueError('Mother Goose source no longer contains the expected rhyme/notices')
        lines = [line.strip() for line in ''.join(poem.itertext()).splitlines() if line.strip()]
        if lines[0] != 'THE CAT AND THE FIDDLE' or len(lines) != 7:
            raise ValueError('Verify Hey Diddle Diddle source before rebuilding')
        lines = lines[1:]
        illustration = poem.find('.//{*}img')
        image_path = posixpath.normpath(posixpath.join(posixpath.dirname(poem_path), illustration.get('src')))
        image = archive.read(image_path)
    target = DEST / 'hey-diddle-diddle.epub'
    (DEST / 'hey-diddle-diddle.jpg').write_bytes(image)
    def xhtml(title, body):
        return f'<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title></head><body>{body}</body></html>'
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as out:
        out.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        out.writestr('META-INF/container.xml', '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        out.writestr('OEBPS/cover.jpg', image)
        items = '<item id="cover" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/><item id="notices" href="notices.xhtml" media-type="application/xhtml+xml"/>'
        spine = ''
        for index in range(3):
            title = ['The cat and the fiddle', 'The cow and the moon', 'The dish and the spoon'][index]
            body = f'<h1>{title}</h1>'
            if index == 0:
                body += '<img src="cover.jpg" alt="A cat plays a fiddle, a cow leaps over the moon, and a dish runs with a spoon. Illustration by Blanche Fisher Wright."/>'
            body += '<p>' + '<br/>'.join(html.escape(line) for line in lines[index*2:index*2+2]) + '</p>'
            out.writestr(f'OEBPS/scene{index}.xhtml', xhtml(title, body))
            items += f'<item id="scene{index}" href="scene{index}.xhtml" media-type="application/xhtml+xml"/>'
            spine += f'<itemref idref="scene{index}"/>'
        attribution = 'Hey Diddle Diddle (The Cat and the Fiddle), a traditional nursery rhyme. Illustration by Blanche Fisher Wright, from The Real Mother Goose, Project Gutenberg ebook 10607. Magneto excerpt: the complete rhyme is unchanged and split across three reading sections. Original source EPUB retained beside this file.'
        out.writestr('OEBPS/notices.xhtml', xhtml('Source and license', '<h1>Source and license</h1><p>' + html.escape(attribution) + '</p><pre>' + html.escape('\n\n'.join(notices)) + '</pre>'))
        out.writestr('OEBPS/nav.xhtml', '<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head><body><nav epub:type="toc"><ol>' + ''.join(f'<li><a href="scene{i}.xhtml">Scene {i+1}</a></li>' for i in range(3)) + '<li><a href="notices.xhtml">Source and license</a></li></ol></nav></body></html>')
        out.writestr('OEBPS/content.opf', '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" version="3.0" unique-identifier="id"><metadata><dc:identifier id="id">magneto-hey-diddle-diddle-v1</dc:identifier><dc:title>Hey Diddle Diddle</dc:title><dc:creator>Traditional · illustrated by Blanche Fisher Wright</dc:creator><dc:language>en</dc:language><dc:rights>Public domain in the USA.</dc:rights><dc:source>https://www.gutenberg.org/ebooks/10607</dc:source><meta property="dcterms:modified">2026-10-11T00:00:00Z</meta></metadata><manifest>' + items + '</manifest><spine>' + spine + '<itemref idref="notices" linear="no"/></spine></package>')
    return dict(id='catalog-10607-hey-diddle', title='Hey Diddle Diddle', author='Traditional · illustrated by Blanche Fisher Wright', description='A cat, a cow and a runaway spoon in a tiny, playful rhyme.', file='./books/catalog/hey-diddle-diddle.epub', cover='./books/catalog/hey-diddle-diddle.jpg', source='https://www.gutenberg.org/ebooks/10607', rights='Public domain in the USA.', sha256=hashlib.sha256(target.read_bytes()).hexdigest(), source_epub='./books/catalog/real-mother-goose.epub')


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    catalog = []
    for number, slug, title, author, description in BOOKS:
        url = f'https://www.gutenberg.org/ebooks/{number}.epub3.images'
        path = DEST / f'{slug}.epub'
        if not path.exists():
            request = urllib.request.Request(url, headers={'User-Agent': 'Magneto-local-library/1.0'})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read(25 * 1024 * 1024 + 1)
            if len(data) > 25 * 1024 * 1024:
                raise ValueError(f'{title}: EPUB too large')
            # Validate before publishing to the local library.
            import io
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                assert archive.read('mimetype') == b'application/epub+zip'
            path.write_bytes(data)
        with zipfile.ZipFile(path) as archive:
            container = ET.fromstring(archive.read('META-INF/container.xml'))
            package = container.find('.//{*}rootfile').attrib['full-path']
            doc = ET.fromstring(archive.read(package))
            rights = doc.find('.//{*}rights').text or ''
            if 'public domain in the usa' not in rights.lower():
                raise ValueError(f'{title}: verify rights metadata before bundling')
            items = doc.findall('.//{*}manifest/{*}item')
            cover = next((item for item in items if 'cover-image' in item.get('properties', '').split()), None)
            if cover is None:
                cover_id = next((m.get('content') for m in doc.findall('.//{*}meta') if m.get('name') == 'cover'), None)
                cover = next((item for item in items if item.get('id') == cover_id), None)
            cover_url = ''
            if cover is not None:
                cover_path = posixpath.normpath(posixpath.join(posixpath.dirname(package), cover.get('href')))
                ext = Path(cover_path).suffix.lower()
                if ext in ('.jpg', '.jpeg', '.png'):
                    (DEST / f'{slug}{ext}').write_bytes(archive.read(cover_path))
                    cover_url = f'./books/catalog/{slug}{ext}'
        catalog.append(build_hey_diddle(path) if number == 10607 else dict(id=f'catalog-{number}', title=title, author=author, description=description,
                            file=f'./books/catalog/{slug}.epub', cover=cover_url,
                            source=f'https://www.gutenberg.org/ebooks/{number}', rights=rights,
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        print(f'{title}: {path.stat().st_size} bytes')
    local_books = DEST / 'local-books.json'
    if local_books.exists():
        catalog = json.loads(local_books.read_text()) + catalog
    (ROOT / 'web/learn/book-catalog.js').write_text(
        '// Generated by scripts/fetch_children_books.py. EPUBs retain original notices.\n'
        'export const childrenBooks = ' + json.dumps(catalog, ensure_ascii=False, indent=2) + ';\n')


if __name__ == '__main__':
    main()
