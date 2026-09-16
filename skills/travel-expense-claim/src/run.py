"""Orchestrator: fetch -> retain -> normalise -> evaluate -> seal snapshot -> CSV.

This revision covers batch 1 only. Later batches reuse the same per-batch path and add
the predecessor hash chain; nothing here writes to a batch file that already exists.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from . import cancellations, finance, normalise, pipeline, sources
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
    ap.add_argument("--batches", default="1",
                    help="comma separated arrival batches to process, in order")
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args(argv)

    run_id = args.run_id or _run_id()
    root = Path(args.artifacts) / run_id
    root.mkdir(parents=True, exist_ok=True)
    print(f"run_id  {run_id}")
    print(f"root    {root}")

    # ---------------------------------------------------------------- fetch
    print("\n[1/6] fresh read of five sources")
    policy_src, policy_doc = sources.fetch_policy(root)
    print(f"  policy            {policy_doc['version']}  "
          f"{policy_src.counts['content_blocks']} blocks  sha {policy_src.sha256[:12]}")
    register_srcs, tables = sources.fetch_registers(root)
    for s in register_srcs:
        print(f"  {s.locator['tab']:22} {s.counts['csv_rows']:>4} csv rows  "
              f"sha {s.sha256[:12]}")
    pdf_srcs, pdf_pages = sources.fetch_pdfs(root)
    for s in pdf_srcs:
        print(f"  {s.source_id:22} {s.counts['pages']:>4} pages     sha {s.sha256[:12]}")

    all_srcs = [policy_src] + register_srcs + pdf_srcs
    sources_rel = sources.write_sources_json(root, all_srcs, run_id)
    source_binding = {"path": sources_rel, "sha256": _sha256(root / sources_rel)}
    print(f"  sources.json      sha {source_binding['sha256'][:12]}")

    # ------------------------------------------------------------ normalise
    print("\n[2/6] normalise")
    reg = Registers(tables, normalise)
    receipts = {r.cost_id: r for r in normalise.parse_receipt_pages(pdf_pages["receipts"])}
    docs = (normalise.parse_claim_pages(pdf_pages["initial_claims"], "initial_claims")
            + normalise.parse_claim_pages(pdf_pages["claim_updates"], "claim_updates"))
    print(f"  claim documents   {len(docs)}")
    print(f"  receipts          {len(receipts)}")
    print(f"  register rows     " + ", ".join(
        f"{k}={len(normalise.table(v))}" for k, v in tables.items()))

    predecessor = None
    predecessor_path = None
    for batch_str in args.batches.split(","):
        batch = int(batch_str.strip())
        predecessor, predecessor_path = _process_batch(
            batch, root, run_id, reg, docs, receipts, source_binding,
            predecessor, predecessor_path)
    return 0


def _process_batch(batch: int, root: Path, run_id: str, reg: Registers, docs, receipts,
                   source_binding, predecessor, predecessor_path):
    print(f"\n[3/6] evaluate batch {batch}")
    current = pipeline.claims_present(docs, batch)

    events = finance.admit(reg.finance_activity, batch)
    money_map = finance.money_by_claim(events)
    print(f"  claims present    {len(current)}")
    print(f"  finance events    {len(events.ids())} admitted, "
          f"{len(events.replays)} exact replays, {len(events.conflicts)} conflicts")

    links = pipeline.prior_settled_links(docs, current, money_map)

    claims_by_trip = defaultdict(list)
    for claim_id, doc in current.items():
        claims_by_trip[doc.trip_id].append(claim_id)
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
            # Constraint: a held claim that already carries an accepted commitment still
            # counts against the shared ledger.
            if req["status"] in ("accepted", "settled", "cancel-pending", "held"):
                accepted_commitment_cents += req["amount_cents"]

    net_settled = sum(m.net_paid_cents for m in money_map.values())
    budget = budget_position(reg, accepted_commitment_cents, net_settled)

    issues_by_id = {}
    for r in results:
        for iss in r.issues:
            issues_by_id.setdefault(iss.record_id, iss)
    for iss in cancel_issues + events.issues:
        issues_by_id.setdefault(iss.record_id, iss)
    issues = [issues_by_id[k].as_record() for k in sorted(issues_by_id)]

    snap = pipeline.snapshot(run_id, str(batch), predecessor, source_binding,
                             results, requests, processes, events.ids(), issues)
    snap["budget_position"] = budget

    print(f"\n[4/6] seal batch {batch} snapshot")
    batches_dir = root / "batches"
    batches_dir.mkdir(exist_ok=True)
    out = batches_dir / f"{batch}.json"
    if out.exists():
        raise RuntimeError(f"refusing to rewrite sealed snapshot {out}")
    out.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    digest = _sha256(out)
    print(f"  batches/{batch}.json    sha {digest[:12]}  "
          f"predecessor={'null' if predecessor is None else predecessor['path']}")

    print(f"\n[5/6] claims.csv")
    pipeline.write_csv(root / "claims.csv", results)
    print(f"  rows              {len(results)}")

    print(f"\n[6/6] batch {batch} summary")
    by_status = defaultdict(int)
    for r in results:
        by_status[r.status] += 1
    for status in sorted(by_status):
        print(f"  {status:20} {by_status[status]}")
    print(f"  requests          {len(requests)} "
          f"({', '.join(sorted({q['status'] for q in requests}))})")
    print(f"  issues            {len(issues)}")
    print(f"  budget remaining  {budget['remaining_cents']} cents of "
          f"{budget['allocation_cents']} allocation")
    return {"path": f"batches/{batch}.json", "sha256": digest}, out


if __name__ == "__main__":
    raise SystemExit(main())
