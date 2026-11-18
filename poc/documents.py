import re

import pymupdf

from .common import ROOT, digest, read_json, write_json


def split_text(text, size, overlap):
    if size <= overlap or overlap < 0:
        raise ValueError("Chunk size must exceed nonnegative overlap")
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start + overlap:
                end = boundary
        yield start, end, text[start:end]
        if end == len(text):
            break
        start = end - overlap


def parse_document(source, run):
    path = ROOT / "data/raw" / source["filename"]
    if digest(path.read_bytes()) != source["sha256"]:
        raise ValueError("PDF checksum changed")
    chunks, pages = [], []
    with run.span("parse", "pdf", corpus_id=source["id"]) as span:
        with pymupdf.open(path) as document:
            for page_index, page in enumerate(document):
                blocks, seen = [], set()
                for block in page.get_text("blocks", sort=True):
                    text = re.sub(r"\s+", " ", block[4]).strip()
                    if text and text not in seen:
                        blocks.append({"text": text, "bbox": list(block[:4])})
                        seen.add(text)
                text = "\n".join(block["text"] for block in blocks)
                pages.append({"page": page_index + 1, "text": text, "blocks": blocks,
                              "needs_ocr": len(text.strip()) < 20})
                for start, end, content in split_text(text, run.settings["chunk_characters"], run.settings["overlap_characters"]):
                    chunk_id = f"{source['id']}-{source['sha256'][:8]}-p{page_index+1}-c{start}"
                    chunks.append({"id": chunk_id, "page": page_index+1, "start": start, "end": end,
                                   "text": content, "corpus_id": source["id"], "document_hash": source["sha256"]})
        span.update(pages=len(pages), chunks=len(chunks), needs_ocr=sum(p["needs_ocr"] for p in pages))
    sections, group, length = [], [], 0
    for chunk in chunks:
        if length >= run.settings["section_characters"]:
            sections.append(group)
            group, length = [], 0
        group.append(chunk)
        length += len(chunk["text"])
    if group:
        sections.append(group)
    return {"source": source, "pages": pages, "chunks": chunks,
            "sections": [{"id": f"section-{i}", "chunk_ids": [c["id"] for c in group]} for i, group in enumerate(sections)]}
