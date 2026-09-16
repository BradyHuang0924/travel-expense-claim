"""Business travel cancellation processes, kept separate from Finance events.

block 15: "Finance admitted event references remain separate from cancellation event
references." The two id sets produced here and in finance.py are disjoint by
construction and checked in verify.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import policy
from .evaluate import Issue
from .normalise import utc_timestamp

_IDENTITY_EXCLUDED = {"Arrival batch"}


@dataclass
class Process:
    cancellation_id: str
    target_type: str
    trip_id: str
    trip_revision: int
    permit_id: str | None
    permit_revision: int | None
    status: str
    event_ids: list[str]
    requested_at: str
    confirmed_at: str | None
    effective_at: str | None
    affected_claim_ids: list[str]
    original_request_ids: list[str]
    financial_status: str
    next_owner: str | None
    reason: str
    issue_record_ids: list[str]
    confirmed_batch: int | None = None

    def admitted_cancellation_event_ids(self) -> list[str]:
        return list(self.event_ids)

    def as_record(self) -> dict:
        return {
            "cancellation_id": self.cancellation_id,
            "target_type": self.target_type,
            "trip_id": self.trip_id,
            "trip_revision": self.trip_revision,
            "permit_id": self.permit_id,
            "permit_revision": self.permit_revision,
            "status": self.status,
            "admitted_cancellation_event_ids": self.event_ids,
            "requested_at": self.requested_at,
            "confirmed_at": self.confirmed_at,
            "effective_at": self.effective_at,
            "affected_claim_ids": self.affected_claim_ids,
            "original_request_ids": self.original_request_ids,
            "financial_status": self.financial_status,
            "next_owner": self.next_owner,
            "reason": self.reason,
            "issue_record_ids": self.issue_record_ids,
        }


def _payload(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in _IDENTITY_EXCLUDED}


def build(rows: list[dict], upto_batch: int, reg, claims_by_trip: dict[str, list[str]],
          request_ids: dict[str, str], exceptions_by_claim: dict[str, object]
          ) -> tuple[list[Process], list[Issue], list[str]]:
    """Returns (processes, issues, admitted cancellation event ids)."""
    issues: list[Issue] = []
    admitted: dict[str, dict] = {}
    order: list[str] = []
    replays: list[str] = []
    batch_of: dict[str, int] = {}

    for row in rows:
        if int(row["Arrival batch"]) > upto_batch:
            continue          # block 13: consume only in the arrival batch or later
        ref = row["Cancellation activity reference"]
        payload = _payload(row)
        if ref in admitted:
            if admitted[ref] == payload:
                replays.append(ref)           # exact redelivery is a no-op
            else:
                issues.append(Issue(
                    f"ISS-CANCEL-CONFLICTING-REPLAY-{ref}",
                    f"Cancellation event {ref} was redelivered with a different payload.",
                    "ADMIN-01",
                    "Supply the authoritative payload for this cancellation event.",
                    subject_type="travel_cancellation",
                    subject_ref=row.get("Cancellation reference", ref),
                    source_refs=[ref], kind="cancel_conflicting_replay"))
            continue
        admitted[ref] = payload
        order.append(ref)
        batch_of[ref] = int(row["Arrival batch"])

    grouped: dict[str, list[dict]] = {}
    for ref in order:
        row = dict(admitted[ref], **{"Cancellation activity reference": ref})
        grouped.setdefault(row["Cancellation reference"], []).append(row)

    processes: list[Process] = []
    for cid, group in grouped.items():
        requests = [r for r in group if r["Action"] == "requested"]
        confirms = [r for r in group if r["Action"] == "confirmed"]

        if len(requests) > 1 or len(confirms) > 1:
            issues.append(Issue(
                f"ISS-CANCEL-MULTIPLE-ACTIONS-{cid}",
                f"Cancellation process {cid} has more than one initiation or "
                f"confirmation; one process has one of each.",
                "ADMIN-01",
                "Supply which initiation and confirmation are authoritative.",
                subject_type="travel_cancellation", subject_ref=cid,
                source_refs=[r["Cancellation activity reference"] for r in group],
                kind="cancel_multiple_actions"))

        if not requests:
            # block 13: a confirmation whose request has not arrived is an unresolved
            # reference, rechecked when the request arrives. No process is established.
            issues.append(Issue(
                f"ISS-CANCEL-ORPHAN-CONFIRMATION-{cid}",
                f"Confirmation for {cid} arrived with no matching initiation; sheet row "
                f"order is not authority.",
                "ADMIN-01",
                "Deliver the initiating request event, or withdraw the confirmation.",
                subject_type="travel_cancellation", subject_ref=cid,
                source_refs=[r["Cancellation activity reference"] for r in group],
                kind="cancel_orphan_confirmation"))
            continue

        req = requests[0]
        trip = reg.trips.get(req["Trip reference"]) or {}
        employee = trip.get("Employee ID")
        people_row = reg.people.get(employee, {})
        supervisor = people_row.get("Supervisor")

        event_ids = [req["Cancellation activity reference"]]
        status = "requested"
        confirmed_at = None
        effective_at = None
        process_issue_ids: list[str] = []

        conf = confirms[0] if confirms else None
        confirmed_batch = None
        if conf is not None:
            ok = True
            # block 12: only the directory supervisor for that employee may confirm.
            if conf["Acting employee or supervisor"] != supervisor:
                ok = False
                iss = Issue(
                    f"ISS-CANCEL-WRONG-ACTOR-{cid}",
                    f"{cid} confirmed by {conf['Acting employee or supervisor']}, who is "
                    f"not the directory supervisor ({supervisor}) for {employee}.",
                    "ADMIN-01",
                    "Supply a confirmation from the directory supervisor.",
                    subject_type="travel_cancellation", subject_ref=cid,
                    source_refs=event_ids, kind="cancel_wrong_actor")
                issues.append(iss)
                process_issue_ids.append(iss.record_id)
            # block 13: the confirmation names the exact matching request.
            if conf.get("Initiation activity reference") != req["Cancellation activity reference"]:
                ok = False
                iss = Issue(
                    f"ISS-CANCEL-UNMATCHED-INITIATION-{cid}",
                    f"{cid} confirmation does not name its matching initiation event.",
                    "ADMIN-01",
                    "Supply a confirmation naming the exact initiating event reference.",
                    subject_type="travel_cancellation", subject_ref=cid,
                    source_refs=event_ids, kind="cancel_unmatched_initiation")
                issues.append(iss)
                process_issue_ids.append(iss.record_id)
            # block 12: occurs strictly later, effective at its own occurrence time.
            t_req = utc_timestamp(req["Activity time (UTC)"])
            t_conf = utc_timestamp(conf["Activity time (UTC)"])
            t_eff = utc_timestamp(conf.get("Effective time (UTC)", ""))
            if not (t_conf and t_req and t_conf > t_req):
                ok = False
                iss = Issue(
                    f"ISS-CANCEL-NOT-LATER-{cid}",
                    f"{cid} confirmation does not occur strictly later than its request.",
                    "ADMIN-01", "Supply a confirmation with a valid later occurrence time.",
                    subject_type="travel_cancellation", subject_ref=cid,
                    source_refs=event_ids, kind="cancel_not_later")
                issues.append(iss)
                process_issue_ids.append(iss.record_id)
            if t_eff is not None and t_conf is not None and t_eff != t_conf:
                ok = False
                iss = Issue(
                    f"ISS-CANCEL-SCHEDULED-EFFECT-{cid}",
                    f"{cid} effective time differs from its occurrence time; scheduled "
                    f"or backdated effective times are not supported.",
                    "ADMIN-01", "Supply a confirmation effective at its occurrence time.",
                    subject_type="travel_cancellation", subject_ref=cid,
                    source_refs=event_ids, kind="cancel_scheduled_effect")
                issues.append(iss)
                process_issue_ids.append(iss.record_id)
            if ok:
                confirmed_batch = batch_of.get(
                    conf["Cancellation activity reference"])
                status = "confirmed"
                confirmed_at = t_conf
                effective_at = t_conf
                event_ids.append(conf["Cancellation activity reference"])

        affected = sorted(claims_by_trip.get(req["Trip reference"], []))
        original_requests = sorted({request_ids[c] for c in affected if c in request_ids})

        financial_status, reason, next_owner = _consequence(
            cid, status, affected, exceptions_by_claim, supervisor, req)
        if financial_status == "unresolved" and status == "confirmed" and affected:
            iss = Issue(
                f"ISS-CANCEL-NO-BOUND-DISPOSITION-{cid}",
                f"Confirmed cancellation {cid} affects {', '.join(affected)} but no "
                f"Finance cost disposition names this travel_cancellation_id. The "
                f"supplied exception does not carry a travel_cancellation_id, and the "
                f"link is not recovered from any other source.",
                "FIN-01",
                f"Supply an explicit Finance exception that itself states the exact "
                f"travel_cancellation_id {cid}, bound actor, claim/revision, expense, "
                f"replacement allowed original amount and reason.",
                subject_type="travel_cancellation", subject_ref=cid,
                subject_revision=int(req["Trip revision"]),
                source_refs=event_ids, blocks=affected,
                kind="cancel_no_bound_disposition")
            issues.append(iss)
            process_issue_ids.append(iss.record_id)

        permit_id = req.get("Permit reference") or None
        permit_rev = req.get("Permit revision") or None
        processes.append(Process(
            cancellation_id=cid,
            target_type=req["Cancelled subject"],
            trip_id=req["Trip reference"],
            trip_revision=int(req["Trip revision"]),
            permit_id=permit_id,
            permit_revision=int(permit_rev) if permit_id and permit_rev else None,
            status=status,
            event_ids=event_ids,
            requested_at=utc_timestamp(req["Activity time (UTC)"]),
            confirmed_at=confirmed_at,
            effective_at=effective_at,
            affected_claim_ids=affected,
            original_request_ids=original_requests,
            financial_status=financial_status,
            next_owner=next_owner,
            reason=reason,
            issue_record_ids=process_issue_ids,
            confirmed_batch=confirmed_batch,
        ))
    return processes, issues, order


def _consequence(cid, status, affected, exceptions_by_claim, supervisor, req):
    """block 14 decides the financial consequence."""
    if status == "requested":
        # "A valid request pauses new affected arrangements and payment readiness while
        # the supervisor decides; it is not confirmed cancellation and changes no
        # Finance request, accepted commitment or money."
        return ("unresolved",
                f"Initiation recorded; awaiting the directory supervisor's decision. "
                f"Payment readiness on affected claims is paused, and no Finance "
                f"request, accepted commitment or money is changed. Business reason: "
                f"{req.get('Business reason', '')}",
                supervisor)
    if not affected:
        # "Confirmed cancellation without costs or financial obligations is recorded as
        # a no-financial-effect trip/permit process, without inventing a claim."
        return ("no-financial-effect",
                "Confirmed cancellation with no claim, cost or financial obligation; "
                "recorded as a no-financial-effect process without inventing a claim.",
                None)
    # Confirmed with costs: needs an exception that itself binds this cancellation id.
    for claim_id in affected:
        exc = exceptions_by_claim.get(claim_id)
        if (exc is not None
                and "travel_cancellation" in exc.covered_issues
                and exc.travel_cancellation_id == cid):
            return ("resolved",
                    f"Confirmed cancellation with an explicit Finance cost disposition "
                    f"bound to {cid}.", None)
    return ("unresolved",
            f"Confirmed cancellation affecting {', '.join(affected)} with no Finance "
            f"cost disposition naming this travel_cancellation_id. An amount-only or "
            f"unrelated exception does not resolve it, and the binding is not inferred "
            f"from review packets or any other source.",
            "FIN-01")
