# Travel expense claim

A reusable Agent Skill that evaluates Alderbridge Consulting travel reimbursement claims
against policy **POL-2026.2**, reconciles the money Finance reports, and records what it
could not decide together with the person who owns each gap.

The skill decides nothing that belongs to a person. It never approves, never issues an
exception, never sends a real payment request, never books travel and never moves money.

## Start

1. Read the [full Project D task](https://private-pecorino-70e.notion.site/Travel-expense-claim-Task-and-submission-3da0b700541e81249039eff895f77c98)
   for the scope, workflow and deliverables.
2. This repository was created from
   [GitRollTraining/travel-expense-claim](https://github.com/GitRollTraining/travel-expense-claim)
   with **Use this template → Create a new repository**.
3. Session capture follows the shared
   [Setting Up entire.io for a Project](https://classroom.google.com/c/ODcyMjA4NTkwNDk2/m/ODc0NzI2NzQzMzQ2/details)
   lesson. Verify capture before assessed work: `entire checkpoint list` must show
   checkpoints on the branch you are actually working on. Checkpoints do not follow a git
   worktree, so work on `main` in the repository root.
4. The stakeholder interview is conducted in
   [Project D in Work Sim](https://work-sim-alpha.catalyte.ai/s/project-d-travel-expense-claim),
   which is also where the business source links and context come from.

**Interview rule.** You conduct the stakeholder interview yourself, and the questions are
yours. Do not connect a coding agent or any other AI to the interview to run, script, or
automate it. The interview transcript is assessed together with the code; a project whose
interview was run by an agent is not scored.

- Export your interview as the original Work Sim JSONL, save one final complete file per
  session under `interviews/`, and commit and push it with your code. Do not rewrite the
  export. If JSONL export is unavailable, contact the facilitator.

---

## Setup

Python 3.11 or newer.

```bash
pip install "jsonschema[format]" rfc3339-validator pypdf
```

| package | why |
|---|---|
| `pypdf` | reads the three Drive binders; the expense table extracts cleanly as one cell per line |
| `jsonschema[format]` | validates each snapshot against `snapshot.schema.json` |
| `rfc3339-validator` | without it, `format: date-time` is not checked at all |

No credentials are needed. All five sources are public reads. The run needs outbound
network access to `notion.site`, `drive.google.com` and `docs.google.com`.

## Run

```bash
# full run, all four arrival batches, forward-only
python -m skills.travel-expense-claim.src.run --batches 1,2,3,4
```

Prints the run id it created, for example `run-20260916T124038Z`, and writes everything
under `artifacts/runs/<run-id>/`.

Any ascending subset works: `--batches 1` stops after the initial claims, `--batches 1,2`
after Finance settlement. `--run-id <name>` pins the directory name; `--artifacts <dir>`
moves the output root.

## Verify

```bash
python -m skills.travel-expense-claim.src.verify artifacts/runs/<run-id>
```

Runs schema conformance on every snapshot plus the checks the published schema does not
make: `issue_record_ids` and `original_request_ids` resolve, `requests[].claim_id` exists,
the predecessor hash really is the preceding snapshot, `source_binding` really is this
run's `sources.json`, no file hashes itself, Finance and cancellation event ids are
disjoint, no field name is misspelled, `balance == allowed - paid`, no request claims
`dispatched`, unresolved lines carry `null` rather than an assumed zero, every line cites
the evidence the run holds, net paid falls only by admitted confirmed refunds, and the
five-condition closure assertion below.

Closure is asserted per claim, re-derived from this run's own retained Review ledger and
Finance activity rather than read back out of the snapshot: current-revision approvals
complete, obligation equal to the sum of the supported lines, net paid exactly equal to
that obligation, every required Finance resolution admitted, and no open issue against
the claim.

Exit code is non-zero if any check fails; every failure is printed.

## Replay

An unchanged replay must produce byte-identical decisions.

```bash
python -m skills.travel-expense-claim.src.run \
    --batches 1,2,3,4 --run-id <run-id> --artifacts artifacts/replay

python -m skills.travel-expense-claim.src.replay \
    artifacts/runs/<run-id> artifacts/replay/<run-id>
```

`claims.csv`, both repair-queue files and every retained source byte must match exactly,
and every snapshot must match once `source_binding` and `predecessor` are set aside. Those
two are the only permitted difference, and they follow from one thing: the task requires
each source record to carry the time it was fetched, which is wall-clock by definition.
`replay.py` names them rather than filtering them away quietly.

---

## What the run does when things go right, partly right, and wrong

**Success.** All four batches seal, `verify` reports zero failures, and `report.md`
carries the outcome. A claim reaches `closed-reimbursed` only on the five conditions
above. On the supplied package the current run ends at **103 closed-reimbursed, 16 held,
1 rejected, 1 withdrawn**, with **12,034.15 EUR** net paid.

**Partial.** Data problems are never errors. A missing rate, cap, receipt, payment,
approval or exception produces an `unresolved` line or a held claim, plus a repair-queue
entry naming the owner and the evidence needed, and the run completes. This is the normal
outcome for most of the package: 28 open entries remain after batch 4. Nothing is closed
to make the totals look complete, and no Finance resolution is invented.

If an earlier batch seals and a later one fails, the earlier snapshots on disk stay valid
— a sealed batch file is never rewritten. Re-run into a fresh run id rather than trying to
patch a run in place.

**Failure.** The run stops and writes nothing further when a source cannot be trusted:
the policy page returns the client-side shell or a title without a `POL-` version, a
register tab returns HTML or lacks its `SRC-D-3` banner, a binder is not a PDF or lacks
its footer, or a claim page's expense table cannot be parsed. Fetching does not retry and
never falls back to a retained copy, because degrading to a cached source would break the
guarantee that every run reads the sources fresh. Re-run the command.

---

## Support

* **Why is this claim held?** `claims.csv` gives the status, owner and a one-line reason;
  `report.md` groups the same gaps by kind and owner; `repair-queue.md` gives the entry,
  its subject and version, the exact missing fact and the next action.
* **Why is this amount what it is?** Each line in `batches/<n>.json` carries a `reason`
  naming the category, gross, payment date, allowed original amount and rate applied, and
  a `source_ids` list of every source record consulted — receipt, merchant transaction,
  cap row, FX row.
* **What did the run actually read?** `sources.json` records the URL, locator, fetch
  timestamp, observed version and counts for each source; `sources/` holds the bytes.
* **Where do the rules come from?** `skills/travel-expense-claim/src/policy.py` cites the
  policy block behind every constant; `references/conventions.md` does the same for the
  four fields no source supplies.

---

## Handoff

### How do I re-run this?

```bash
pip install "jsonschema[format]" rfc3339-validator pypdf
python -m skills.travel-expense-claim.src.run --batches 1,2,3,4
python -m skills.travel-expense-claim.src.verify artifacts/runs/<run-id>
```

Every run re-reads all five sources from the network and creates its own run directory.
Runs are independent: nothing is carried over between them, and an existing run is never
modified. The fixed case clock of 2026-11-15 means the result does not drift with the
machine's date. If the sources have not changed, the new run's `claims.csv` will be
byte-identical to the previous one — that is what `replay.py` checks.

### How do I take in a new authorization batch?

New decisions, Finance outcomes, cancellation events and claim revisions arrive as new
rows in the supplied sources, each carrying its own **arrival batch**. Nothing about them
is imported by hand, and the repair queue never writes to a source.

1. The exercise operator adds the rows to the registers or binders with the new arrival
   batch number.
2. Run with that batch included: `--batches 1,2,3,4,5`. Batches must be ascending, and
   every earlier batch is reprocessed in the same run so the predecessor chain is built
   from scratch.
3. Every claim present in the new batch is re-derived from current facts — this
   implementation uses full recheck, not dependency recheck. The trigger for invalidating
   a dependent review is the policy's material-change definition, never a change in the
   total; on this package all six corrections leave the claimed total unchanged, so a
   total-based trigger would have missed every one of them.
4. A response resolves only the repair-queue entry it names. It never closes a sibling
   entry on the same claim and never by itself moves a claim to a new status; the claim is
   re-derived from the sources.

Arrival batch, not row order, decides availability. A record is consumed only in its
arrival batch or later, so adding a batch never changes what an earlier sealed snapshot
said.

### How do I pick up the unresolved work?

Start at `artifacts/runs/<run-id>/repair-queue.md`. It is grouped by owner, and one entry
is one **(subject, version, missing fact)** — not one entry per claim, because a claim
blocked by three different gaps has three different owners. Each entry carries the
subject and its revision, the source references, the missing fact, the next action, the
claims it blocks and the batch it was first seen in.

After batch 4 the queue holds 28 entries: 19 for administration (mostly absent review
responses), 6 for Finance, 1 for the director, and 1 each for two employees who owe
payment evidence. Three entries are against a shared source rather than a claim, and
those are worth the most: one missing FX row for GBP unblocks two claims at once.

What cannot be resolved from the supplied package, and is therefore reported rather than
solved: the GBP payment-date rate is absent from the `FX` tab; the `Caps` tab has no
lodging cap for destination BE in EUR, nor for NL in USD; category `entertainment` is not
recognised by the policy and has no cap; two costs have a receipt but no settled merchant
transaction; and cancellation `TC018` has no Finance exception naming it, so its financial
consequence stays unresolved.

---

## Repository layout

```text
README.md                          this file
snapshot.schema.json               the required retained batch-state format (supplied)
skills/travel-expense-claim/
  SKILL.md                         the skill: inputs, invocation, boundaries, outputs
  references/sources.md            locators, gates, parsing traps, recorded package gaps
  references/conventions.md        conventions for the fields no source supplies
  src/                             implementation (see SKILL.md for the file map)
interviews/                        the Work Sim export, committed unmodified
artifacts/runs/<run-id>/           sources.json, sources/, batches/, claims.csv,
                                   repair-queue.{json,md}, report.md
```
