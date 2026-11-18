"""Download public PDFs and record the exact bytes, source and coverage."""
from datetime import datetime, timezone
import time

import httpx
import pymupdf

from .common import ROOT, digest, read_json, write_json


def fetch_all():
    destination = ROOT / "data/raw"
    destination.mkdir(parents=True, exist_ok=True)
    manifests = []
    for source in read_json(ROOT / "sources.json"):
        path = destination / source["filename"]
        manifest_path = destination / (source["id"] + ".manifest.json")
        if path.exists() and manifest_path.exists():
            manifest = read_json(manifest_path)
            if digest(path.read_bytes()) != manifest["sha256"]:
                raise ValueError(f"Checksum mismatch for {path}")
            manifests.append(manifest)
            continue
        errors = []
        for url in source["urls"]:
            start = time.perf_counter()
            try:
                response = httpx.get(url, follow_redirects=True, timeout=120)
                response.raise_for_status()
                content = response.content
                if not content.startswith(b"%PDF"):
                    raise ValueError("Source returned something other than a PDF")
                with pymupdf.open(stream=content, filetype="pdf") as pdf:
                    pages = len(pdf)
                    if pages < source["expected_min_pages"]:
                        raise ValueError(f"Incomplete PDF with {pages} pages")
                    sample_text = pdf[0].get_text()
                temporary = path.with_suffix(".part")
                temporary.write_bytes(content)
                temporary.replace(path)
                manifest = {**source, "download_url": str(response.url),
                            "downloaded_at": datetime.now(timezone.utc).isoformat(),
                            "sha256": digest(content), "bytes": len(content), "pages": pages,
                            "download_seconds": time.perf_counter() - start,
                            "first_page_preview": sample_text[:500], "failed_sources": errors}
                write_json(manifest_path, manifest)
                manifests.append(manifest)
                print(f"{source['id']}: {pages} pages, {len(content)} bytes", flush=True)
                break
            except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                errors.append({"url": url, "error": str(exc)})
        else:
            raise RuntimeError(f"Failed to download {source['id']}: {errors}")
    write_json(ROOT / "data/corpus-manifest.json", manifests)
    return manifests


if __name__ == "__main__":
    fetch_all()
