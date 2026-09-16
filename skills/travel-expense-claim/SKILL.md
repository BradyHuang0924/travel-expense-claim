---
name: travel-expense-claim
description: >-
  Evaluate Alderbridge Consulting travel reimbursement claims against POL-2026.2.
  Reads five live business sources fresh, normalises them, evaluates each claim line
  for entitlement, and emits a sealed per-batch snapshot, claims.csv and sources.json.
  Use when asked to run, re-run or verify the Alderbridge travel expense claim workflow.
---

# Travel expense claim

Reusable evaluation of Alderbridge travel reimbursement claims. The skill reads the
business sources, decides what is supported, excluded or unresolved, and records what it
could not decide. It never approves, never issues an exception, never sends a payment
request and never moves money.

## Scope of this revision

Batches 1 and 2, end to end. Batches 3 and 4 reuse the same per-batch path; they are not
yet wired up.

## Run it

```
pip install "jsonschema[format]" rfc3339-validator pypdf
python -m skills.travel-expense-claim.src.run --batches 1,2
python -m skills.travel-expense-claim.src.verify artifacts/runs/<run-id>
```

Outputs land in `artifacts/runs/<run-id>/`: `sources.json`, `sources/` (the retained
bytes), `batches/1.json`, `claims.csv`.

## The two standing constraints

**Continue independent claims.** A claim that cannot be decided is held on its own
findings; it does not hold the rest of the batch. Three boundaries ride with it:

* A held claim that already carries an accepted commitment still counts against the
  shared budget pool. The budget is computed once per batch over the whole
  department/project/period ledger (`evaluate.budget_position`); there is deliberately no
  per-claim budget figure, because the policy does not define one.
* A cost already settled under an earlier obligation is linked and excluded from the
  later claim, which shows only the remaining entitlement
  (`pipeline.prior_settled_links`). Derived from cost_id overlap, never from a list of
  identifiers.
* Admitted transfers are never erased by a hold, a withdrawal or a closure
  (`finance.ClaimMoney.net_paid_cents`).

**Full recheck.** Every claim present in a batch is re-derived from current facts. The
trigger for invalidating dependent review is the policy's material-change definition, not
a change in the total: employee, trip (including trip revision and trip dates), the line
set, line money and first-submitted dates, the exception and its covered issues, the
submission date, and authority. Recomputation is forward-only: `run` refuses to write a
batch file that already exists, and each snapshot binds its predecessor by path and
SHA-256, so a rewritten history breaks the chain visibly.

## What the skill will not do

* It will not recover a missing authorisation link from another source. A Finance
  exception covering `travel_cancellation` must itself carry the exact
  `travel_cancellation_id`; the id is not taken from Review packets or anywhere else, and
  the finding stays unresolved with an issue naming Finance
  (POL-2026.2 block 14, and block 2: "neither the employee nor automation invents one").
* It will not write `requests[].status = "dispatched"`. No supplied Finance activity type
  denotes dispatch, and the skill does not send requests, so the state has no admissible
  source. `verify` asserts the value never appears.
* It will not assume a zero. An unknown category, missing evidence, missing rate or
  missing applicable cap yields `unresolved` with `allowed_cents: null`.
* It will not treat a claim as authorised because Finance acted on it. Approvals are
  asserted independently in `pipeline.build_request`; if Finance has accepted a request
  whose claim is missing a required approval, the row is kept so the commitment stays in
  the ledger, but it is recorded as `held` with an issue rather than passing silently.
* It will not name a request that was never proposed. `original_request_ids` is filtered
  to requests that actually exist in the same snapshot, and `verify` checks it.
* It will not drop evidence it holds. A line records every source record the run looked
  up for it, including when the decision short-circuits earlier.

## Layout

```
src/policy.py         constants read off POL-2026.2, each citing its block
src/sources.py        fresh read, validation gates, retention, sources.json
src/normalise.py      per-tab header detection, multi-value cells, PDF parsing
src/evaluate.py       line evaluation, filing deadline, ledger-level budget position
src/finance.py        event admission, replay handling, net paid
src/cancellations.py  cancellation processes and their financial consequence
src/pipeline.py       per-batch claim assembly, snapshot, claims.csv
src/run.py            orchestrator
src/verify.py         schema conformance plus the checks the schema does not make
references/           source locators, conventions, the recorded package defects
```

## Case clock

All business dates are compared against the fixed case clock **2026-11-15
Europe/Amsterdam**. The machine's date is used only to name the run directory.
