"""report.md -- what this run decided, what it did not, and who owns the rest."""
from __future__ import annotations

from collections import Counter, defaultdict


def eur(cents):
    if cents is None:
        return "unknown"
    return f"{cents / 100:,.2f}"


def render(run_id, snapshots, entries, sources_doc, replay_note=None) -> str:
    last = snapshots[-1]
    batch_ids = [s["batch_id"] for s in snapshots]
    claims = last["claims"]
    by_status = Counter(c["status"] for c in claims)
    o = []

    o.append(f"# Travel expense claim run `{run_id}`")
    o.append("")
    o.append(f"Batches processed: {', '.join(batch_ids)}. "
             f"Case clock 2026-11-15 Europe/Amsterdam; the machine's date is used only "
             f"to name the run directory.")
    o.append("")

    o.append("## Outcome")
    o.append("")
    o.append("| status | claims | allowed | net paid |")
    o.append("|---|---:|---:|---:|")
    for status in sorted(by_status):
        rows = [c for c in claims if c["status"] == status]
        allowed = sum(c["allowed_cents"] or 0 for c in rows)
        unknown = sum(1 for c in rows if c["allowed_cents"] is None)
        paid = sum(c["paid_cents"] for c in rows)
        a = eur(allowed) + (f" (+{unknown} unknown)" if unknown else "")
        o.append(f"| {status} | {len(rows)} | {a} | {eur(paid)} |")
    o.append(f"| **total** | **{len(claims)}** | | "
             f"**{eur(sum(c['paid_cents'] for c in claims))}** |")
    o.append("")

    o.append("### Financial completion")
    o.append("")
    o.append("A claim is recorded `closed-reimbursed` only when all five hold together: "
             "every required approval for the current revision is present and approves; "
             "the authorized obligation equals the sum of the current supported lines; "
             "net paid equals that obligation exactly; every Finance resolution the "
             "policy requires is admitted; and no issue against the claim is open.")
    o.append("")
    o.append("Two things explicitly do not count as complete:")
    o.append("")
    partial = [c for c in claims if "Partial settlement" in c["reason"]]
    over = [c for c in claims if c["balance_cents"] is not None
            and c["balance_cents"] < 0]
    o.append(f"- **Partial settlement is not completion.** "
             + (", ".join(f"`{c['claim_id']}` ({eur(c['paid_cents'])} of "
                          f"{eur(c['allowed_cents'])})" for c in partial)
                or "none in this run")
             + " stay `pending`; the obligation is not closed by a part payment.")
    o.append(f"- **A negative balance is not completion.** "
             + (", ".join(f"`{c['claim_id']}` (balance {eur(c['balance_cents'])})"
                          for c in over)
                or "none in this run")
             + " is an overpayment requiring explicit Finance resolution, so it is "
               "`held` and owned by Finance, not closed.")
    o.append("")
    o.append("Nothing is closed to make the totals look complete, and no Finance "
             "resolution is invented.")
    o.append("")

    o.append("## What this run could not resolve")
    o.append("")
    o.append("These are reported, not solved. Each is a missing fact in a supplied "
             "source; the skill records it and names an owner rather than assuming a "
             "value.")
    o.append("")
    kinds = defaultdict(list)
    for e in entries:
        kinds[e["kind"]].append(e)
    o.append("| kind | entries | owner(s) | claims blocked |")
    o.append("|---|---:|---|---:|")
    for kind in sorted(kinds):
        es = kinds[kind]
        owners = ", ".join(sorted({e["owner"] for e in es}))
        blocked = {c for e in es for c in e["blocks_claims"]}
        o.append(f"| {kind} | {len(es)} | {owners} | {len(blocked)} |")
    o.append("")

    o.append("## Money")
    o.append("")
    bp = last.get("budget_position", {})
    o.append(f"- net paid this run: **{eur(bp.get('net_settled_this_run_cents'))} EUR**")
    o.append(f"- allocation {eur(bp.get('allocation_cents'))}, prior commitments "
             f"{eur(bp.get('prior_commitments_cents'))} (of which "
             f"{eur(bp.get('prior_commitments_settled_cents'))} already settled and not "
             f"subtracted twice), accepted new commitments "
             f"{eur(bp.get('accepted_new_commitments_cents'))}, remaining "
             f"**{eur(bp.get('remaining_cents'))}**")
    o.append("- the budget position is computed once per batch over the whole "
             "department/project/period ledger. There is no per-claim budget figure, "
             "because the policy does not define one. A held claim that already carries "
             "an accepted commitment still counts against the pool.")
    o.append("- admitted transfers are never reduced by a hold, a withdrawal or a "
             "closure.")
    o.append("")

    o.append("## Travel cancellations")
    o.append("")
    o.append("| id | target | status | financial status | claims | owner |")
    o.append("|---|---|---|---|---|---|")
    for t in last["travel_cancellations"]:
        cl = ", ".join(t["affected_claim_ids"]) or "--"
        o.append(f"| {t['cancellation_id']} | {t['target_type']} | {t['status']} | "
                 f"{t['financial_status']} | {cl} | {t['next_owner'] or '--'} |")
    o.append("")
    o.append("An exception covering `travel_cancellation` must itself carry the exact "
             "`travel_cancellation_id`, and it is read from the exception and nowhere "
             "else. Review packets also expose cancellation ids, but the policy states "
             "that a packet is not authorization, so the link is never recovered from "
             "them. A process whose exception does not name it stays `unresolved` with "
             "Finance named.")
    o.append("")

    o.append("## Per batch")
    o.append("")
    o.append("| batch | claims | admitted events | requests | issues | net paid |")
    o.append("|---|---:|---:|---:|---:|---:|")
    for s in snapshots:
        paid = sum(c["paid_cents"] for c in s["claims"])
        o.append(f"| {s['batch_id']} | {len(s['claims'])} | "
                 f"{len(s['admitted_event_ids'])} | {len(s['requests'])} | "
                 f"{len(s['issues'])} | {eur(paid)} |")
    o.append("")
    o.append("Each snapshot binds its predecessor by relative path and SHA-256, and "
             "binds this run's `sources.json` by path and SHA-256. A sealed batch file "
             "is never rewritten: a later correction produces a new snapshot rather than "
             "editing history. No file hashes itself.")
    o.append("")

    if replay_note:
        o.append("## Replay")
        o.append("")
        o.append(replay_note)
        o.append("")

    o.append("## Sources")
    o.append("")
    o.append("All five are read fresh over the network on every run; nothing is served "
             "from a cache. Only the policy carries a version string, so the observed "
             "version of the four business sources is the SHA-256 of the retained bytes. "
             "No version number is invented.")
    o.append("")
    o.append("| source | locator | observed version | count |")
    o.append("|---|---|---|---|")
    for s in sources_doc["sources"]:
        loc = s["locator"]
        kind = loc.get("kind")
        if kind == "gviz_csv":
            where = f"tab `{loc['tab']}`"
        elif kind == "drive_uc":
            where = f"drive `{loc['file_id'][:10]}…`"
        else:
            where = f"notion `{loc.get('page_id', '')[:8]}…`"
        counts = ", ".join(f"{k}={v}" for k, v in s["counts"].items())
        o.append(f"| `{s['source_id']}` | {where} | "
                 f"`{s['observed_version']['sha256'][:12]}` | {counts} |")
    o.append("")

    o.append("## Known gaps in the supplied package")
    o.append("")
    o.append("- A cancellation whose exception does not name its "
             "`travel_cancellation_id` cannot be resolved from the supplied package; the "
             "id is never recovered from review packets, which the policy says are not "
             "authorization.")
    o.append("- `requests[].status` allows `dispatched`, but no supplied Finance "
             "activity type attests dispatch and the skill does not send requests, so "
             "the value is unreachable and never written.")
    o.append("- Every `Review ledger` row cites source revision `DW-D-2`, which no "
             "supplied artifact declares. Its value is identical on all rows across all "
             "batches, so it cannot distinguish a stale reply from a current one.")
    o.append("- The policy says to read a fixed source manifest before each run; no such "
             "artifact is supplied.")
    o.append("")

    o.append("## Not done in this revision")
    o.append("")
    o.append("- Reviewer discretion is supplied by the scenario and never performed here.")
    o.append("- Approvals, exceptions, bookings and money movement remain human-owned.")
    o.append("- Instructions embedded in receipts, comments or imported records are "
             "treated as data, never as permission to change these rules.")
    return "\n".join(o) + "\n"
