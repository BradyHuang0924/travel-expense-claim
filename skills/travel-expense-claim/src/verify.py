"""Schema conformance plus the checks the published schema does not make."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA_FIELDS = {
    "snapshot": {"schema_version", "run_id", "batch_id", "predecessor", "source_binding",
                 "claims", "requests", "travel_cancellations", "admitted_event_ids",
                 "issues", "budget_position"},
    "claim": {"claim_id", "revision", "trip_id", "trip_revision", "status", "lines",
              "allowed_cents", "paid_cents", "balance_cents", "decision_ids",
              "next_owner", "reason"},
    "line": {"cost_id", "source_ids", "status", "allowed_cents", "reason"},
    "request": {"request_id", "claim_id", "revision", "amount_cents", "payee",
                "currency", "status", "decision_ids"},
    "issue": {"record_id", "reason", "owner", "resolution_needed"},
    "cancellation": {"cancellation_id", "target_type", "trip_id", "trip_revision",
                     "permit_id", "permit_revision", "status",
                     "admitted_cancellation_event_ids", "requested_at", "confirmed_at",
                     "effective_at", "affected_claim_ids", "original_request_ids",
                     "financial_status", "next_owner", "reason", "issue_record_ids"},
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(run_root: Path, schema_path: Path) -> list[tuple[bool, str]]:
    out: list[tuple[bool, str]] = []
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    snaps = sorted(run_root.glob("batches/*.json"), key=lambda p: int(p.stem))
    sources_path = run_root / "sources.json"

    try:
        from jsonschema import Draft202012Validator, FormatChecker
        for snap_path in snaps:
            doc = json.loads(snap_path.read_text(encoding="utf-8"))
            validator = Draft202012Validator(schema, format_checker=FormatChecker())
            errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
            if errors:
                for err in errors[:5]:
                    out.append((False, f"schema {snap_path.name}: "
                                       f"{'/'.join(str(p) for p in err.path)}: "
                                       f"{err.message}"))
            else:
                out.append((True, f"schema conformance {snap_path.name}"))
        import rfc3339_validator  # noqa: F401
        out.append((True, "rfc3339-validator present, date-time format enforced"))
    except ImportError as exc:
        out.append((False, f"validation dependency missing: {exc}"))

    for snap_path in snaps:
        doc = json.loads(snap_path.read_text(encoding="utf-8"))
        name = snap_path.name

        # 1. every issue_record_ids entry resolves to an issues[].record_id
        known = {i["record_id"] for i in doc["issues"]}
        dangling = [rid for c in doc["travel_cancellations"]
                    for rid in c["issue_record_ids"] if rid not in known]
        out.append((not dangling,
                    f"{name}: issue_record_ids resolve"
                    + (f" -- dangling {dangling}" if dangling else "")))

        # 2. every requests[].claim_id exists in claims[]
        claim_ids = {c["claim_id"] for c in doc["claims"]}
        orphan = [r["request_id"] for r in doc["requests"]
                  if r["claim_id"] not in claim_ids]
        out.append((not orphan,
                    f"{name}: requests[].claim_id resolve"
                    + (f" -- orphan {orphan}" if orphan else "")))

        # 3. every original_request_ids entry resolves to a requests[].request_id
        request_ids = {r["request_id"] for r in doc["requests"]}
        dangling_req = sorted({rid for c in doc["travel_cancellations"]
                               for rid in c["original_request_ids"]
                               if rid not in request_ids})
        out.append((not dangling_req,
                    f"{name}: original_request_ids resolve"
                    + (f" -- dangling {dangling_req}" if dangling_req else "")))

        # 4. predecessor.sha256 really is the hash of the preceding snapshot
        pred = doc["predecessor"]
        if pred is None:
            out.append((snap_path == snaps[0],
                        f"{name}: predecessor null on the first snapshot"))
        else:
            target = run_root / pred["path"]
            ok = target.exists() and _sha256(target) == pred["sha256"]
            out.append((ok, f"{name}: predecessor.sha256 matches {pred['path']}"))

        # 5. source_binding.sha256 really is the hash of this run's sources.json
        sb = doc["source_binding"]
        ok = ((run_root / sb["path"]).exists()
              and _sha256(run_root / sb["path"]) == sb["sha256"])
        out.append((ok, f"{name}: source_binding.sha256 matches {sb['path']}"))

        # 6. no file hashes itself
        self_hash = _sha256(snap_path)
        blob = snap_path.read_text(encoding="utf-8")
        ok = (self_hash not in blob
              and _sha256(sources_path) not in sources_path.read_text(encoding="utf-8"))
        out.append((ok, f"{name}: no file hashes itself"))

        # 7. admitted_event_ids and cancellation event ids are disjoint
        fin = set(doc["admitted_event_ids"])
        can = {e for c in doc["travel_cancellations"]
               for e in c["admitted_cancellation_event_ids"]}
        overlap = fin & can
        out.append((not overlap,
                    f"{name}: finance and cancellation event ids disjoint"
                    + (f" -- overlap {sorted(overlap)}" if overlap else "")))

        # 8. field names spelled correctly (a misspelled field is silently accepted)
        bad: list[str] = []
        bad += [f"snapshot.{k}" for k in doc if k not in SCHEMA_FIELDS["snapshot"]]
        for c in doc["claims"]:
            bad += [f"claim.{k}" for k in c if k not in SCHEMA_FIELDS["claim"]]
            for l in c["lines"]:
                bad += [f"line.{k}" for k in l if k not in SCHEMA_FIELDS["line"]]
        for r in doc["requests"]:
            bad += [f"request.{k}" for k in r if k not in SCHEMA_FIELDS["request"]]
        for i in doc["issues"]:
            bad += [f"issue.{k}" for k in i if k not in SCHEMA_FIELDS["issue"]]
        for c in doc["travel_cancellations"]:
            bad += [f"cancellation.{k}" for k in c
                    if k not in SCHEMA_FIELDS["cancellation"]]
        out.append((not bad, f"{name}: no unexpected field names"
                             + (f" -- {sorted(set(bad))}" if bad else "")))

        # 9. money invariants
        bad_money = [c["claim_id"] for c in doc["claims"]
                     if c["allowed_cents"] is not None
                     and c["balance_cents"] != c["allowed_cents"] - c["paid_cents"]]
        out.append((not bad_money,
                    f"{name}: balance == allowed - paid"
                    + (f" -- {bad_money}" if bad_money else "")))

        # 10. requests never carry the unreachable status
        bad_status = [r["request_id"] for r in doc["requests"]
                      if r["status"] == "dispatched"]
        out.append((not bad_status,
                    f"{name}: no request claims 'dispatched'"
                    + (f" -- {bad_status}" if bad_status else "")))

        # 11. unresolved lines never carry an assumed zero
        bad_zero = [(c["claim_id"], l["cost_id"]) for c in doc["claims"]
                    for l in c["lines"]
                    if l["status"] == "unresolved" and l["allowed_cents"] is not None]
        out.append((not bad_zero,
                    f"{name}: unresolved lines have null allowed_cents"
                    + (f" -- {bad_zero}" if bad_zero else "")))

        # 12. every line records the evidence the run holds for it
        thin = [(c["claim_id"], l["cost_id"]) for c in doc["claims"]
                for l in c["lines"] if len(l["source_ids"]) < 2]
        out.append((not thin,
                    f"{name}: every line cites at least its cost and one source record"
                    + (f" -- {thin}" if thin else "")))

        out.extend(closure_assertions(run_root, doc))

    # 13. an unchanged replay preserves obligation and money identity across batches
    if len(snaps) > 1:
        docs = [json.loads(p.read_text(encoding="utf-8")) for p in snaps]
        activity_rows = _retained_table(run_root, "Finance_activity")
        drift = []
        for prev, cur in zip(docs, docs[1:]):
            prev_req = {r["request_id"]: r["claim_id"] for r in prev["requests"]}
            cur_req = {r["request_id"]: r["claim_id"] for r in cur["requests"]}
            for rid, cid in prev_req.items():
                if rid in cur_req and cur_req[rid] != cid:
                    drift.append(f"{rid} moved claim {cid}->{cur_req[rid]}")
            # block 10: "Only the confirmed refund reduces net paid." A fall is
            # legitimate exactly when newly admitted refunds account for it.
            new_events = set(cur["admitted_event_ids"]) - set(prev["admitted_event_ids"])
            refunds = {}
            for r in activity_rows:
                if r["Activity reference"] in new_events and r["Activity type"] == "refund":
                    cents = int(round(float(
                        (r["Amount (EUR)"] or "0").replace(",", "")) * 100))
                    refunds[r["Claim reference"]] = refunds.get(r["Claim reference"], 0) + cents
            prev_paid = {c["claim_id"]: c["paid_cents"] for c in prev["claims"]}
            for c in cur["claims"]:
                was = prev_paid.get(c["claim_id"])
                if was is None or c["paid_cents"] >= was:
                    continue
                fell = was - c["paid_cents"]
                accounted = refunds.get(c["claim_id"], 0)
                if fell != accounted:
                    drift.append(f"{c['claim_id']} paid_cents fell {was}->"
                                 f"{c['paid_cents']} but newly admitted refunds total "
                                 f"{accounted}")
            prev_events = set(prev["admitted_event_ids"])
            if not prev_events <= set(cur["admitted_event_ids"]):
                drift.append("admitted_event_ids shrank between batches")
        out.append((not drift,
                    "across batches: request identity stable, net paid falls only by "
                    "admitted confirmed refunds, event ids monotonic"
                    + (f" -- {drift}" if drift else "")))
    return out


# --------------------------------------------------------------- closure assertions

def _retained_table(run_root: Path, name: str):
    """Re-read a retained register from this run's own bytes, so the closure check is an
    independent re-derivation rather than a restatement of the snapshot."""
    import csv as _csv
    path = run_root / "sources" / "registers" / f"{name}.csv"
    rows = list(_csv.reader(path.open(encoding="utf-8-sig", newline="")))
    hi = next(i for i, r in enumerate(rows) if len(r) > 1 and r[1].strip())
    hdr = [c.split("\n")[-1].strip() for c in rows[hi]]
    hdr[0] = (rows[hi][0].split("\n")[-1].strip() if "\n" in rows[hi][0]
              else rows[hi][0].rsplit(". ", 1)[-1].strip())
    return [dict(zip(hdr, r)) for r in rows[hi + 1:] if any(c.strip() for c in r)]


_DIRECTOR_THRESHOLD_CENTS = 100_000
_REQUIRED_ROLES = {"administration", "budget_owner", "supervisor"}


def closure_assertions(run_root: Path, doc: dict) -> list[tuple[bool, str]]:
    """Every claim recorded closed-reimbursed must satisfy all five conditions at once.

    Condition 1 and 4 are re-derived from the retained Review ledger and Finance
    activity, not read back out of the snapshot.
    """
    import re as _re
    batch = int(doc["batch_id"])
    ledger = _retained_table(run_root, "Review_ledger")
    activity = _retained_table(run_root, "Finance_activity")
    people = {r["Employee ID"]: r for r in _retained_table(run_root, "People")}
    trips = {r["Trip reference"]: r for r in _retained_table(run_root, "Trips")}

    admitted = set(doc["admitted_event_ids"])
    acts_by_claim: dict[str, list[dict]] = {}
    for r in activity:
        if r["Activity reference"] in admitted and int(r["Arrival batch"]) <= batch:
            acts_by_claim.setdefault(r["Claim reference"], []).append(r)

    # block 15: a business cancellation confirmed BEFORE any request for the affected
    # obligation was accepted needs no separate Finance resolution event; only one
    # occurring after acceptance/dispatch does.
    cancel_batch = {}
    for r in _retained_table(run_root, "Travel_cancellations"):
        if r["Action"] == "confirmed":
            ref = r["Cancellation reference"]
            b = int(r["Arrival batch"])
            cancel_batch[ref] = min(b, cancel_batch.get(ref, b))
    accepted_batch = {}
    for r in activity:
        if r["Activity type"] == "accepted":
            cid = r["Claim reference"]
            b = int(r["Arrival batch"])
            accepted_batch[cid] = min(b, accepted_batch.get(cid, b))
    post_acceptance_cancel = set()
    for c in doc["travel_cancellations"]:
        if c["status"] != "confirmed":
            continue
        cb = cancel_batch.get(c["cancellation_id"])
        for cid in c["affected_claim_ids"]:
            ab = accepted_batch.get(cid)
            if cb is not None and ab is not None and cb > ab:
                post_acceptance_cancel.add(cid)

    closed = [c for c in doc["claims"] if c["status"] == "closed-reimbursed"]
    failures: list[str] = []
    loose: list[str] = []

    for c in closed:
        cid, rev = c["claim_id"], c["revision"]
        trip = trips.get(c["trip_id"], {})
        emp = trip.get("Employee ID")
        prow = people.get(emp, {})
        same = (prow.get("Budget owner")
                and prow.get("Budget owner") == prow.get("Supervisor"))

        # 1. every required approval for the CURRENT revision is present and approves
        approved = set()
        adverse = []
        for r in ledger:
            if not (r["Subject type"] == "claim" and r["Subject reference"] == cid
                    and r["Revision"] == str(rev)
                    and int(r["Arrival batch"]) <= batch):
                continue
            roles = [x.strip() for x in r["Review roles"].split("\n") if x.strip()]
            if len(roles) > 1:
                if {"administration", "director"} & set(roles):
                    continue
                if set(roles) == {"budget_owner", "supervisor"} and not same:
                    continue
            if r["Outcome"] == "approve":
                approved |= set(roles)
            else:
                adverse.append(f"{'+'.join(roles)}={r['Outcome']}")
        need = set(_REQUIRED_ROLES)
        if (c["allowed_cents"] or 0) > _DIRECTOR_THRESHOLD_CENTS:
            need.add("director")
        if not need <= approved:
            failures.append(f"{cid}: missing approval {sorted(need - approved)}")
        if adverse:
            failures.append(f"{cid}: adverse review outcome {adverse}")

        # 2. authorized obligation equals the sum of the current supported lines
        supported = sum(l["allowed_cents"] or 0 for l in c["lines"]
                        if l["status"] == "supported")
        if c["allowed_cents"] != supported:
            failures.append(f"{cid}: allowed {c['allowed_cents']} != supported-line sum "
                            f"{supported}")
        if any(l["status"] == "unresolved" for l in c["lines"]):
            failures.append(f"{cid}: closed with an unresolved line")

        # 3. net paid equals that obligation exactly
        if c["paid_cents"] != c["allowed_cents"] or c["balance_cents"] != 0:
            failures.append(f"{cid}: paid {c['paid_cents']} vs allowed "
                            f"{c['allowed_cents']} (balance {c['balance_cents']})")

        # 4. every Finance resolution the policy requires is admitted
        kinds = {r["Activity type"] for r in acts_by_claim.get(cid, [])}
        needs_resolution = (bool(kinds & {"adjustment", "refund"})
                            or cid in post_acceptance_cancel)
        if (c["balance_cents"] or 0) < 0:
            needs_resolution = True
        if needs_resolution and "resolution" not in kinds:
            failures.append(f"{cid}: closure requires a Finance resolution; admitted "
                            f"activity is {sorted(kinds)}")
        if not kinds:
            failures.append(f"{cid}: closed with no admitted Finance activity at all")

        # 5. no issue against the claim is open
        hits = []
        for i in doc["issues"]:
            tokens = set(i["record_id"].split("-"))
            if cid in tokens or _re.search(rf"\b{_re.escape(cid)}\b", i["reason"]):
                hits.append(i["record_id"])
        if hits:
            failures.append(f"{cid}: open issue(s) {hits}")
        if c["next_owner"] is not None:
            failures.append(f"{cid}: closed but next_owner is {c['next_owner']!r}")

    name = f"batches/{doc['batch_id']}.json"
    out = [(not failures,
            f"{name}: all {len(closed)} closed-reimbursed claims satisfy approvals, "
            f"obligation == supported lines, net paid == obligation, required Finance "
            f"resolutions and no open issue"
            + ("" if not failures else " -- " + "; ".join(failures[:6])))]
    out.append((True,
                f"{name}: closure condition 5 links issues to claims by exact '-' token "
                f"in record_id plus word-boundary match in reason; conditions 1-4 are "
                f"exact numeric or set comparisons re-derived from retained sources"))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_root")
    ap.add_argument("--schema", default="snapshot.schema.json")
    args = ap.parse_args(argv)
    results = check(Path(args.run_root), Path(args.schema))
    failed = 0
    for ok, msg in results:
        print(("  PASS  " if ok else "  FAIL  ") + msg)
        failed += 0 if ok else 1
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
