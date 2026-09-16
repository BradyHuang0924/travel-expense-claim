"""The repair queue.

Constraint 4 fixes the unit of work: one entry is one (subject, subject version, missing
fact). It is not one entry per claim. The 21 held claims after batch 2 decompose into
gaps of different kinds with different owners -- a missing review response belongs to
administration, a missing rate or cap to Finance, a missing settled merchant transaction
to the employee who paid, an undecided cancellation to the directory supervisor -- and
flattening them to one row per claim would hide both the gap and its owner.

Every entry carries subject, version, source references, the missing fact or return
reason, the owner and the next action.

Partial response rule: a response resolves only the entry it names. It never closes a
sibling entry on the same claim and never upgrades a claim's status. The same rule the
supplied data already demonstrates for money -- a partial settlement leaves the
obligation pending rather than closing it -- applies to evidence.

The queue never writes to a source. Later batches are fixed inputs supplied by the
exercise, not consequences of anything drafted here.
"""
from __future__ import annotations

from collections import defaultdict


def build(issues, claims_by_id: dict, batch_id: str) -> list[dict]:
    """One entry per (subject_type, subject_ref, subject_revision, kind/record)."""
    entries = []
    for iss in issues:
        blocked = sorted({c for c in iss.blocks if c})
        entries.append({
            "entry_id": iss.record_id,
            "subject_type": iss.subject_type,
            "subject_ref": iss.subject_ref,
            "subject_revision": iss.subject_revision,
            "kind": iss.kind or "unclassified",
            "missing_fact": iss.reason,
            "owner": iss.owner,
            "next_action": iss.resolution_needed,
            "source_refs": sorted(set(iss.source_refs)),
            "blocks_claims": blocked,
            "first_seen_batch": batch_id,
        })
    entries.sort(key=lambda e: (e["owner"], e["subject_type"], e["subject_ref"],
                                e["entry_id"]))
    return entries


def carry_forward(previous: list[dict], current: list[dict]) -> list[dict]:
    """Keep the batch in which an entry was first raised, so a long-standing gap is not
    made to look new every batch. Resolved entries simply drop out of `current`."""
    first = {e["entry_id"]: e["first_seen_batch"] for e in previous}
    for e in current:
        if e["entry_id"] in first:
            e["first_seen_batch"] = first[e["entry_id"]]
    return current


def render(entries: list[dict], claims_by_id: dict, batch_id: str) -> str:
    out = [f"# Repair queue -- state after batch {batch_id}", ""]
    out.append(f"{len(entries)} open entries. One entry is one (subject, version, "
               f"missing fact); a claim blocked by three different gaps appears three "
               f"times, once per owner and per fact.")
    out.append("")
    out.append("A response resolves only the entry it names. It does not close a sibling "
               "entry on the same claim and does not by itself move a claim to a new "
               "status; the claim is re-derived from the sources in the next batch.")
    out.append("")

    by_owner = defaultdict(list)
    for e in entries:
        by_owner[e["owner"]].append(e)

    out.append("## By owner")
    out.append("")
    out.append("| owner | entries | claims blocked |")
    out.append("|---|---:|---:|")
    for owner in sorted(by_owner):
        blocked = {c for e in by_owner[owner] for c in e["blocks_claims"]}
        out.append(f"| {owner} | {len(by_owner[owner])} | {len(blocked)} |")
    out.append("")

    for owner in sorted(by_owner):
        out.append(f"## {owner}")
        out.append("")
        for e in by_owner[owner]:
            rev = "" if e["subject_revision"] is None else f" rev {e['subject_revision']}"
            out.append(f"### `{e['entry_id']}`")
            out.append("")
            out.append(f"- **subject**: {e['subject_type']} `{e['subject_ref']}`{rev}")
            out.append(f"- **kind**: {e['kind']}")
            out.append(f"- **missing fact**: {e['missing_fact']}")
            out.append(f"- **next action**: {e['next_action']}")
            srcs = ", ".join(f"`{s}`" for s in e["source_refs"]) or "--"
            out.append(f"- **source references**: {srcs}")
            blocks = ", ".join(f"`{c}`" for c in e["blocks_claims"]) or "--"
            out.append(f"- **blocks claims**: {blocks}")
            out.append(f"- **first seen**: batch {e['first_seen_batch']}")
            out.append("")
    return "\n".join(out) + "\n"
