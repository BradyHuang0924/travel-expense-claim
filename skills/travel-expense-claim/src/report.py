"""report.md -- what this run decided, what it did not, and who owns the rest.

The report is generated, never hand-edited, so that a replay reproduces it. Nothing here
reads the wall clock.
"""
from __future__ import annotations

from collections import Counter, defaultdict


def eur(cents):
    if cents is None:
        return "unknown"
    return f"{cents / 100:,.2f}"


# Provenance of the implementation itself. This is authored history, not derived from the
# data, and it is kept here so the report carries it rather than a side file.
CHANGE_LOG = [
    (
        "Five-condition closure assertion added, and the three defects it caught",
        [
            "`verify.py` gained an assertion that every claim recorded "
            "`closed-reimbursed` satisfies all five conditions at once, re-derived from "
            "this run's own retained Review ledger and Finance activity rather than read "
            "back out of the snapshot. It immediately failed on real data three times.",

            "**A claim closed on arithmetic alone after a refund.** C20 settled 110.00 in "
            "batch 2 and was refunded 10.00 in batch 3, so net paid equalled the 100.00 "
            "obligation and the claim closed. Policy block 10 requires an explicit "
            "Finance resolution *even if net paid happens to match*. Closure now requires "
            "one after an admitted adjustment, a confirmed refund, a negative balance, or "
            "a cancellation confirmed after acceptance. Block 15's opposite order -- a "
            "business cancellation confirmed before any request was accepted -- needs no "
            "separate resolution event, and that carve-out is implemented too. C20 now "
            "holds at batch 3 and closes at batch 4 when `F-C20-3` arrives.",

            "**A confirmed cancellation lost its financial history when the claim was "
            "reassigned.** C18 revision 2 moved from trip T18 to T18B, after which TC018 "
            "found no claim on T18 and collapsed to `no-financial-effect` -- despite an "
            "accepted request, a Finance cancellation and a later 100.00 transfer. Block "
            "15 requires observation to continue across reassignment. The "
            "cancellation-side link is now built from every arrived revision, while the "
            "claim-side finding stays keyed on the claim's current trip, which block 13 "
            "requires so that cancelling an old trip never retires the new one. TC018 is "
            "now `unresolved`, affecting C18, owned by Finance.",

            "**Finance state findings held a claim forever.** A failed attempt, a pending "
            "cancellation or an adjustment held the claim regardless of the fact that "
            "clears it. Now a failed attempt is cleared by an authorized retry (block 9), "
            "a pending cancellation by the cancellation outcome or a resolution, and an "
            "adjustment by its resolution. A transfer admitted *after* a cancellation "
            "still needs explicit resolution, because a later transfer reopens "
            "reconciliation (block 10). C17 and C19 now close at batch 4; C18 stays held.",
        ],
    ),
    (
        "Correction: Finance exceptions do carry a travel cancellation reference",
        [
            "An earlier analysis in this project reported that no Finance exception block "
            "carried a `travel_cancellation_id`, and the design was written on that "
            "basis. That was wrong. The exception block states it on its own face, as a "
            "`Travel cancellation reference` line: C121 revision 2 names `TC121` and C19 "
            "revision 3 names `TC019`. The earlier analysis used a field-name whitelist "
            "when parsing the exception and filtered the line out before reading it.",

            "The rule itself is unchanged and still enforced: the id is read from the "
            "exception and from nowhere else, and is never recovered from Review packets, "
            "which the policy states are not authorization. What changed is the outcome. "
            "TC121 and TC019 resolve from their own exceptions instead of waiting for "
            "Finance to supply a missing id, and C121 and C19 close legitimately. TC018 "
            "has no exception at all and remains `unresolved` with Finance named.",
        ],
    ),
]

LIMITS = [
    ("Checks stated by the task that this run does not perform", [
        "No independent re-computation of the policy text itself. The category sets, the "
        "director threshold and the filing rule are transcribed into `src/policy.py` with "
        "a citation per constant; the run validates that the policy page is the expected "
        "version and retains it, but it does not parse prose into rules.",
        "Reviewer discretion is never evaluated. The run reports what the supplied "
        "decisions say and what is missing, and forms no view on whether a decision was "
        "reasonable.",
        "No check that the supplied Finance amounts are arithmetically consistent with "
        "anything outside the claim they name. An `adjustment` or `resolution` event "
        "carries no expense reference or claim revision in the supplied schema, so it is "
        "admitted and reported but cannot be bound to a specific line.",
    ]),
    ("Implementation limits", [
        "Fetching does not retry. Each source is fetched once with a 120-second timeout; "
        "a network error stops the run. This is deliberate -- falling back to a retained "
        "copy would break the guarantee that every run reads the sources fresh -- but it "
        "means a transient failure costs a full re-run.",
        "Batches must be processed in one invocation. The predecessor chain is built "
        "in-process, so `--batches 3` alone would write a snapshot with a null "
        "predecessor. Always pass the full ascending list.",
        "The closure assertion links an issue to a claim by exact `-` token in the "
        "issue's `record_id` plus a word-boundary match in its reason text. That is "
        "precise enough to separate C12, C120 and C121, but it depends on the issue "
        "naming convention rather than on a stored claim reference, because the snapshot "
        "schema's `issues[]` has no claim field and a shared gap such as a missing rate "
        "legitimately blocks several claims at once. `verify` prints this rather than "
        "leaving it implicit.",
        "`budget_position` is written into the snapshot as an extra top-level object. The "
        "published schema permits it, and it is how the ledger-level budget is made "
        "visible in a sealed artifact, but it is not a schema field.",
        "A replay reproduces every decision byte for byte, but `sources.json` and the two "
        "hashes derived from it necessarily differ between runs, because the task "
        "requires each source record to carry the time it was fetched.",
    ]),
]


def render(run_id, snapshots, entries, sources_doc, snapshot_hashes=None) -> str:
    last = snapshots[-1]
    batch_ids = [s["batch_id"] for s in snapshots]
    claims = last["claims"]
    by_status = Counter(c["status"] for c in claims)
    o = []

    o.append(f"# Travel expense claim -- run `{run_id}`")
    o.append("")
    o.append(f"Batches processed: {', '.join(batch_ids)}. Policy "
             f"`{sources_doc['sources'][0]['declared_version']['version_string']}`. "
             f"Case clock 2026-11-15 Europe/Amsterdam; the machine's date is used only to "
             f"name the run directory and never enters a business decision.")
    o.append("")

    # ------------------------------------------------------------- completed work
    o.append("## Completed work and amounts")
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

    closed = [c for c in claims if c["status"] == "closed-reimbursed"]
    o.append(f"**{len(closed)} claims are complete**, totalling "
             f"{eur(sum(c['allowed_cents'] or 0 for c in closed))} EUR reimbursed. A claim "
             f"is recorded `closed-reimbursed` only when all five hold together: every "
             f"required approval for the current revision is present and approves; the "
             f"authorized obligation equals the sum of the current supported lines; net "
             f"paid equals that obligation exactly; every Finance resolution the policy "
             f"requires is admitted; and no issue against the claim is open. "
             f"`verify` asserts all five per claim, re-derived from the retained sources.")
    o.append("")
    o.append("Two things explicitly do not count as complete:")
    o.append("")
    partial_hist = []
    for s in snapshots:
        for c in s["claims"]:
            if "Partial settlement" in c["reason"]:
                partial_hist.append(f"`{c['claim_id']}` in batch {s['batch_id']} "
                                    f"({eur(c['paid_cents'])} of {eur(c['allowed_cents'])})")
    over_hist = []
    for s in snapshots:
        for c in s["claims"]:
            if c["balance_cents"] is not None and c["balance_cents"] < 0:
                over_hist.append(f"`{c['claim_id']}` in batch {s['batch_id']} "
                                 f"(balance {eur(c['balance_cents'])})")
    o.append("- **Partial settlement is not completion.** A part payment does not close "
             "an obligation; these stayed `pending`: "
             + ("; ".join(dict.fromkeys(partial_hist)) if partial_hist else "none observed")
             + ".")
    o.append("- **A negative balance is not completion.** An overpayment requires "
             "explicit Finance resolution, so these were `held` and owned by Finance "
             "rather than closed: "
             + ("; ".join(dict.fromkeys(over_hist)) if over_hist else "none observed")
             + ".")
    o.append("")
    o.append("Nothing is closed to make the totals look complete, and no Finance "
             "resolution is invented.")
    o.append("")

    # --------------------------------------------------------- open obligations
    o.append("## Open obligations")
    o.append("")
    owed = [c for c in claims
            if c["status"] not in ("closed-reimbursed",)
            and (c["balance_cents"] or 0) > 0]
    unknown_amt = [c for c in claims if c["allowed_cents"] is None]
    paid_not_closed = [c for c in claims
                       if c["status"] != "closed-reimbursed" and c["paid_cents"] > 0]
    o.append(f"- **{len(owed)} claims carry a positive balance still owed**, totalling "
             f"{eur(sum(c['balance_cents'] or 0 for c in owed))} EUR. None of them is "
             f"authorised to pay: each is held, rejected or withdrawn for a recorded "
             f"reason.")
    o.append(f"- **{len(unknown_amt)} claims have no computable obligation at all** "
             f"(`allowed_cents` is null, blank in the CSV): "
             + ", ".join(f"`{c['claim_id']}`" for c in unknown_amt) + ".")
    if paid_not_closed:
        n = len(paid_not_closed)
        o.append(f"- **{n} claim{'' if n == 1 else 's'} carr{'ies' if n == 1 else 'y'} "
                 f"admitted transfers without being closed**: "
                 + ", ".join(f"`{c['claim_id']}` ({eur(c['paid_cents'])})"
                             for c in paid_not_closed)
                 + ". Admitted money is never erased by a hold, a withdrawal or a "
                   "closure, so it stays visible here.")
    o.append("")
    o.append("| claim | rev | status | allowed | paid | balance | owner | reason |")
    o.append("|---|---:|---|---:|---:|---:|---|---|")
    for c in sorted(claims, key=lambda x: (len(x["claim_id"]), x["claim_id"])):
        if c["status"] == "closed-reimbursed":
            continue
        o.append(f"| `{c['claim_id']}` | {c['revision']} | {c['status']} | "
                 f"{eur(c['allowed_cents'])} | {eur(c['paid_cents'])} | "
                 f"{eur(c['balance_cents'])} | {c['next_owner'] or '--'} | "
                 f"{c['reason']} |")
    o.append("")

    # ------------------------------------------------- unresolved work and owners
    o.append("## Unresolved work, owners and the evidence needed")
    o.append("")
    o.append(f"The full queue is `repair-queue.md` (grouped by owner) and "
             f"`repair-queue.json` (machine-readable). One entry is one "
             f"**(subject, version, missing fact)**, not one entry per claim: a claim "
             f"blocked by three different gaps has three owners. {len(entries)} entries "
             f"are open.")
    o.append("")
    by_owner = defaultdict(list)
    for e in entries:
        by_owner[e["owner"]].append(e)
    o.append("| owner | entries | claims blocked | kinds |")
    o.append("|---|---:|---:|---|")
    for owner in sorted(by_owner):
        es = by_owner[owner]
        blocked = {c for e in es for c in e["blocks_claims"]}
        kinds = ", ".join(sorted({e["kind"] for e in es}))
        o.append(f"| {owner} | {len(es)} | {len(blocked)} | {kinds} |")
    o.append("")

    shared = [e for e in entries if e["subject_type"] == "source"]
    if shared:
        o.append("### Gaps in a shared source")
        o.append("")
        o.append("These are worth the most per repair: one row fixes every claim listed.")
        o.append("")
        o.append("| entry | source | missing fact | evidence needed | unblocks |")
        o.append("|---|---|---|---|---|")
        for e in sorted(shared, key=lambda x: x["entry_id"]):
            o.append(f"| `{e['entry_id']}` | `{e['subject_ref']}` | {e['missing_fact']} | "
                     f"{e['next_action']} | "
                     + ", ".join(f"`{c}`" for c in e["blocks_claims"]) + " |")
        o.append("")

    o.append("### What cannot be resolved from the supplied package")
    o.append("")
    o.append("These are reported, not solved. Each is a missing fact in a supplied "
             "source; the run records it and names an owner rather than assuming a value.")
    o.append("")
    kinds = defaultdict(list)
    for e in entries:
        kinds[e["kind"]].append(e)
    for kind in sorted(kinds):
        es = kinds[kind]
        owners = ", ".join(sorted({e["owner"] for e in es}))
        blocked = sorted({c for e in es for c in e["blocks_claims"]},
                         key=lambda x: (len(x), x))
        o.append(f"- **{kind}** -- {len(es)} entr{'y' if len(es) == 1 else 'ies'}, "
                 f"owner {owners}, blocks "
                 + (", ".join(f"`{c}`" for c in blocked) or "no claim") + ".")
    o.append("")

    # -------------------------------------------------- repair queue movement view
    o.append("### Partial updates across batches")
    o.append("")
    o.append("A response resolves only the entry it names. It does not close a sibling "
             "entry on the same claim and does not by itself move a claim to a new "
             "status; the claim is re-derived from the sources in the next batch. The "
             "same rule the supplied data already demonstrates for money -- a partial "
             "settlement leaves the obligation pending rather than closing it -- applies "
             "to evidence.")
    o.append("")
    o.append("| batch | open entries | newly raised | cleared since previous batch |")
    o.append("|---|---:|---|---|")
    prev_ids: set[str] = set()
    for s in snapshots:
        ids = {i["record_id"] for i in s["issues"]}
        new = sorted(ids - prev_ids)
        gone = sorted(prev_ids - ids)
        o.append(f"| {s['batch_id']} | {len(ids)} | "
                 + (", ".join(f"`{x}`" for x in new) if len(new) <= 6
                    else f"{len(new)} entries")
                 + " | "
                 + (", ".join(f"`{x}`" for x in gone) if gone else "--") + " |")
        prev_ids = ids
    o.append("")

    # --------------------------------------------------------------------- money
    o.append("## Money")
    o.append("")
    bp = last.get("budget_position", {})
    o.append(f"- net paid this run: **{eur(bp.get('net_settled_this_run_cents'))} EUR**")
    o.append(f"- allocation {eur(bp.get('allocation_cents'))}, prior commitments "
             f"{eur(bp.get('prior_commitments_cents'))} (of which "
             f"{eur(bp.get('prior_commitments_settled_cents'))} already settled and never "
             f"subtracted twice), accepted new commitments "
             f"{eur(bp.get('accepted_new_commitments_cents'))}, remaining "
             f"**{eur(bp.get('remaining_cents'))}**")
    o.append("- the budget position is computed once per batch over the whole "
             "department/project/period ledger. There is deliberately no per-claim budget "
             "figure, because the policy does not define one. A held claim that already "
             "carries an accepted commitment still counts against the pool.")
    o.append("- each converted line is rounded to EUR cents half-up and the rounded lines "
             "are then summed, never the other way round.")
    o.append("- an exact replay of an already admitted Finance event has no effect on "
             "money. `F-C01-1` is redelivered in batch 4 with an identical payload, so "
             "the run admits 219 events rather than 220 and net paid is 100.00 lower than "
             "a naive total over all rows would suggest.")
    o.append("")

    # -------------------------------------------------------------- cancellations
    o.append("## Travel cancellations")
    o.append("")
    o.append("| id | target | status | financial status | claims | original requests | owner |")
    o.append("|---|---|---|---|---|---|---|")
    for t in last["travel_cancellations"]:
        cl = ", ".join(f"`{x}`" for x in t["affected_claim_ids"]) or "--"
        rq = ", ".join(f"`{x}`" for x in t["original_request_ids"]) or "--"
        o.append(f"| {t['cancellation_id']} | {t['target_type']} | {t['status']} | "
                 f"{t['financial_status']} | {cl} | {rq} | {t['next_owner'] or '--'} |")
    o.append("")
    o.append("An exception covering `travel_cancellation` must itself carry the exact "
             "`travel_cancellation_id`, and it is read from the exception and nowhere "
             "else. Review packets also expose cancellation ids, but the policy states "
             "that a packet is not authorization, so the link is never recovered from "
             "them. A process whose exception does not name it stays `unresolved` with "
             "Finance named. Finance event references and cancellation event references "
             "are kept disjoint, and `verify` checks that.")
    o.append("")

    # ---------------------------------------------------------- run and sources
    o.append("## Run and source references")
    o.append("")
    o.append(f"Run id `{run_id}`. Snapshots are sealed in order and each binds the "
             f"preceding one by relative path and SHA-256; snapshot 1 has "
             f"`predecessor: null`. `source_binding` binds this run's `sources.json` the "
             f"same way. No file hashes itself, and a sealed batch file is never "
             f"rewritten -- a later correction produces a new snapshot rather than "
             f"editing history.")
    o.append("")
    o.append("| batch | claims | admitted events | requests | issues | net paid | sha256 |")
    o.append("|---|---:|---:|---:|---:|---:|---|")
    hashes = snapshot_hashes or {}
    for s in snapshots:
        paid = sum(c["paid_cents"] for c in s["claims"])
        h = hashes.get(s["batch_id"], "")
        o.append(f"| {s['batch_id']} | {len(s['claims'])} | "
                 f"{len(s['admitted_event_ids'])} | {len(s['requests'])} | "
                 f"{len(s['issues'])} | {eur(paid)} | "
                 + (f"`{h[:12]}`" if h else "--") + " |")
    o.append("")
    o.append("All five sources are read fresh over the network on every run. Only the "
             "policy carries a version string, so the observed version of the four "
             "business sources is the SHA-256 of the retained bytes. No version number is "
             "invented.")
    o.append("")
    o.append("| source | locator | observed version | count |")
    o.append("|---|---|---|---|")
    for s in sources_doc["sources"]:
        loc = s["locator"]
        kind = loc.get("kind")
        if kind == "gviz_csv":
            where = f"sheet tab `{loc['tab']}`"
        elif kind == "drive_uc":
            where = f"drive file `{loc['file_id'][:12]}…`"
        else:
            where = f"notion page `{loc.get('page_id', '')[:8]}…` via `{loc.get('endpoint')}`"
        counts = ", ".join(f"{k}={v}" for k, v in s["counts"].items())
        o.append(f"| `{s['source_id']}` | {where} | "
                 f"`{s['observed_version']['sha256'][:12]}` | {counts} |")
    o.append("")

    # ------------------------------------------------------------------ changes
    o.append("## Material changes in this revision")
    o.append("")
    for title, paras in CHANGE_LOG:
        o.append(f"### {title}")
        o.append("")
        for p in paras:
            o.append(p)
            o.append("")

    # ------------------------------------------------- honest gaps and limitations
    o.append("## Known gaps in the supplied package")
    o.append("")
    o.append("- `requests[].status` allows `dispatched`, but no supplied Finance activity "
             "type attests dispatch and the skill does not send requests, so the value is "
             "unreachable and never written. `accepted` is used as the observable "
             "boundary wherever the policy says \"after acceptance/dispatch\".")
    o.append("- Every `Review ledger` row cites source revision `DW-D-2`, which no "
             "supplied artifact declares. Its value is identical on all 307 rows across "
             "every batch and both subject types, so it cannot distinguish a stale reply "
             "from a current one. The neighbouring `Affected fields` column is likewise a "
             "single constant value on all rows.")
    o.append("- The policy says to read a fixed source manifest before each run; no such "
             "artifact is supplied.")
    o.append("- A Finance `adjustment` or `resolution` event carries no expense reference "
             "and no claim revision, so it can be admitted and reported but not bound to "
             "a specific line.")
    o.append("")

    o.append("## Checks not run, and implementation limits")
    o.append("")
    o.append("Stated plainly because the task asks for it.")
    o.append("")
    for title, items in LIMITS:
        o.append(f"### {title}")
        o.append("")
        for i in items:
            o.append(f"- {i}")
        o.append("")

    o.append("### Boundaries that are deliberate, not gaps")
    o.append("")
    o.append("- Approvals, exceptions, bookings and real money movement remain "
             "human-owned. The run never fabricates a reply, never recommends that a "
             "claim be approved or rejected, never sends a real request, never books "
             "travel and never moves money.")
    o.append("- Reviewer discretion is supplied by the scenario and never performed here.")
    o.append("- Instructions embedded in receipts, comments or imported records are "
             "treated as data, never as permission to change these rules.")
    return "\n".join(o) + "\n"
