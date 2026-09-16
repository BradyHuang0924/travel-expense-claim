"""Turn the retained bytes into typed records.

Two shapes need care:

* Register tabs carry a human banner. On nine tabs the banner is folded into the first
  header cell; on `People` it occupies three whole rows before the header. Header
  detection is therefore per tab, never a fixed row index.
* Register cells hold multiple ordered values separated by newlines
  ("Ordered references appear on separate lines").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal


# --------------------------------------------------------------------------- sheets

def header_index(rows: list[list[str]]) -> int:
    """First row whose second cell is non-empty is the header row."""
    for i, row in enumerate(rows):
        if len(row) > 1 and row[1].strip():
            return i
    raise ValueError("no header row found")


def _clean_first_header(cell: str) -> str:
    """The banner is folded into the first header cell. The real column name is the
    trailing sentence fragment after the last full stop, or the last line."""
    if "\n" in cell:
        return cell.split("\n")[-1].strip()
    return cell.rsplit(". ", 1)[-1].strip()


def table(rows: list[list[str]]) -> list[dict]:
    hi = header_index(rows)
    header = [c.split("\n")[-1].strip() for c in rows[hi]]
    header[0] = _clean_first_header(rows[hi][0])
    out = []
    for row in rows[hi + 1:]:
        if not any(c.strip() for c in row):
            continue
        out.append(dict(zip(header, row)))
    return out


def multi(cell: str) -> list[str]:
    """An ordered multi-value cell."""
    return [part.strip() for part in (cell or "").split("\n") if part.strip()]


def money(cell: str) -> Decimal | None:
    cell = (cell or "").strip().replace(",", "")
    if not cell:
        return None
    return Decimal(cell)


def utc_timestamp(cell: str) -> str | None:
    """'2026-09-10 09:00:00 UTC' -> RFC3339 '2026-09-10T09:00:00Z'."""
    cell = (cell or "").strip()
    if not cell:
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})\s*UTC$", cell)
    if not m:
        raise ValueError(f"unrecognised UTC timestamp: {cell!r}")
    return f"{m.group(1)}T{m.group(2)}Z"


# ----------------------------------------------------------------------------- pdfs

@dataclass
class ExpenseLine:
    line_no: int
    cost_id: str
    receipt_id: str
    first_submitted: str
    gross: Decimal
    currency: str


@dataclass
class FinanceException:
    actor: str
    claim_id: str
    revision: int
    cost_id: str
    allowed_original: Decimal
    covered_issues: list[str]
    reason: str
    travel_cancellation_id: str | None  # never present in the supplied binders


@dataclass
class ClaimDoc:
    claim_id: str
    revision: int
    arrival_batch: int
    employee_id: str
    trip_id: str
    trip_revision: int
    submitted: str
    status: str
    reason: str
    related_claim_ids: list[str]
    lines: list[ExpenseLine]
    exception: FinanceException | None
    source_page: str


@dataclass
class Receipt:
    receipt_id: str
    cost_id: str
    employee_id: str
    trip_id: str
    category: str
    currency: str
    gross: Decimal
    documented_units: int
    issued: str
    source_page: str


_FIELD = re.compile(r"^([A-Z][A-Za-z /]+):\s*(.*)$")


def _fields(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = _FIELD.match(line.strip())
        if m:
            out.setdefault(m.group(1).strip(), m.group(2).strip())
    return out


_EXPENSE_HEADER = ["Line", "Expense reference", "Receipt reference",
                   "First submitted date", "Original amount", "Currency"]


def parse_claim_page(text: str, page_label: str) -> ClaimDoc:
    f = _fields(text)
    lines_raw = [ln.strip() for ln in text.splitlines()]

    # The expense table extracts as one cell per line: the six header names, then a
    # repeating group of six values per expense line.
    try:
        start = lines_raw.index(_EXPENSE_HEADER[0])
        for offset, name in enumerate(_EXPENSE_HEADER):
            if lines_raw[start + offset] != name:
                raise ValueError
        start += len(_EXPENSE_HEADER)
    except (ValueError, IndexError) as exc:
        raise ValueError(f"{page_label}: expense table header not found") from exc

    lines: list[ExpenseLine] = []
    i = start
    while i + 5 < len(lines_raw) and re.fullmatch(r"\d+", lines_raw[i] or ""):
        no, cost, receipt, first, amount, currency = lines_raw[i:i + 6]
        if not cost.startswith("COST-"):
            break
        lines.append(ExpenseLine(int(no), cost, receipt, first,
                                 Decimal(amount.replace(",", "")), currency))
        i += 6
    if not lines:
        raise ValueError(f"{page_label}: no expense lines parsed")

    exception = None
    if "Finance exception" in text and f.get("Authorizing Finance officer"):
        covered = f.get("Covered issues", "None").strip()
        covered_list = [] if covered.lower() in ("none", "") else [
            part.strip().lower().replace(" ", "_") for part in covered.split(",")
        ]
        exception = FinanceException(
            actor=f["Authorizing Finance officer"],
            claim_id=f.get("Applies to claim", ""),
            revision=int(f.get("Applies to revision", "0") or 0),
            cost_id=f.get("Expense reference", ""),
            allowed_original=Decimal(
                f.get("Allowed original amount", "0").replace(",", "")),
            covered_issues=covered_list,
            reason=f.get("Exception reason", ""),
            # The supplied exception block has no travel_cancellation_id field at all.
            # It is deliberately not recovered from any other source.
            travel_cancellation_id=f.get("Travel cancellation reference") or None,
        )

    related = f.get("Related earlier claims", "None").strip()
    related_ids = [] if related.lower() == "none" else [
        r.strip() for r in related.split(",") if r.strip()
    ]
    return ClaimDoc(
        claim_id=f["Claim reference"],
        revision=int(f["Revision"]),
        arrival_batch=int(f["Arrival batch"]),
        employee_id=f["Employee"],
        trip_id=f["Trip reference"],
        trip_revision=int(f["Trip revision"]),
        submitted=f["Submitted date"],
        status=f["Status"],
        reason=f.get("Claim reason", ""),
        related_claim_ids=related_ids,
        lines=lines,
        exception=exception,
        source_page=page_label,
    )


def parse_receipt_pages(pages: list[str]) -> list[Receipt]:
    out: list[Receipt] = []
    for page_no, text in enumerate(pages, start=1):
        blocks = re.split(r"(?=Receipt reference:)", text)
        for blk in blocks:
            if not blk.strip().startswith("Receipt reference:"):
                continue
            f = _fields(blk)
            if "Issued date" not in f:
                continue
            out.append(Receipt(
                receipt_id=f["Receipt reference"],
                cost_id=f["Expense reference"],
                employee_id=f["Employee"],
                trip_id=f["Trip reference"],
                category=f["Category"],
                currency=f["Currency"],
                gross=Decimal(f["Gross amount"].replace(",", "")),
                documented_units=int(f["Documented units"]),
                issued=f["Issued date"],
                source_page=f"receipts p{page_no}",
            ))
    return out


def parse_claim_pages(pages: list[str], binder: str) -> list[ClaimDoc]:
    return [parse_claim_page(t, f"{binder} p{n}") for n, t in enumerate(pages, 1)]
