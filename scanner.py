# scanner.py
import os, re, io, hashlib
from bs4 import BeautifulSoup
from email import policy
from email.parser import BytesParser
import logging

# Optional libs (pdf, ocr, .msg)
try:
    from pdfminer.high_level import extract_text as pdf_extract_text
    PDFMINER_AVAILABLE = True
except Exception:
    PDFMINER_AVAILABLE = False

try:
    from PIL import Image, ImageOps, ImageFilter
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

try:
    import extract_msg
    MSG_AVAILABLE = True
except Exception:
    MSG_AVAILABLE = False

logger = logging.getLogger(__name__)

# helpers
def _safe_read_bytes(path, max_bytes=30*1024*1024):
    """Read file binary but protect against huge files."""
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError(f"file too large: {size} bytes")
    with open(path, "rb") as f:
        return f.read()

def _strip_and_normalize_text(s: str) -> str:
    # collapse whitespace, strip
    return re.sub(r'\s+', ' ', s).strip()

def extract_from_txt(path):
    b = _safe_read_bytes(path)
    try:
        text = b.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = b.decode("latin1")
        except Exception:
            text = b.decode("utf-8", errors="ignore")
    return _strip_and_normalize_text(text)

def extract_from_html(path):
    b = _safe_read_bytes(path)
    # decode best-effort
    try:
        html = b.decode("utf-8")
    except UnicodeDecodeError:
        html = b.decode("latin1", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    # remove script/style
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    # optional: remove inline event attributes to be safe (not executing anyway)
    for tag in soup.find_all(True):
        attrs = dict(tag.attrs)
        for a in list(attrs):
            if a.startswith("on"):  # onclick etc
                del tag.attrs[a]
    text = soup.get_text(separator=" ", strip=True)
    snippet = str(soup)[:2000]  # return a short HTML snippet for reference
    return _strip_and_normalize_text(text), snippet

def _extract_urls_from_text(text):
    return re.findall(r'https?://[^\s"\'<>]+', text)

def extract_from_pdf(path):
    if not PDFMINER_AVAILABLE:
        raise RuntimeError("pdfminer.six not available. Install pdfminer.six")
    # pdfminer extracts text; it's slower but reliable
    text = pdf_extract_text(path)
    return _strip_and_normalize_text(text)

def extract_from_image(path, ocr_config="--psm 3"):
    if not OCR_AVAILABLE:
        raise RuntimeError("OCR (pytesseract + Pillow) not available")
    # basic preprocess: convert to grayscale, increase contrast, maybe threshold
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    img = img.convert("L")  # grayscale
    # optional resizing if very small
    w, h = img.size
    if max(w, h) < 1000:
        scale = int(1000 / max(w, h)) + 1
        img = img.resize((w * scale, h * scale))
    # optional filter
    img = img.filter(ImageFilter.MedianFilter())
    text = pytesseract.image_to_string(img, config=ocr_config)
    return _strip_and_normalize_text(text)

def extract_from_eml(path, do_attachments=False, max_attachment_bytes=5*1024*1024):
    """
    Returns: dict with headers, plain_text, html_text (snippet), attachments list (meta)
    """
    raw = _safe_read_bytes(path)
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    headers = dict(msg.items())
    plain_parts = []
    html_parts = []
    attachments = []

    def _process_part(part):
        ctype = part.get_content_type()
        disp = part.get_content_disposition()  # 'attachment' or 'inline' or None
        if part.is_multipart():
            for sub in part.iter_parts():
                _process_part(sub)
        else:
            payload = part.get_payload(decode=True) or b""
            # text/plain
            if ctype == "text/plain":
                try:
                    plain_parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="ignore"))
                except Exception:
                    plain_parts.append(payload.decode("utf-8", errors="ignore"))
            elif ctype == "text/html":
                try:
                    html_parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="ignore"))
                except Exception:
                    html_parts.append(payload.decode("utf-8", errors="ignore"))
            else:
                # treat as attachment
                if do_attachments:
                    fn = part.get_filename()
                    size = len(payload)
                    if size <= max_attachment_bytes:
                        # store digest & meta (not full content here)
                        sha = hashlib.sha256(payload).hexdigest()
                        attachments.append({"filename": fn, "content_type": ctype, "size": size, "sha256": sha})
                    else:
                        attachments.append({"filename": fn, "content_type": ctype, "size": size, "sha256": None, "note": "too large"})
    _process_part(msg)

    plain_text = _strip_and_normalize_text(" ".join(plain_parts)) if plain_parts else ""
    html_text, snippet = ("", "")
    if html_parts:
        # combine and extract text from combined HTML
        combined_html = "\n".join(html_parts)
        soup = BeautifulSoup(combined_html, "html.parser")
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        html_text = _strip_and_normalize_text(soup.get_text(separator=" ", strip=True))
        snippet = str(soup)[:2000]
    # fallback: if no plain but html exists, use html_text for plain_text
    if not plain_text and html_text:
        plain_text = html_text

    # collect urls from both
    urls = _extract_urls_from_text(plain_text)
    urls += _extract_urls_from_text(html_text)

    return {
        "headers": headers,
        "plain_text": plain_text,
        "html_snippet": snippet,
        "extracted_urls": list(dict.fromkeys(urls)),
        "attachments": attachments
    }

def extract_from_msg(path):
    if not MSG_AVAILABLE:
        raise RuntimeError(".msg support requires extract_msg library")
    m = extract_msg.Message(path)
    subject = m.subject
    body = m.body or ""
    # attachments metadata
    atts = []
    for a in m.attachments:
        atts.append({"filename": a.filename, "size": len(a.data)})
    urls = _extract_urls_from_text(body)
    return {"subject": subject, "plain_text": _strip_and_normalize_text(body), "extracted_urls": urls, "attachments": atts}

# Top-level
def extract_text(path, ocr_images=False):
    """
    Main entry point.
    Returns a dict: { "text": ..., "html_snippet": ..., "urls": [...], "type": "...", "meta": {...} }
    """
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    try:
        if ext in ("txt", "text"):
            text = extract_from_txt(path)
            return {"type":"text", "text": text, "html_snippet": None, "urls": _extract_urls_from_text(text), "meta":{}}
        if ext in ("html", "htm"):
            text, snippet = extract_from_html(path)
            return {"type":"html", "text": text, "html_snippet": snippet, "urls": _extract_urls_from_text(text), "meta":{}}
        if ext in ("eml",):
            eml = extract_from_eml(path, do_attachments=True)
            return {"type":"eml", "text": eml.get("plain_text",""), "html_snippet": eml.get("html_snippet",""), "urls": eml.get("extracted_urls",[]), "meta": {"headers": eml.get("headers"), "attachments": eml.get("attachments")}}
        if ext in ("pdf",):
            text = extract_from_pdf(path)
            return {"type":"pdf", "text": text, "html_snippet": None, "urls": _extract_urls_from_text(text), "meta":{}}
        if ext in ("png","jpg","jpeg","tiff","bmp","gif"):
            if ocr_images:
                text = extract_from_image(path)
                return {"type":"image", "text": text, "html_snippet": None, "urls": _extract_urls_from_text(text), "meta":{}}
            else:
                return {"type":"image", "text": "", "html_snippet": None, "urls": [], "meta":{}}
...         if ext in ("msg",):
...             msg = extract_from_msg(path)
...             return {"type":"msg", "text": msg.get("plain_text",""), "html_snippet": None, "urls": msg.get("extracted_urls",[]), "meta": {"subject": msg.get("subject"), "attachments": msg.get("attachments")}}
...     except Exception as e:
...         logger.exception("extract_text error")
...         return {"type":"unknown", "text": "", "error": str(e), "meta":{}}
... 
...     # fallback: try to read as text
...     try:
...         text = extract_from_txt(path)
...         return {"type":"text_fallback", "text": text, "html_snippet": None, "urls": _extract_urls_from_text(text), "meta":{}}
...     except Exception as e:
...         return {"type":"unknown", "text":"", "error": str(e), "meta":{}}
... 
... 
... # convenience wrapper used by your Flask app's scan_file
... def scan_file(path, ocr_images=False):
...     # returns a structured result suitable for JSONifying
...     res = extract_text(path, ocr_images=ocr_images)
...     # add quick heuristics
...     heuristics = {
...         "has_login_word": bool(re.search(r'\b(login|verify|password|account|reset)\b', res.get("text",""), flags=re.I)),
...         "url_count": len(res.get("urls", []))
...     }
...     out = {
...         "file_name": os.path.basename(path),
...         "file_hash": hashlib.sha256(_safe_read_bytes(path)).hexdigest(),
...         "type": res.get("type"),
...         "text": res.get("text"),
...         "html_snippet": res.get("html_snippet"),
...         "urls": res.get("urls", []),
...         "meta": res.get("meta", {}),
...         "heuristics": heuristics
...     }
...     return out

