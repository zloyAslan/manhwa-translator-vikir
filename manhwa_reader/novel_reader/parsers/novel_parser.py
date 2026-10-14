"""
Parsers for Novel Reader (EPUB, DOCX, TXT).
Extracts chapters and plain text suitable for clean display and translation.
"""

import re
import zipfile
import html
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import docx
except ImportError:
    docx = None


def clean_html_text(raw_html: str) -> str:
    """Strip HTML tags and CSS/script blocks while preserving line breaks and paragraph spacing."""
    if not raw_html:
        return ""
    # Strip <style>...</style>, <script>...</script>, and <head>...</head> blocks
    text = re.sub(r'<(style|script|head)[^>]*>.*?</\1>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
    # Strip any loose or malformed style tags
    text = re.sub(r'<\/?style[^>]*>', '', text, flags=re.IGNORECASE)
    # Convert block/break tags to newlines
    text = re.sub(r'<(br|p|div|h[1-6]|tr|li)[^>]*>', '\n', text, flags=re.IGNORECASE)
    # Strip all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    # Normalize multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class EpubParser:
    """Parser for EPUB novel files using standard zipfile and xml parsing (no heavy external deps needed)."""
    
    @staticmethod
    def extract_chapters(epub_path: Path) -> List[Dict[str, Any]]:
        """
        Extracts chapters from an EPUB file.
        Uses toc.ncx/nav.xhtml when available to get true chapter titles,
        and filters out covers, table of contents, and ads.
        """
        chapters = []
        if not epub_path.exists():
            return chapters

        SKIP_FILENAMES = {
            'cover.xhtml', 'cover.html', 'title-page.xhtml', 'titlepage.xhtml',
            'title_page.xhtml', 'contents.xhtml', 'contents.html', 'toc.xhtml',
            'toc.html', 'jnovels.xhtml', 'jnovels.html', 'ad.xhtml', 'ads.xhtml'
        }
        SKIP_TITLES = {
            'cover', 'title page', 'contents', 'table of contents',
            'copyright', 'advertisement', 'about this book'
        }

        try:
            with zipfile.ZipFile(epub_path, 'r') as z:
                # 1. Parse container.xml to locate root OPF
                container_data = z.read("META-INF/container.xml")
                root = ET.fromstring(container_data)
                rootfile = root.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile")
                if rootfile is None:
                    return chapters
                opf_path = rootfile.attrib.get("full-path", "")
                opf_dir = str(Path(opf_path).parent) if Path(opf_path).parent != Path(".") else ""

                # 2. Parse OPF
                opf_data = z.read(opf_path)
                opf_root = ET.fromstring(opf_data)
                
                ns = {'pkg': 'http://www.idpf.org/2007/opf'}
                manifest = {}
                ncx_href = None
                for item in opf_root.findall(".//pkg:manifest/pkg:item", ns) or opf_root.findall(".//{http://www.idpf.org/2007/opf}item"):
                    item_id = item.attrib.get("id")
                    href = item.attrib.get("href")
                    media_type = item.attrib.get("media-type", "")
                    manifest[item_id] = href
                    if media_type == "application/x-dtbncx+xml" or href.endswith(".ncx"):
                        ncx_href = href

                spine_items = []
                for itemref in opf_root.findall(".//pkg:spine/pkg:itemref", ns) or opf_root.findall(".//{http://www.idpf.org/2007/opf}itemref"):
                    idref = itemref.attrib.get("idref")
                    if idref in manifest:
                        spine_items.append(manifest[idref])

                # 3. Build TOC Title Map from NCX or NAV
                toc_map: Dict[str, str] = {}
                # Locate NCX file
                ncx_candidates = []
                if ncx_href:
                    ncx_full = f"{opf_dir}/{ncx_href}".lstrip("/") if opf_dir else ncx_href
                    ncx_candidates.append(ncx_full)
                ncx_candidates.extend([f for f in z.namelist() if f.lower().endswith(".ncx")])

                for ncx_file in ncx_candidates:
                    if ncx_file in z.namelist():
                        try:
                            ncx_xml = z.read(ncx_file)
                            ncx_root = ET.fromstring(ncx_xml)
                            for np in ncx_root.iter('{http://www.daisy.org/z3986/2005/ncx/}navPoint'):
                                lbl = np.find('{http://www.daisy.org/z3986/2005/ncx/}navLabel/{http://www.daisy.org/z3986/2005/ncx/}text')
                                cnt = np.find('{http://www.daisy.org/z3986/2005/ncx/}content')
                                if lbl is not None and cnt is not None and lbl.text:
                                    src = cnt.attrib.get('src', '').split('#')[0]
                                    title_txt = lbl.text.strip()
                                    if src:
                                        toc_map[src] = title_txt
                                        toc_map[src.lstrip('/')] = title_txt
                                        if '/' in src:
                                            toc_map[src.split('/')[-1]] = title_txt
                            break
                        except Exception:
                            pass

                # 4. Extract spine chapters, filter metadata/ads, and match TOC names
                ch_index = 1
                for rel_href in spine_items:
                    file_path = f"{opf_dir}/{rel_href}".lstrip("/") if opf_dir else rel_href
                    if file_path not in z.namelist():
                        continue

                    filename = rel_href.split('/')[-1].lower()
                    toc_title = toc_map.get(rel_href) or toc_map.get(rel_href.lstrip('/')) or toc_map.get(filename)

                    # Filter out cover pages, TOC pages, and known ad pages
                    if filename in SKIP_FILENAMES:
                        continue
                    if toc_title and toc_title.strip().lower() in SKIP_TITLES:
                        continue

                    raw_content = z.read(file_path).decode("utf-8", errors="ignore")
                    clean_text = clean_html_text(raw_content)

                    # Filter out tiny or ad-only pages
                    if len(clean_text) < 50:
                        continue
                    # Skip common ad text
                    if "stay up to date on light novels" in clean_text.lower() and len(clean_text) < 300:
                        continue

                    # Determine Chapter Title
                    if toc_title:
                        final_title = toc_title
                    else:
                        first_lines = clean_text.splitlines()[:3]
                        final_title = f"Chapter {ch_index}"
                        for line in first_lines:
                            line = line.strip()
                            if re.search(r'(chapter|глава|розділ|volume|том|prologue|пролог|epilogue|епілог)\s*\d*', line, re.IGNORECASE):
                                final_title = line[:60]
                                break

                    chapters.append({
                        "chapter": ch_index,
                        "title": final_title,
                        "content": clean_text
                    })
                    ch_index += 1

        except Exception as e:
            # Fallback simple extractor: iterate all html/xhtml files
            try:
                with zipfile.ZipFile(epub_path, 'r') as z:
                    html_files = [f for f in z.namelist() if f.lower().endswith(('.html', '.xhtml', '.htm'))]
                    html_files.sort()
                    ch_index = 1
                    for hf in html_files:
                        fn = hf.split('/')[-1].lower()
                        if fn in SKIP_FILENAMES:
                            continue
                        raw = z.read(hf).decode("utf-8", errors="ignore")
                        text = clean_html_text(raw)
                        if len(text) > 80:
                            chapters.append({
                                "chapter": ch_index,
                                "title": f"Chapter {ch_index}",
                                "content": text
                            })
                            ch_index += 1
            except Exception:
                pass

        return chapters


class DocxParser:
    """Parser for .docx and .txt chapter files."""

    @staticmethod
    def extract_text(file_path: Path) -> str:
        if not file_path.exists():
            return ""

        suffix = file_path.suffix.lower()
        if suffix == ".txt":
            try:
                return file_path.read_text(encoding="utf-8")
            except Exception:
                return file_path.read_text(encoding="cp1251", errors="ignore")

        elif suffix == ".docx":
            if docx is not None:
                try:
                    doc = docx.Document(str(file_path))
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    return "\n\n".join(paragraphs)
                except Exception:
                    pass

            # Fallback without python-docx: docx is a zip with word/document.xml
            try:
                with zipfile.ZipFile(file_path, 'r') as z:
                    xml_content = z.read("word/document.xml")
                    tree = ET.fromstring(xml_content)
                    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    text_parts = []
                    for p in tree.findall('.//w:p', ns):
                        p_texts = [t.text for t in p.findall('.//w:t', ns) if t.text]
                        if p_texts:
                            text_parts.append("".join(p_texts))
                    return "\n\n".join(text_parts)
            except Exception:
                return ""

        return ""
