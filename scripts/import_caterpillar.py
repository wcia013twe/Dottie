"""Package the user-supplied scanned PDF for the existing local EPUB reader."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZIP_STORED, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
def main():
    source = Path(sys.argv[1])
    dest = ROOT / 'web/learn/books/catalog'
    dest.mkdir(parents=True, exist_ok=True)
    slug = 'very-hungry-caterpillar'
    shutil.copyfile(source, dest / f'{slug}.pdf')
    with tempfile.TemporaryDirectory() as temp:
        subprocess.run(['pdftoppm', '-scale-to', '1600', '-jpeg', '-jpegopt', 'quality=90', str(source), str(Path(temp)/'page')], check=True)
        pages = sorted(Path(temp).glob('page-*.jpg'))
        if not pages:
            raise ValueError('No PDF pages rendered')
        shutil.copyfile(pages[0], dest / f'{slug}.jpg')
        with ZipFile(dest / f'{slug}.epub', 'w', ZIP_DEFLATED) as out:
            out.writestr('mimetype', 'application/epub+zip', compress_type=ZIP_STORED)
            out.writestr('META-INF/container.xml', '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
            items, spine = [], []
            for i, page in enumerate(pages, 1):
                out.write(page, f'OEBPS/images/page-{i}.jpg')
                out.writestr(f'OEBPS/page-{i}.xhtml', f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Page {i} of {len(pages)}</title></head><body><img src="images/page-{i}.jpg" alt="Scanned book page {i}; original words are part of the image."/></body></html>')
                items.append(f'<item id="p{i}" href="page-{i}.xhtml" media-type="application/xhtml+xml"/><item id="i{i}" href="images/page-{i}.jpg" media-type="image/jpeg"/>')
                spine.append(f'<itemref idref="p{i}"/>')
            out.writestr('OEBPS/content.opf', '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" version="2.0" unique-identifier="id"><metadata><dc:identifier id="id">user-caterpillar-scan-v1</dc:identifier><dc:title>The Very Hungry Caterpillar</dc:title><dc:creator>Eric Carle</dc:creator><dc:language>en</dc:language><dc:rights>Copyrighted work. User-supplied PDF for local reading; no redistribution license asserted.</dc:rights><meta name="cover" content="i1"/></metadata><manifest>'+''.join(items)+'</manifest><spine>'+''.join(spine)+'</spine></package>')
    entry = dict(id='local-very-hungry-caterpillar', title='The Very Hungry Caterpillar', author='Eric Carle', description='Your scanned book · 26 original pages · narrated picture descriptions.', file=f'./books/catalog/{slug}.epub', cover=f'./books/catalog/{slug}.jpg', source=f'./books/catalog/{slug}.pdf', sourceLabel='Original PDF', rights='User-supplied copyrighted book; local reading.', sha256=hashlib.sha256((dest/f'{slug}.epub').read_bytes()).hexdigest())
    (dest/'local-books.json').write_text(json.dumps([entry], indent=2)+'\n')
    catalog_path = ROOT/'web/learn/book-catalog.js'
    catalog = json.loads(catalog_path.read_text().split('export const childrenBooks = ',1)[1].rstrip().removesuffix(';'))
    catalog = [b for b in catalog if b['id'] != entry['id']]
    catalog_path.write_text('// Generated catalog, including user-supplied local books.\nexport const childrenBooks = '+json.dumps([entry]+catalog, ensure_ascii=False, indent=2)+';\n')
if __name__ == '__main__':
    main()
