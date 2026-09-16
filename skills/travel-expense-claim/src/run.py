"""Orchestrator: fetch -> retain -> normalise -> evaluate -> seal snapshot -> CSV.

Batches are processed in ascending arrival order. Each snapshot binds its predecessor by
relative path and SHA-256, and a sealed batch file is never rewritten: recomputation is
forward-only, so a later correction produces a new snapshot rather than editing history.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from . import cancellations, finance, normalise, pipeline, repair, report, sources
from .evaluate import Registers, budget_position


def _run_id() -> str:
    """Identifies the run artifact. All business dates use the fixed case clock instead;
    the machine's date never enters a business decision."""
    return "run-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default="artifacts/runs")
    ap.add_argument("--batches", default="1,2,3,4",
                    help="comma separated arrival batches to process, in order")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args(argv)

    run_id = args.run_id or _run_id()
    root = Path(args.artifacts) / run_id
    root.mkdir(parents=True, exist_ok=True)
    print(f"run_id  {run_id}")

    # ---------------------------------------------------------------- fetch
    print("\n[fetch] fresh read of five sources")
    policy_src, policy_doc = sources.fetch_policy(root)
    print(f"  policy            {policy_doc['version']}  "
          f"{policy_src.counts['content_blocks']} blocks  sha {policy_src.sha256[:12]}")
    register_srcs, tables = sources.fetch_registers(root)
    pdf_srcs, pdf_pages = sources.fetch_pdfs(root)
    for s in register_srcs + pdf_srcs:
        label = s.locator.get("tab") or s.source_id
        count = s.counts.get("csv_rows") or s.counts.get("pages")
        print(f"  {label:22} {count:>4}  sha {s.sha256[:12]}")

    all_srcs = [policy_src] + register_srcs + pdf_srcs
    sources_rel = sources.write_sources_json(root, all_srcs, run_id)
    source_binding = {"path": sources_rel, "sha256": _sha256(root / sources_rel)}
    print(f"  sources.json      sha {source_binding['sha256'][:12]}")

    # ------------------------------------------------------------ normalise
    reg = Registers(tables, normalise)
    receipts = {r.cost_id: r for r in normalise.parse_receipt_pages(pdf_pages["receipts"])}
    docs = (normalise.parse_claim_pages(pdf_pages["initial_claims"], "initial_claims")
            + normalise.parse_claim_pages(pdf_pages["claim_updates"], "claim_updates"))
    print(f"\n[normalise] {len(docs)} claim documents, {len(receipts)} receipts")

    predecessor = None
    snapshots = []
    snapshot_hashes: dict[str, str] = {}
    entries: list[dict] = []
    for batch_str in args.batches.split(","):
        batch = int(batch_str.strip())
        predecessor, snap, issue_objs = _process_batch(
            batch, root, run_id, reg, docs, receipts, source_binding, predecessor)
        snapshots.append(snap)
        snapshot_hashes[snap["batch_id"]] = predecessor["sha256"]
        claims_by_id = {c["claim_id"]: c for c in snap["claims"]}
        entries = repair.carry_forward(
            entries, repair.build(issue_objs, claims_by_id, str(batch)))

    # ----------------------------------------------------- queue and report
    last_batch = snapshots[-1]["batch_id"]
    (root / "repair-queue.json").write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "repair-queue.md").write_text(
        repair.render(entries, {c["claim_id"]: c for c in snapshots[-1]["claims"]},
                      last_batch), encoding="utf-8")
    sources_doc = json.loads((root / "sources.json").read_text(encoding="utf-8"))
    (root / "report.md").write_text(
        report.render(run_id, snapshots, entries, sources_doc, snapshot_hashes),
        encoding="utf-8")
    print(f"\n[deliverables] repair-queue.md ({len(entries)} entries), report.md, "
          f"claims.csv, {len(snapshots)} sealed snapshots")
    return 0


def _process_batch(batch: int, root: Path, run_id: str, reg: Registers, docs, receipts,
                   source_binding, predecessor):
    print(f"\n{'=' * 62}\n[batch {batch}]\n{'=' * 62}")
    current = pipeline.claims_present(docs, batch)

    events = finance.admit(reg.finance_activity, batch)
    money_map = finance.money_by_claim(
        events, finance.arrival_batches(reg.finance_activity))
    print(f"  claims present    {len(current)}   "
          f"(revisions above 1: "
          f"{sorted((c, d.revision) for c, d in current.items() if d.revision > 1)})")
    print(f"  finance events    {len(events.ids())} admitted, "
          f"{len(events.replays)} exact replays, {len(events.conflicts)} conflicts")
    if events.replays:
        print(f"     replayed        {sorted(set(events.replays))}")

    links = pipeline.prior_settled_links(docs, current, money_map)
    for claim_id, mapping in sorted(links.items()):
        for cost_id, ref in sorted(mapping.items()):
            print(f"  prepaid link      {claim_id}.{cost_id} excluded, settled under {ref}")

    # A cancellation keeps its financial history even after the claim is reassigned to
    # another trip. block 15: "Continue observing original requests after cancellation
    # or claim reassignment, including late transfers." So the cancellation-side link is
    # built from every arrived revision, while the claim-side finding (cancel_index) stays
    # keyed on the claim's current trip, because block 13 forbids an old trip's
    # cancellation from retiring the new one.
    trip_history = defaultdict(set)
    for doc in docs:
        if doc.arrival_batch <= batch and doc.claim_id in current:
            trip_history[doc.trip_id].add(doc.claim_id)
    claims_by_trip = {trip: sorted(ids) for trip, ids in trip_history.items()}
    request_ids = {cid: finance.request_id_for(cid) for cid in current}
    exceptions_by_claim = {cid: d.exception for cid, d in current.items() if d.exception}

    processes, cancel_issues, cancel_event_ids = cancellations.build(
        reg.cancellations, batch, reg, claims_by_trip, request_ids, exceptions_by_claim)
    cancel_index = defaultdict(list)
    for proc in processes:
        cancel_index[proc.trip_id].append(proc)
    print(f"  cancellations     {len(processes)} processes from "
          f"{len(cancel_event_ids)} admitted events")

    results = []
    for claim_id in sorted(current, key=lambda c: (len(c), c)):
        results.append(pipeline.evaluate_claim(
            current[claim_id], reg, receipts, money_map, batch,
            links.get(claim_id, {}), cancel_index))

    requests = []
    accepted_commitment_cents = 0
    for r in results:
        m = money_map.get(r.claim.claim_id, finance.ClaimMoney())
        req = pipeline.build_request(r, m, reg)
        if req is not None:
            requests.append(req)
            if req["status"] in ("accepted", "settled", "cancel-pending", "held"):
                accepted_commitment_cents += req["amount_cents"]

    pipeline.resolve_original_requests(processes, requests)

    net_settled = sum(m.net_paid_cents for m in money_map.values())
    budget = budget_position(reg, accepted_commitment_cents, net_settled)

    # One entry is one (subject, version, missing fact). A gap in a shared source -- a
    # missing rate or cap -- is one entry that accumulates every claim it blocks, so
    # repairing that single row is visibly worth more than repairing one claim.
    issues_by_id = {}
    for iss in [i for r in results for i in r.issues] + cancel_issues + events.issues:
        seen = issues_by_id.get(iss.record_id)
        if seen is None:
            issues_by_id[iss.record_id] = iss
            continue
        seen.blocks = sorted({*seen.blocks, *iss.blocks})
        seen.source_refs = sorted({*seen.source_refs, *iss.source_refs})
    issue_objs = [issues_by_id[k] for k in sorted(issues_by_id)]
    issues = [i.as_record() for i in issue_objs]

    snap = pipeline.snapshot(run_id, str(batch), predecessor, source_binding,
                             results, requests, processes, events.ids(), issues)
    snap["budget_position"] = budget

    batches_dir = root / "batches"
    batches_dir.mkdir(exist_ok=True)
    out = batches_dir / f"{batch}.json"
    if out.exists():
        raise RuntimeError(f"refusing to rewrite sealed snapshot {out}")
    out.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    digest = _sha256(out)
    print(f"  sealed            batches/{batch}.json sha {digest[:12]}  "
          f"predecessor={'null' if predecessor is None else predecessor['path']}")

    pipeline.write_csv(root / "claims.csv", results)

    by_status = defaultdict(int)
    for r in results:
        by_status[r.status] += 1
    for status in sorted(by_status):
        print(f"     {status:20} {by_status[status]}")
    req_status = defaultdict(int)
    for q in requests:
        req_status[q["status"]] += 1
    print(f"  requests          {len(requests)}  " +
          ", ".join(f"{k}={v}" for k, v in sorted(req_status.items())))
    print(f"  issues            {len(issues)}")
    print(f"  net paid          {net_settled} cents")
    print(f"  budget remaining  {budget['remaining_cents']} cents")
    return {"path": f"batches/{batch}.json", "sha256": digest}, snap, issue_objs


if __name__ == "__main__":
    raise SystemExit(main())
