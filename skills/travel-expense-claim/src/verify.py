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

    # 13. an unchanged replay preserves obligation and money identity across batches
    if len(snaps) > 1:
        docs = [json.loads(p.read_text(encoding="utf-8")) for p in snaps]
        drift = []
        for prev, cur in zip(docs, docs[1:]):
            prev_req = {r["request_id"]: r["claim_id"] for r in prev["requests"]}
            cur_req = {r["request_id"]: r["claim_id"] for r in cur["requests"]}
            for rid, cid in prev_req.items():
                if rid in cur_req and cur_req[rid] != cid:
                    drift.append(f"{rid} moved claim {cid}->{cur_req[rid]}")
            prev_paid = {c["claim_id"]: c["paid_cents"] for c in prev["claims"]}
            for c in cur["claims"]:
                was = prev_paid.get(c["claim_id"])
                if was is not None and c["paid_cents"] < was:
                    drift.append(f"{c['claim_id']} paid_cents fell {was}->{c['paid_cents']}")
            prev_events = set(prev["admitted_event_ids"])
            if not prev_events <= set(cur["admitted_event_ids"]):
                drift.append("admitted_event_ids shrank between batches")
        out.append((not drift,
                    "across batches: request identity stable, admitted money never "
                    "reduced, event ids monotonic"
                    + (f" -- {drift}" if drift else "")))
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
