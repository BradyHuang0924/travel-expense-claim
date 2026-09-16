"""Fresh read, validation and retention of the five business sources.

Every run fetches all five over the network. Nothing is served from a cache: the brief
requires the sources to be "fetched fresh on every run", so a stale local copy would
make that claim false. A gate failure raises and stops the run rather than degrading.
"""
from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import io
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

POLICY_PAGE_ID = "3d80b700-541e-81ed-93eb-d386abc1dcb0"
POLICY_HOST = "https://private-pecorino-70e.notion.site"
SPREADSHEET_ID = "1338nvKD6rgAdLgGRhYCMMlQyDNLK0sE8pvFWrZAaaxg"

REGISTER_TABS = (
    "People", "Trips", "Merchant payments", "FX", "Caps", "Budget",
    "Review ledger", "Review packets", "Finance activity", "Travel cancellations",
)
PDF_BINDERS = (
    ("initial_claims", "13sRj6s_kMeP1hsYGstWWmfkb6SCN1YOS", "Initial claim binder"),
    ("claim_updates", "16829RwrGrMCK9oq5TnWuytFewGk_8xQP", "Claim updates binder"),
    ("receipts", "1Ynn1VLH-faRIy91xy95rOWwCBhy5mjjM", "Receipt binder"),
)

# The package id every business source stamps on itself. None of them carry a version
# string; only the policy does. See references/sources.md for the recorded gap.
BUSINESS_PACKAGE_ID = "SRC-D-3"

_UA = {"User-Agent": "alderbridge-travel-expense-claim/1.0"}


class SourceGateError(RuntimeError):
    """A fetched response is not the expected source (login page, shell, wrong page)."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(url: str, *, data: bytes | None = None, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, data=data, headers=dict(_UA))
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


@dataclass
class RetainedSource:
    source_id: str
    url: str
    locator: dict
    fetched_at: str
    retained_path: str
    sha256: str
    bytes_len: int
    declared_version: dict
    counts: dict
    extra: dict = field(default_factory=dict)

    def as_record(self) -> dict:
        rec = {
            "source_id": self.source_id,
            "url": self.url,
            "locator": self.locator,
            "fetched_at": self.fetched_at,
            "retained_path": self.retained_path,
            "observed_version": {
                "convention": "sha256-of-retained-bytes",
                "sha256": self.sha256,
                "bytes": self.bytes_len,
            },
            "declared_version": self.declared_version,
            "counts": self.counts,
        }
        if self.extra:
            rec["observed_version"].update(self.extra)
        return rec


def _retain(root: Path, rel: str, data: bytes) -> str:
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return rel.replace("\\", "/")


# --------------------------------------------------------------------------- policy

def fetch_policy(root: Path) -> tuple[RetainedSource, dict]:
    """Notion public pages are client-rendered: a plain GET returns the SPA shell with
    no policy text at all. The page content only exists behind the public loadPageChunk
    endpoint, so that is the access path. It is still a fresh unauthenticated read of
    the live page, and the payload carries the page's own version and last_edited_time,
    which we record alongside the content hash."""
    url = f"{POLICY_HOST}/api/v3/loadPageChunk"
    chunks: list[dict] = []
    raw_parts: list[bytes] = []
    cursor: dict = {"stack": []}
    for chunk_no in range(0, 20):
        body = json.dumps({
            "pageId": POLICY_PAGE_ID,
            "limit": 200,
            "cursor": cursor,
            "chunkNumber": chunk_no,
            "verticalColumns": False,
        }).encode()
        raw = _get(url, data=body)
        raw_parts.append(raw)
        payload = json.loads(raw)
        chunks.append(payload)
        cursor = payload.get("cursor") or {"stack": []}
        if not cursor.get("stack"):
            break

    merged_blocks: dict = {}
    for payload in chunks:
        merged_blocks.update((payload.get("recordMap") or {}).get("block", {}))

    if not merged_blocks:
        raise SourceGateError("policy: loadPageChunk returned no blocks")
    root_block = _block_value(merged_blocks, POLICY_PAGE_ID)
    if root_block is None:
        raise SourceGateError("policy: page block absent from recordMap")
    title = _rich_text(root_block.get("properties", {}).get("title"))
    if "POL-" not in title:
        raise SourceGateError(f"policy: title does not carry a POL version: {title!r}")
    content_ids = root_block.get("content") or []
    if not content_ids:
        raise SourceGateError("policy: page has no content blocks")

    blocks_text = []
    for bid in content_ids:
        val = _block_value(merged_blocks, bid)
        if val is None:
            raise SourceGateError(f"policy: content block {bid} not loaded")
        blocks_text.append(_rich_text((val.get("properties") or {}).get("title")))
    rendered = "\n\n".join(blocks_text)
    if "JavaScript must be enabled" in rendered:
        raise SourceGateError("policy: response is the SPA shell, not page content")

    raw_blob = b"\n".join(raw_parts)
    rel = _retain(root, "sources/policy/loadPageChunk.json", raw_blob)
    _retain(root, "sources/policy/policy.txt", rendered.encode("utf-8"))

    version = title.split("POL-", 1)[1].strip()
    edited_ms = root_block.get("last_edited_time")
    edited = (
        _dt.datetime.fromtimestamp(edited_ms / 1000, _dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        if edited_ms else None
    )
    src = RetainedSource(
        source_id="policy",
        url=f"{POLICY_HOST}/api/v3/loadPageChunk",
        locator={"kind": "notion_api", "page_id": POLICY_PAGE_ID,
                 "endpoint": "/api/v3/loadPageChunk"},
        fetched_at=_now(),
        retained_path=rel,
        sha256=_sha256(raw_blob),
        bytes_len=len(raw_blob),
        declared_version={"package_id": None, "version_string": f"POL-{version}"},
        counts={"content_blocks": len(content_ids), "chunks": len(chunks)},
        extra={"notion_block_version": root_block.get("version"),
               "notion_last_edited_time": edited},
    )
    return src, {"title": title, "version": f"POL-{version}", "blocks": blocks_text}


def _block_value(blocks: dict, bid: str):
    node = blocks.get(bid)
    if not node:
        return None
    val = node.get("value")
    if val is None:
        return None
    return val.get("value", val)


def _rich_text(prop) -> str:
    if not prop:
        return ""
    return "".join(part[0] for part in prop)


# ------------------------------------------------------------------------ registers

def fetch_registers(root: Path) -> tuple[list[RetainedSource], dict[str, list[list[str]]]]:
    out: list[RetainedSource] = []
    tables: dict[str, list[list[str]]] = {}
    for tab in REGISTER_TABS:
        url = (f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
               f"/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(tab)}")
        raw = _get(url)
        head = raw[:200].lstrip().lower()
        if head.startswith(b"<!doctype") or head.startswith(b"<html"):
            raise SourceGateError(f"registers/{tab}: response is HTML, not CSV")
        text = raw.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text, newline="")))
        if not rows:
            raise SourceGateError(f"registers/{tab}: empty CSV")
        if BUSINESS_PACKAGE_ID not in text:
            raise SourceGateError(
                f"registers/{tab}: banner does not carry {BUSINESS_PACKAGE_ID}")
        slug = tab.replace(" ", "_")
        rel = _retain(root, f"sources/registers/{slug}.csv", raw)
        tables[tab] = rows
        out.append(RetainedSource(
            source_id=f"registers.{slug.lower()}",
            url=url,
            locator={"kind": "gviz_csv", "spreadsheet_id": SPREADSHEET_ID, "tab": tab},
            fetched_at=_now(),
            retained_path=rel,
            sha256=_sha256(raw),
            bytes_len=len(raw),
            declared_version={"package_id": BUSINESS_PACKAGE_ID, "version_string": None},
            counts={"csv_rows": len(rows)},
        ))
    return out, tables


# ----------------------------------------------------------------------------- pdfs

def fetch_pdfs(root: Path) -> tuple[list[RetainedSource], dict[str, list[str]]]:
    import pypdf

    out: list[RetainedSource] = []
    pages: dict[str, list[str]] = {}
    for name, file_id, label in PDF_BINDERS:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        raw = _get(url)
        if not raw.startswith(b"%PDF"):
            raise SourceGateError(
                f"pdf/{name}: response is not a PDF (Drive interstitial or error page)")
        reader = pypdf.PdfReader(io.BytesIO(raw))
        text_pages = [p.extract_text() or "" for p in reader.pages]
        joined = "\n".join(text_pages)
        if BUSINESS_PACKAGE_ID not in joined:
            raise SourceGateError(
                f"pdf/{name}: footer does not carry {BUSINESS_PACKAGE_ID}")
        rel = _retain(root, f"sources/pdf/{name}.pdf", raw)
        _retain(root, f"sources/pdf/{name}.txt", joined.encode("utf-8"))
        pages[name] = text_pages
        out.append(RetainedSource(
            source_id=f"binder.{name}",
            url=url,
            locator={"kind": "drive_uc", "file_id": file_id, "label": label},
            fetched_at=_now(),
            retained_path=rel,
            sha256=_sha256(raw),
            bytes_len=len(raw),
            declared_version={"package_id": BUSINESS_PACKAGE_ID, "version_string": None},
            counts={"pages": len(text_pages)},
        ))
    return out, pages


# -------------------------------------------------------------------- sources.json

def write_sources_json(root: Path, sources: list[RetainedSource], run_id: str) -> str:
    """sources.json never contains its own hash; snapshots bind to it by path+sha256."""
    doc = {
        "run_id": run_id,
        "case_clock": {"date": "2026-11-15", "timezone": "Europe/Amsterdam"},
        "fetch_policy": "all five sources fetched fresh over the network on every run",
        "version_convention": (
            "Only the policy carries a version string (POL-2026.2). The four business "
            "sources stamp package id SRC-D-3 with no version, so observed_version is "
            "the SHA-256 of the retained bytes. No version number is invented."
        ),
        "sources": [s.as_record() for s in sources],
    }
    path = root / "sources.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return "sources.json"


def sha256_of(path: Path) -> str:
    return _sha256(path.read_bytes())
