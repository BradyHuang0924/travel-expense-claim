"""Admission of supplied Finance outcomes, replay handling and money arithmetic.

block 9: "Only supplied Finance outcomes establish pending, failed, settled,
cancellation, refund and resolution facts." Nothing here originates a fact; it admits
what the register supplies and refuses what it cannot validate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from . import policy
from .evaluate import Issue, to_cents

# block 13: "The immutable payload excludes only arrival batch."
_IDENTITY_EXCLUDED = {"Arrival batch"}


def request_id_for(claim_id: str) -> str:
    """block 8: 'Use a stable request ID for the same obligation.'

    A pure function of the claim id, so the same obligation yields the same id on every
    rerun. The obligation is the claim, not the claim revision: the supplied Finance
    register keeps one request reference per claim across all its revisions.
    """
    return f"REQ-{claim_id}"


@dataclass
class AdmittedEvents:
    admitted: dict[str, dict] = field(default_factory=dict)   # activity ref -> payload
    order: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    replays: list[str] = field(default_factory=list)

    def ids(self) -> list[str]:
        return list(self.order)


def _payload(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in _IDENTITY_EXCLUDED}


def arrival_batches(rows: list[dict], key: str = "Activity reference") -> dict[str, int]:
    """First arrival batch per event reference; an exact replay never moves it."""
    out: dict[str, int] = {}
    for row in rows:
        ref = row[key]
        b = int(row["Arrival batch"])
        if ref not in out or b < out[ref]:
            out[ref] = b
    return out


def admit(rows: list[dict], upto_batch: int) -> AdmittedEvents:
    """Admit Finance activity rows delivered in this batch or earlier.

    block 9: "An immutable event ID identifies one payload across all batches/versions:
    exact replay has no extra effect, conflicting replay holds the case without erasing
    admitted money."
    """
    out = AdmittedEvents()
    for row in rows:
        if int(row["Arrival batch"]) > upto_batch:
            continue
        ref = row["Activity reference"]
        kind = row["Activity type"]
        if kind not in policy.FINANCE_ACTIVITY_TYPES:
            out.issues.append(Issue(
                f"ISS-FINANCE-UNKNOWN-TYPE-{ref}",
                f"Finance activity {ref} has unrecognised activity type '{kind}'.",
                row.get("Finance officer") or "FIN-01",
                "Confirm the intended activity type or withdraw the event.",
                subject_type="source", subject_ref="registers.finance_activity",
                source_refs=[ref], kind="finance_unknown_type"))
            continue
        payload = _payload(row)
        if ref in out.admitted:
            if out.admitted[ref] == payload:
                out.replays.append(ref)          # exact replay: no extra effect
            else:
                out.conflicts.append(ref)
                out.issues.append(Issue(
                    f"ISS-FINANCE-CONFLICTING-REPLAY-{ref}",
                    f"Finance event {ref} was redelivered with a different payload; "
                    f"admitted money is retained and the case is held.",
                    row.get("Finance officer") or "FIN-01",
                    "Supply the authoritative payload for this event reference.",
                    subject_type="source", subject_ref="registers.finance_activity",
                    source_refs=[ref], blocks=[row.get("Claim reference", "")],
                    kind="finance_conflicting_replay"))
            continue
        out.admitted[ref] = payload
        out.order.append(ref)
    return out


@dataclass
class ClaimMoney:
    settled_cents: int = 0
    refunded_cents: int = 0
    accepted: bool = False
    failed: bool = False
    retry_authorized: bool = False
    cancel_pending: bool = False
    cancelled: bool = False
    adjustment: bool = False
    resolution: bool = False
    accepted_batch: int | None = None
    event_ids: list[str] = field(default_factory=list)
    unlinked_refunds: list[str] = field(default_factory=list)

    @property
    def net_paid_cents(self) -> int:
        """block 10: 'Net paid = admitted confirmed transfers minus linked confirmed
        refunds.' Withdrawal, holding or closure never reduce it."""
        return self.settled_cents - self.refunded_cents


def money_by_claim(events: AdmittedEvents,
                   arrival_batch: dict[str, int] | None = None) -> dict[str, ClaimMoney]:
    out: dict[str, ClaimMoney] = {}
    settled_by_ref: dict[str, int] = {}
    arrival_batch = arrival_batch or {}
    for ref in events.order:
        row = events.admitted[ref]
        claim_id = row["Claim reference"]
        m = out.setdefault(claim_id, ClaimMoney())
        m.event_ids.append(ref)
        kind = row["Activity type"]
        raw = (row.get("Amount (EUR)") or "").replace(",", "").strip()
        cents = to_cents(Decimal(raw)) if raw else 0
        if kind == "accepted":
            m.accepted = True
            b = arrival_batch.get(ref)
            if b is not None and (m.accepted_batch is None or b < m.accepted_batch):
                m.accepted_batch = b
        elif kind == "settled":
            m.settled_cents += cents
            settled_by_ref[ref] = cents
        elif kind == "failed":
            m.failed = True              # block 9: does not change paid amount
        elif kind == "retry_authorized":
            m.retry_authorized = True
        elif kind == "cancellation_requested":
            m.cancel_pending = True
        elif kind == "cancelled":
            m.cancelled = True
        elif kind == "adjustment":
            m.adjustment = True
        elif kind == "resolution":
            m.resolution = True
        elif kind == "refund":
            # block 9: "A confirmed refund must name a prior settled transfer and cannot
            # exceed its unrecovered amount."
            origin = row.get("Original activity reference") or ""
            if origin and origin in settled_by_ref and cents <= settled_by_ref[origin]:
                m.refunded_cents += cents
                settled_by_ref[origin] -= cents
            else:
                m.unlinked_refunds.append(ref)
    return out
