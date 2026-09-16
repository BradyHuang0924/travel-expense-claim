"""Per-batch evaluation and snapshot assembly."""
from __future__ import annotations

import csv as _csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from . import cancellations, finance, normalise, policy
from .evaluate import (ClaimResult, Issue, LineResult, Registers, approved_roles,
                       budget_position, evaluate_line, filing_deadline, to_cents)

SCHEMA_VERSION = "travel-claim-snapshot/2"


def claims_present(docs, upto_batch: int) -> dict[str, object]:
    """Arrival batch, not row order, decides availability; the highest revision that has
    arrived is the current one."""
    current: dict[str, object] = {}
    for doc in docs:
        if doc.arrival_batch > upto_batch:
            continue
        cur = current.get(doc.claim_id)
        if cur is None or doc.revision > cur.revision:
            current[doc.claim_id] = doc
    return current


def prior_settled_links(docs, current: dict[str, object],
                        money: dict[str, finance.ClaimMoney]) -> dict[str, dict[str, str]]:
    """block 8: a later final claim may contain a previously prepaid cost; link and
    exclude that settled obligation. Derived by cost_id overlap, never by listing ids."""
    holders: dict[str, list] = defaultdict(list)
    for claim_id, doc in current.items():
        for line in doc.lines:
            holders[line.cost_id].append(doc)
    links: dict[str, dict[str, str]] = defaultdict(dict)
    for cost_id, docs_with in holders.items():
        if len(docs_with) < 2:
            continue
        ordered = sorted(docs_with, key=lambda d: (d.arrival_batch, d.claim_id))
        origin = ordered[0]
        origin_money = money.get(origin.claim_id)
        if origin_money is None or origin_money.settled_cents <= 0:
            continue
        settled_ref = next(
            (e for e in origin_money.event_ids if e.startswith("F-")), origin.claim_id)
        for later in ordered[1:]:
            links[later.claim_id][cost_id] = (
                f"{finance.request_id_for(origin.claim_id)} ({settled_ref})")
    return links


def evaluate_claim(doc, reg: Registers, receipts: dict, money_map, upto_batch: int,
                   prior_links: dict[str, str], cancel_index: dict) -> ClaimResult:
    trip = reg.trips.get(doc.trip_id)
    people_row = reg.people.get(doc.employee_id, {})
    issues: list[Issue] = []
    findings: list[str] = []

    covered = set(doc.exception.covered_issues) if doc.exception else set()
    bound_cancellation_id = doc.exception.travel_cancellation_id if doc.exception else None

    # ---- lines --------------------------------------------------------------
    line_results: list[LineResult] = []
    for line in doc.lines:
        res = evaluate_line(line, receipts.get(line.cost_id), reg, trip,
                            doc.exception, prior_links)
        line_results.append(res)
        issues.extend(res.issues)
    if any(r.status == "unresolved" for r in line_results):
        allowed_cents = None                     # an unknown cannot be summed
        findings.append("unresolved_line")
    else:
        allowed_cents = sum(r.allowed_cents or 0 for r in line_results)

    # ---- trip record --------------------------------------------------------
    if trip is None:
        findings.append("trip_missing")
        issues.append(Issue(f"ISS-TRIP-MISSING-{doc.trip_id}",
                            f"Claim {doc.claim_id} references trip {doc.trip_id}, which "
                            f"is absent from the Trips register.", "ADMIN-01",
                            "Supply the trip record for this reference."))

    # ---- filing deadline (block 4) -----------------------------------------
    if trip is not None:
        deadline = filing_deadline(trip["End date"])
        if doc.submitted > deadline and "late_filing" not in covered:
            findings.append("late_filing")
            issues.append(Issue(
                f"ISS-LATE-FILING-{doc.claim_id}-{doc.revision}",
                f"Claim {doc.claim_id} rev {doc.revision} was submitted {doc.submitted}, "
                f"after the ordinary filing deadline {deadline} for a trip ending "
                f"{trip['End date']}.",
                "FIN-01",
                "Supply an explicit Finance exception covering late_filing, or the claim "
                "remains held."))

    # ---- permit for international travel (block 3) --------------------------
    if trip is not None and trip.get("International") == "TRUE":
        permit_id = trip.get("Permit reference") or None
        permit_rev = trip.get("Permit revision") or "1"
        got = set()
        if permit_id:
            rows = reg.decisions_for("permit", permit_id, int(permit_rev), upto_batch)
            got, outcomes = approved_roles(rows, people_row)
            got = {r for r in got if outcomes.get(r) == "approve"}
        need = set(policy.PERMIT_REQUIRED_ROLES)
        estimate = trip.get("Estimate (EUR)", "0").replace(",", "")
        if estimate and to_cents(Decimal(estimate)) > policy.DIRECTOR_THRESHOLD_CENTS:
            need.add("director")
        if not need <= got:
            if "permit_unapproved" not in covered:
                findings.append("permit_unapproved")
                issues.append(Issue(
                    f"ISS-PERMIT-UNAPPROVED-{permit_id or doc.trip_id}",
                    f"International trip {doc.trip_id} needs an approved permit before "
                    f"the first arrangement or payment commitment; "
                    f"{permit_id or 'no permit'} is missing approvals from "
                    f"{', '.join(sorted(need - got))}.",
                    "ADMIN-01",
                    "Supply the missing permit review responses, or an explicit Finance "
                    "exception covering permit_unapproved."))

    # ---- travel cancellation (blocks 13 and 14) -----------------------------
    for proc in cancel_index.get(doc.trip_id, []):
        if proc.status == "requested":
            findings.append("cancellation_requested_pause")
            issues.append(Issue(
                f"ISS-CANCEL-PAUSE-{proc.cancellation_id}-{doc.claim_id}",
                f"Cancellation {proc.cancellation_id} is requested and awaiting the "
                f"directory supervisor; payment readiness on {doc.claim_id} is paused. "
                f"This is not a confirmed cancellation and changes no money.",
                proc.next_owner or "ADMIN-01",
                f"Supervisor decision on cancellation {proc.cancellation_id}."))
            continue
        # Confirmed. block 14: the covering exception must itself carry the exact id.
        resolves = ("travel_cancellation" in covered
                    and bound_cancellation_id == proc.cancellation_id)
        if not resolves:
            findings.append("travel_cancellation")
            issues.append(Issue(
                f"ISS-TRAVEL-CANCELLATION-{proc.cancellation_id}-{doc.claim_id}",
                f"Confirmed cancellation {proc.cancellation_id} affects {doc.claim_id}. "
                + ("The supplied Finance exception names covered issue "
                   "'travel_cancellation' but carries no travel_cancellation_id, so it "
                   "does not resolve this finding."
                   if "travel_cancellation" in covered else
                   "No Finance exception covers travel_cancellation for this claim."),
                "FIN-01",
                f"An explicit Finance exception that itself states the exact "
                f"travel_cancellation_id {proc.cancellation_id}, bound actor, "
                f"claim/revision, expense, replacement allowed original amount and "
                f"reason. The link is not inferred from review packets or elsewhere."))

    # ---- claim review (block 3) --------------------------------------------
    rows = reg.decisions_for("claim", doc.claim_id, doc.revision, upto_batch)
    decision_ids = sorted(r["Decision reference"] for r in rows)
    got, outcomes = approved_roles(rows, people_row)
    need = set(policy.CLAIM_REQUIRED_ROLES)
    if allowed_cents is not None and allowed_cents > policy.DIRECTOR_THRESHOLD_CENTS:
        need.add("director")
    rejected = [r for r, o in outcomes.items() if o == "reject"]
    returned = [r for r, o in outcomes.items() if o == "return"]
    approved = {r for r, o in outcomes.items() if o == "approve"}
    missing = need - approved
    if rejected:
        findings.append("review_reject")
    elif returned:
        findings.append("review_return")
        issues.append(Issue(
            f"ISS-REVIEW-RETURNED-{doc.claim_id}-{doc.revision}",
            f"{doc.claim_id} rev {doc.revision} was returned by "
            f"{', '.join(sorted(returned))} with a repair request.",
            people_row.get("Administration reviewer", "ADMIN-01"),
            "Supply the repaired claim revision addressing the recorded repair request."))
    elif missing:
        findings.append("review_missing")
        owner_map = {"administration": people_row.get("Administration reviewer"),
                     "budget_owner": people_row.get("Budget owner"),
                     "supervisor": people_row.get("Supervisor"),
                     "director": people_row.get("Director")}
        who = sorted(missing)
        issues.append(Issue(
            f"ISS-REVIEW-MISSING-{doc.claim_id}-{doc.revision}",
            f"{doc.claim_id} rev {doc.revision} has no reply for required role(s) "
            f"{', '.join(who)}.",
            owner_map.get(who[0]) or "ADMIN-01",
            f"Supply the review response for {', '.join(who)} on this claim revision."))

    # ---- Finance state (blocks 9 and 10) ------------------------------------
    m = money_map.get(doc.claim_id, finance.ClaimMoney())
    for flag, name in ((m.failed, "finance_failed"),
                       (m.cancel_pending, "finance_cancel_pending"),
                       (m.cancelled, "finance_cancelled"),
                       (m.adjustment, "finance_adjustment")):
        if flag:
            findings.append(name)
    if m.unlinked_refunds:
        findings.append("finance_unlinked_refund")
        issues.append(Issue(
            f"ISS-FINANCE-UNLINKED-REFUND-{doc.claim_id}",
            f"Refund event(s) {', '.join(m.unlinked_refunds)} do not name a prior "
            f"settled transfer with sufficient unrecovered amount.",
            "FIN-01",
            "Supply the refund naming its prior settled transfer, within its "
            "unrecovered amount."))

    paid_cents = m.net_paid_cents
    balance_cents = None if allowed_cents is None else allowed_cents - paid_cents
    if balance_cents is not None and balance_cents < 0:
        findings.append("overpayment")
        issues.append(Issue(
            f"ISS-OVERPAYMENT-{doc.claim_id}",
            f"Net paid {paid_cents} cents exceeds the current authorized obligation "
            f"{allowed_cents} cents.", "FIN-01",
            "Supply Finance resolution for the overpayment."))

    # ---- status -------------------------------------------------------------
    status, reason, next_owner = _status(doc, findings, issues, allowed_cents,
                                         paid_cents, m, rejected)

    return ClaimResult(
        claim=doc, status=status, lines=line_results, allowed_cents=allowed_cents,
        paid_cents=paid_cents, balance_cents=balance_cents, decision_ids=decision_ids,
        next_owner=next_owner, reason=reason, issues=issues, findings=findings,
    )


def _status(doc, findings, issues, allowed_cents, paid_cents, m, rejected):
    """block 10: closure conditions; block 6: rejection and clean withdrawal close with
    a non-payment reason."""
    if doc.status == "withdrawn":
        note = ("Clean withdrawal by the employee; closed with an explicit non-payment "
                "reason.")
        if paid_cents:
            note += (f" Admitted transfers of {paid_cents} cents are retained: "
                     f"withdrawal never erases an actual payment.")
        return "withdrawn", note, None
    if rejected:
        return ("rejected",
                f"Rejected by {', '.join(sorted(rejected))}; closed with an explicit "
                f"non-payment reason.", None)
    if findings:
        owner = issues[0].owner if issues else "ADMIN-01"
        return ("held",
                "Held on: " + ", ".join(sorted(set(findings))) + ".", owner)
    if allowed_cents == 0:
        return ("closed-no-payment",
                "Zero entitlement on every line; closed with an explicit non-payment "
                "reason and no unresolved financial effect.", None)
    if m.settled_cents and paid_cents == allowed_cents:
        return ("closed-reimbursed",
                "Current approvals, obligation and net paid agree with no issue "
                "remaining.", None)
    if m.settled_cents:
        return ("pending", "Partial settlement; the obligation stays pending.", "FIN-01")
    if m.accepted:
        return ("pending",
                "Finance accepted the payment request; awaiting confirmed settlement.",
                "FIN-01")
    return ("ready",
            "Reviewed and authorized; payment request may be proposed to Finance.",
            "FIN-01")


def build_request(result: ClaimResult, m: finance.ClaimMoney, reg: Registers):
    """block 8: a payment request is a proposal, not a transfer."""
    doc = result.claim
    if result.allowed_cents is None:
        return None
    if not (m.accepted or m.settled_cents or result.status == "ready"):
        return None
    people_row = reg.people.get(doc.employee_id, {})
    if m.cancelled:
        status = "cancelled"
    elif m.cancel_pending:
        status = "cancel-pending"
    elif m.settled_cents and m.net_paid_cents == result.allowed_cents:
        status = "settled"
    elif result.status == "held":
        status = "held"
    elif m.accepted or m.settled_cents:
        status = "accepted"
    else:
        status = "proposed"
    assert status not in policy.UNREACHABLE_REQUEST_STATUSES
    return {
        "request_id": finance.request_id_for(doc.claim_id),
        "claim_id": doc.claim_id,
        "revision": doc.revision,
        "amount_cents": result.allowed_cents,
        "payee": people_row.get("Payee ID") or doc.employee_id,
        "currency": policy.BASE_CURRENCY,
        "status": status,
        "decision_ids": result.decision_ids,
    }


def snapshot(run_id: str, batch_id: str, predecessor, source_binding,
             results: list[ClaimResult], requests, processes, event_ids, issues) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "batch_id": batch_id,
        "predecessor": predecessor,
        "source_binding": source_binding,
        "claims": [
            {
                "claim_id": r.claim.claim_id,
                "revision": r.claim.revision,
                "trip_id": r.claim.trip_id,
                "trip_revision": r.claim.trip_revision,
                "status": r.status,
                "lines": [
                    {"cost_id": l.cost_id, "source_ids": sorted(set(l.source_ids)),
                     "status": l.status, "allowed_cents": l.allowed_cents,
                     "reason": l.reason}
                    for l in r.lines
                ],
                "allowed_cents": r.allowed_cents,
                "paid_cents": r.paid_cents,
                "balance_cents": r.balance_cents,
                "decision_ids": r.decision_ids,
                "next_owner": r.next_owner,
                "reason": r.reason,
            }
            for r in results
        ],
        "requests": requests,
        "travel_cancellations": [p.as_record() for p in processes],
        "admitted_event_ids": event_ids,
        "issues": issues,
    }


CSV_COLUMNS = ["claim_id", "revision", "trip_id", "status", "allowed_cents",
               "paid_cents", "balance_cents", "next_owner", "reason"]


def write_csv(path: Path, results: list[ClaimResult]) -> None:
    """Money is integer EUR cents, blank when unknown. Zero is a known amount."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = _csv.writer(fh)
        writer.writerow(CSV_COLUMNS)
        for r in results:
            writer.writerow([
                r.claim.claim_id, r.claim.revision, r.claim.trip_id, r.status,
                "" if r.allowed_cents is None else r.allowed_cents,
                r.paid_cents,
                "" if r.balance_cents is None else r.balance_cents,
                r.next_owner or "", r.reason,
            ])
