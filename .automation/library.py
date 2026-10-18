"""Read selected Calibre sources without modifying the library or exporting ebooks."""
import hashlib
import json
from pathlib import Path
import posixpath
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile

AUTO = Path(__file__).resolve().parent


def normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def library_root():
    private = json.loads((AUTO / "private.json").read_text(encoding="utf-8-sig"))
    root = Path(private["calibre_library"]).resolve()
    if not (root / "metadata.db").is_file():
        raise RuntimeError("Configured Calibre library is unavailable")
    return root


def source_file(book):
    root = library_root()
    with sqlite3.connect((root / "metadata.db").as_uri() + "?mode=ro", uri=True) as connection:
        row = connection.execute("select path from books where id=?", (book["id"],)).fetchone()
        if not row:
            raise RuntimeError(f"Calibre source missing: {book['title']}")
        formats = connection.execute("select format,name from data where book=?", (book["id"],)).fetchall()
    for preferred in ("EPUB", "PDF", "TXT"):
        for format_name, name in formats:
            if format_name == preferred:
                path = (root / row[0] / (name + "." + format_name.lower())).resolve()
                if root not in path.parents:
                    raise RuntimeError("Calibre source path escaped the library")
                if path.is_file():
                    return path
    raise RuntimeError(f"No readable EPUB, PDF, or TXT source: {book['title']}")


def epub_units(path):
    from bs4 import BeautifulSoup
    units = []
    with zipfile.ZipFile(path) as archive:
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        package_path = next(e.attrib["full-path"] for e in container.iter() if e.tag.endswith("rootfile"))
        package = ET.fromstring(archive.read(package_path))
        manifest = {e.attrib["id"]: e.attrib for e in package.iter() if e.tag.endswith("}item")}
        spine = [e.attrib["idref"] for e in package.iter() if e.tag.endswith("itemref")]
        for position, reference in enumerate(spine):
            item = manifest[reference]
            if "nav" in item.get("properties", "").split():
                continue
            resource = posixpath.normpath(posixpath.join(posixpath.dirname(package_path), item["href"].split("#")[0]))
            from urllib.parse import unquote
            soup = BeautifulSoup(archive.read(unquote(resource)), "html.parser")
            for node in soup.select("script,style,nav"):
                node.decompose()
            heading = next((normalize(h.get_text(" ", strip=True)) for h in soup.select("h1,h2,h3") if normalize(h.get_text(" ", strip=True))), f"EPUB section {position + 1}")
            paragraphs = [normalize(p.get_text(" ", strip=True)) for p in soup.select("p") if len(normalize(p.get_text(" ", strip=True)).split()) >= 8]
            if not paragraphs and soup.body:
                paragraphs = [normalize(soup.body.get_text(" ", strip=True))]
            if paragraphs:
                units.append({"locator": f"{heading[:150]} (EPUB section {position + 1})", "paragraphs": paragraphs})
    return units


def pdf_units(path):
    import fitz
    units = []
    with fitz.open(path) as document:
        if document.needs_pass:
            raise RuntimeError("Password-protected PDF cannot be read automatically")
        for number, page in enumerate(document):
            blocks = page.get_text("blocks", sort=True)
            paragraphs = [normalize(block[4]) for block in blocks if len(normalize(block[4]).split()) >= 8]
            if paragraphs:
                units.append({"locator": f"PDF page {number + 1}", "paragraphs": paragraphs})
    return units


def load_units(book):
    path = source_file(book)
    fingerprint = hashlib.sha256(f"{path}:{path.stat().st_size}:{path.stat().st_mtime_ns}".encode()).hexdigest()
    cached = AUTO / "cache" / f"book-{book['id']}.json"
    if cached.exists():
        data = json.loads(cached.read_text(encoding="utf-8"))
        if data.get("fingerprint") == fingerprint:
            return data["units"]
    if path.suffix.lower() == ".epub":
        units = epub_units(path)
    elif path.suffix.lower() == ".pdf":
        units = pdf_units(path)
    else:
        text = path.read_text(encoding="utf-8-sig")
        units = [{"locator": "Plain-text edition", "paragraphs": [normalize(p) for p in re.split(r"\n\s*\n", text) if normalize(p)]}]
    if sum(sum(len(p.split()) for p in u["paragraphs"]) for u in units) < 1000:
        raise RuntimeError(f"Insufficient extractable source text: {book['title']}")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps({"fingerprint": fingerprint, "units": units}, ensure_ascii=False), encoding="utf-8")
    return units


def select_passage(book, theme, history, day):
    units = load_units(book)
    used = {s["locator"] for post in history for s in post["sources"] if s["book_id"] == book["id"]}
    candidates = []
    for index, unit in enumerate(units):
        text = " ".join(unit["paragraphs"])
        lower = text.casefold()
        if len(text.split()) < 120 or unit["locator"] in used:
            continue
        if re.search(r"all rights reserved|table of contents|bibliography|index of|isbn|copyright ©", lower):
            continue
        if re.search(r"dosage|milligrams|withdrawal symptoms|detoxification|antidepressant|benzodiazepine", lower):
            continue
        hits = sum(min(4, lower.count(word)) for word in theme["keywords"])
        if not hits:
            continue
        tie = hashlib.sha256(f"{day}:{book['id']}:{index}".encode()).hexdigest()
        candidates.append((hits, tie, index))
    if not candidates:
        raise RuntimeError(f"No fresh suitable source passage for {book['title']}")
    # Prefer a relevant passage, with stable daily variety among similar passages.
    _, _, selected = max(candidates)
    unit = units[selected]
    # Some PDF text blocks and EPUB paragraphs span several pages. Bound the
    # selection window without rewriting words or changing quotation matching.
    paragraphs = []
    for paragraph in unit["paragraphs"]:
        words = paragraph.split()
        if len(words) > 300:
            paragraphs.extend(" ".join(words[i:i + 180]) for i in range(0, len(words), 180))
        else:
            paragraphs.append(paragraph)
    scores = [sum(p.casefold().count(word) for word in theme["keywords"]) for p in paragraphs]
    center = max(range(len(scores)), key=scores.__getitem__)
    left = right = center
    words = len(paragraphs[center].split())
    while words < 950 and (left > 0 or right + 1 < len(paragraphs)):
        if left > 0:
            left -= 1
            words += len(paragraphs[left].split())
        if right + 1 < len(paragraphs):
            right += 1
            words += len(paragraphs[right].split())
    text = "\n\n".join(paragraphs[left:right + 1])
    if len(text.split()) > 2200:
        raise RuntimeError("Source paragraph is too large for a focused daily excerpt")
    return {"book_id": book["id"], "title": book["title"], "author": book["author"], "isbn": book["isbn"], "locator": unit["locator"], "text": text}
