# Travel expense claim -- run `run-A`

Batches processed: 1, 2, 3, 4. Policy `POL-2026.2`. Case clock 2026-11-15 Europe/Amsterdam; the machine's date is used only to name the run directory and never enters a business decision.

## Completed work and amounts

| status | claims | allowed | net paid |
|---|---:|---:|---:|
| closed-reimbursed | 103 | 11,934.15 | 11,934.15 |
| held | 16 | 1,520.01 (+6 unknown) | 100.00 |
| rejected | 1 | 40.00 | 0.00 |
| withdrawn | 1 | 50.00 | 0.00 |
| **total** | **121** | | **12,034.15** |

**103 claims are complete**, totalling 11,934.15 EUR reimbursed. A claim is recorded `closed-reimbursed` only when all five hold together: every required approval for the current revision is present and approves; the authorized obligation equals the sum of the current supported lines; net paid equals that obligation exactly; every Finance resolution the policy requires is admitted; and no issue against the claim is open. `verify` asserts all five per claim, re-derived from the retained sources.

Two things explicitly do not count as complete:

- **Partial settlement is not completion.** A part payment does not close an obligation; these stayed `pending`: `C16` in batch 2 (40.00 of 100.00); `C120` in batch 2 (30.00 of 75.00).
- **A negative balance is not completion.** An overpayment requires explicit Finance resolution, so these were `held` and owned by Finance rather than closed: `C20` in batch 2 (balance -10.00); `C19` in batch 3 (balance -20.00).

Nothing is closed to make the totals look complete, and no Finance resolution is invented.

## Open obligations

- **9 claims carry a positive balance still owed**, totalling 1,510.01 EUR. None of them is authorised to pay: each is held, rejected or withdrawn for a recorded reason.
- **6 claims have no computable obligation at all** (`allowed_cents` is null, blank in the CSV): `C08`, `C22`, `C23`, `C114`, `C116`, `C117`.
- **1 claim carries admitted transfers without being closed**: `C18` (100.00). Admitted money is never erased by a hold, a withdrawal or a closure, so it stays visible here.

| claim | rev | status | allowed | paid | balance | owner | reason |
|---|---:|---|---:|---:|---:|---|---|
| `C08` | 1 | held | unknown | 0.00 | unknown | EMP-01 | Held on: review_missing, unresolved_line. |
| `C10` | 1 | held | 90.00 | 0.00 | 90.00 | ADMIN-01 | Held on: review_missing. |
| `C13` | 1 | withdrawn | 50.00 | 0.00 | 50.00 | -- | Clean withdrawal by the employee; closed with an explicit non-payment reason. |
| `C14` | 1 | rejected | 40.00 | 0.00 | 40.00 | -- | Rejected by budget_owner; closed with an explicit non-payment reason. |
| `C15` | 1 | held | 0.00 | 0.00 | 0.00 | ADMIN-01 | Held on: review_missing. |
| `C18` | 2 | held | 100.00 | 100.00 | 0.00 | ADMIN-01 | Held on: review_missing, transfer_after_cancellation. |
| `C21` | 1 | held | 80.00 | 0.00 | 80.00 | ADMIN-01 | Held on: review_return. |
| `C22` | 1 | held | unknown | 0.00 | unknown | FIN-01 | Held on: review_missing, unresolved_line. |
| `C23` | 1 | held | unknown | 0.00 | unknown | FIN-01 | Held on: review_missing, unresolved_line. |
| `C25` | 1 | held | 100.00 | 0.00 | 100.00 | ADMIN-01 | Held on: permit_unapproved, review_missing. |
| `C26` | 1 | held | 100.00 | 0.00 | 100.00 | ADMIN-01 | Held on: review_missing. |
| `C112` | 1 | held | 25.00 | 0.00 | 25.00 | FIN-01 | Held on: late_filing, review_missing. |
| `C113` | 1 | held | 25.00 | 0.00 | 25.00 | ADMIN-01 | Held on: review_missing. |
| `C114` | 1 | held | unknown | 0.00 | unknown | EMP-03 | Held on: review_missing, unresolved_line. |
| `C116` | 1 | held | unknown | 0.00 | unknown | FIN-01 | Held on: review_missing, unresolved_line. |
| `C117` | 1 | held | unknown | 0.00 | unknown | ADMIN-01 | Held on: review_missing, unresolved_line. |
| `C118` | 1 | held | 0.00 | 0.00 | 0.00 | ADMIN-01 | Held on: review_missing. |
| `C119` | 1 | held | 1,000.01 | 0.00 | 1,000.01 | DIR-01 | Held on: review_missing. |

## Unresolved work, owners and the evidence needed

The full queue is `repair-queue.md` (grouped by owner) and `repair-queue.json` (machine-readable). One entry is one **(subject, version, missing fact)**, not one entry per claim: a claim blocked by three different gaps has three owners. 28 entries are open.

| owner | entries | claims blocked | kinds |
|---|---:|---:|---|
| ADMIN-01 | 19 | 16 | category_unrecognised, permit_unapproved, request_unauthorized, review_missing, review_returned |
| DIR-01 | 1 | 1 | review_missing |
| EMP-01 | 1 | 1 | evidence_missing_payment |
| EMP-03 | 1 | 1 | evidence_missing_payment |
| FIN-01 | 6 | 5 | cancel_no_bound_disposition, cap_missing, fx_missing, late_filing, transfer_after_cancellation |

### Gaps in a shared source

These are worth the most per repair: one row fixes every claim listed.

| entry | source | missing fact | evidence needed | unblocks |
|---|---|---|---|---|
| `ISS-CAP-MISSING-BE-lodging-EUR-2026-09-01` | `registers.caps` | No applicable lodging cap for destination BE in EUR effective on payment date 2026-09-01. | Supply the Caps row: destination BE, category lodging, currency EUR, effective range covering 2026-09-01, and the amount per unit. | `C23` |
| `ISS-CAP-MISSING-NL-lodging-USD-2026-09-01` | `registers.caps` | No applicable lodging cap for destination NL in USD effective on payment date 2026-09-01. | Supply the Caps row: destination NL, category lodging, currency USD, effective range covering 2026-09-01, and the amount per unit. | `C116` |
| `ISS-FX-MISSING-GBP-2026-09-01` | `registers.fx` | No Finance EUR-per-unit rate for GBP on payment date 2026-09-01. | Supply the FX row: rate date 2026-09-01, currency GBP, EUR per currency unit. | `C116`, `C22` |

### What cannot be resolved from the supplied package

These are reported, not solved. Each is a missing fact in a supplied source; the run records it and names an owner rather than assuming a value.

- **cancel_no_bound_disposition** -- 1 entry, owner FIN-01, blocks `C18`.
- **cap_missing** -- 2 entries, owner FIN-01, blocks `C23`, `C116`.
- **category_unrecognised** -- 1 entry, owner ADMIN-01, blocks `C117`.
- **evidence_missing_payment** -- 2 entries, owner EMP-01, EMP-03, blocks `C08`, `C114`.
- **fx_missing** -- 1 entry, owner FIN-01, blocks `C22`, `C116`.
- **late_filing** -- 1 entry, owner FIN-01, blocks `C112`.
- **permit_unapproved** -- 1 entry, owner ADMIN-01, blocks `C25`.
- **request_unauthorized** -- 1 entry, owner ADMIN-01, blocks `C18`.
- **review_missing** -- 16 entries, owner ADMIN-01, DIR-01, blocks `C08`, `C10`, `C13`, `C15`, `C18`, `C22`, `C23`, `C25`, `C26`, `C112`, `C113`, `C114`, `C116`, `C117`, `C118`, `C119`.
- **review_returned** -- 1 entry, owner ADMIN-01, blocks `C21`.
- **transfer_after_cancellation** -- 1 entry, owner FIN-01, blocks `C18`.

### Partial updates across batches

A response resolves only the entry it names. It does not close a sibling entry on the same claim and does not by itself move a claim to a new status; the claim is re-derived from the sources in the next batch. The same rule the supplied data already demonstrates for money -- a partial settlement leaves the obligation pending rather than closing it -- applies to evidence.

| batch | open entries | newly raised | cleared since previous batch |
|---|---:|---|---|
| 1 | 28 | 28 entries | -- |
| 2 | 36 | 9 entries | `ISS-CANCEL-PAUSE-TC121-C121` |
| 3 | 32 | `ISS-CANCEL-NO-BOUND-DISPOSITION-TC019`, `ISS-OVERPAYMENT-C19`, `ISS-REQUEST-UNAUTHORIZED-C18-2`, `ISS-RESOLUTION-REQUIRED-C19`, `ISS-REVIEW-MISSING-C18-2`, `ISS-TRAVEL-CANCELLATION-TC019-C19` | `ISS-CANCEL-NO-BOUND-DISPOSITION-TC121`, `ISS-FINANCE-CANCEL-PENDING-C18`, `ISS-FINANCE-FAILED-C17`, `ISS-LATE-FILING-C12-1`, `ISS-OVERPAYMENT-C20`, `ISS-RESOLUTION-REQUIRED-C18`, `ISS-REVIEW-MISSING-C12-1`, `ISS-REVIEW-RETURNED-C09-1`, `ISS-TRAVEL-CANCELLATION-TC018-C18`, `ISS-TRAVEL-CANCELLATION-TC121-C121` |
| 4 | 28 | `ISS-TRANSFER-AFTER-CANCELLATION-C18` | `ISS-CANCEL-NO-BOUND-DISPOSITION-TC019`, `ISS-OVERPAYMENT-C19`, `ISS-RESOLUTION-REQUIRED-C19`, `ISS-RESOLUTION-REQUIRED-C20`, `ISS-TRAVEL-CANCELLATION-TC019-C19` |

## Money

- net paid this run: **12,034.15 EUR**
- allocation 20,000.00, prior commitments 5,000.00 (of which 2,000.00 already settled and never subtracted twice), accepted new commitments 12,034.15, remaining **2,965.85**
- the budget position is computed once per batch over the whole department/project/period ledger. There is deliberately no per-claim budget figure, because the policy does not define one. A held claim that already carries an accepted commitment still counts against the pool.
- each converted line is rounded to EUR cents half-up and the rounded lines are then summed, never the other way round.
- an exact replay of an already admitted Finance event has no effect on money. `F-C01-1` is redelivered in batch 4 with an identical payload, so the run admits 219 events rather than 220 and net paid is 100.00 lower than a naive total over all rows would suggest.

## Travel cancellations

| id | target | status | financial status | claims | original requests | owner |
|---|---|---|---|---|---|---|
| TC122 | trip | confirmed | no-financial-effect | -- | -- | -- |
| TC121 | permit | confirmed | resolved | `C121` | `REQ-C121` | -- |
| TC018 | trip | confirmed | unresolved | `C18` | `REQ-C18` | FIN-01 |
| TC019 | trip | confirmed | resolved | `C19` | `REQ-C19` | -- |

An exception covering `travel_cancellation` must itself carry the exact `travel_cancellation_id`, and it is read from the exception and nowhere else. Review packets also expose cancellation ids, but the policy states that a packet is not authorization, so the link is never recovered from them. A process whose exception does not name it stays `unresolved` with Finance named. Finance event references and cancellation event references are kept disjoint, and `verify` checks that.

## Run and source references

Run id `run-A`. Snapshots are sealed in order and each binds the preceding one by relative path and SHA-256; snapshot 1 has `predecessor: null`. `source_binding` binds this run's `sources.json` the same way. No file hashes itself, and a sealed batch file is never rewritten -- a later correction produces a new snapshot rather than editing history.

| batch | claims | admitted events | requests | issues | net paid | sha256 |
|---|---:|---:|---:|---:|---:|---|
| 1 | 120 | 100 | 100 | 28 | 0.00 | `175214d8e5cf` |
| 2 | 120 | 200 | 100 | 36 | 11,539.15 | `43d6a7f211d7` |
| 3 | 121 | 210 | 104 | 32 | 11,634.15 | `656b11a4eba1` |
| 4 | 121 | 219 | 104 | 28 | 12,034.15 | `e06f02624713` |

All five sources are read fresh over the network on every run. Only the policy carries a version string, so the observed version of the four business sources is the SHA-256 of the retained bytes. No version number is invented.

| source | locator | observed version | count |
|---|---|---|---|
| `policy` | notion page `3d80b700…` via `/api/v3/loadPageChunk` | `eaefc34b6add` | content_blocks=16, chunks=1 |
| `registers.people` | sheet tab `People` | `a228b55f381b` | csv_rows=18 |
| `registers.trips` | sheet tab `Trips` | `949e7e9737ea` | csv_rows=124 |
| `registers.merchant_payments` | sheet tab `Merchant payments` | `c2c476c7b2f7` | csv_rows=202 |
| `registers.fx` | sheet tab `FX` | `63d57b2e0a62` | csv_rows=3 |
| `registers.caps` | sheet tab `Caps` | `a74cb95e3d57` | csv_rows=3 |
| `registers.budget` | sheet tab `Budget` | `01c418150b54` | csv_rows=4 |
| `registers.review_ledger` | sheet tab `Review ledger` | `fdc5908547e4` | csv_rows=308 |
| `registers.review_packets` | sheet tab `Review packets` | `534d0abf759b` | csv_rows=308 |
| `registers.finance_activity` | sheet tab `Finance activity` | `c9cec4208b19` | csv_rows=221 |
| `registers.travel_cancellations` | sheet tab `Travel cancellations` | `961de2ba41fe` | csv_rows=10 |
| `binder.initial_claims` | drive file `13sRj6s_kMeP…` | `b42a28754b18` | pages=120 |
| `binder.claim_updates` | drive file `16829RwrGrMC…` | `03c15787d18e` | pages=7 |
| `binder.receipts` | drive file `1Ynn1VLH-faR…` | `4c3dc47f187c` | pages=102 |

## Material changes in this revision

### Five-condition closure assertion added, and the three defects it caught

`verify.py` gained an assertion that every claim recorded `closed-reimbursed` satisfies all five conditions at once, re-derived from this run's own retained Review ledger and Finance activity rather than read back out of the snapshot. It immediately failed on real data three times.

**A claim closed on arithmetic alone after a refund.** C20 settled 110.00 in batch 2 and was refunded 10.00 in batch 3, so net paid equalled the 100.00 obligation and the claim closed. Policy block 10 requires an explicit Finance resolution *even if net paid happens to match*. Closure now requires one after an admitted adjustment, a confirmed refund, a negative balance, or a cancellation confirmed after acceptance. Block 15's opposite order -- a business cancellation confirmed before any request was accepted -- needs no separate resolution event, and that carve-out is implemented too. C20 now holds at batch 3 and closes at batch 4 when `F-C20-3` arrives.

**A confirmed cancellation lost its financial history when the claim was reassigned.** C18 revision 2 moved from trip T18 to T18B, after which TC018 found no claim on T18 and collapsed to `no-financial-effect` -- despite an accepted request, a Finance cancellation and a later 100.00 transfer. Block 15 requires observation to continue across reassignment. The cancellation-side link is now built from every arrived revision, while the claim-side finding stays keyed on the claim's current trip, which block 13 requires so that cancelling an old trip never retires the new one. TC018 is now `unresolved`, affecting C18, owned by Finance.

**Finance state findings held a claim forever.** A failed attempt, a pending cancellation or an adjustment held the claim regardless of the fact that clears it. Now a failed attempt is cleared by an authorized retry (block 9), a pending cancellation by the cancellation outcome or a resolution, and an adjustment by its resolution. A transfer admitted *after* a cancellation still needs explicit resolution, because a later transfer reopens reconciliation (block 10). C17 and C19 now close at batch 4; C18 stays held.

### Correction: Finance exceptions do carry a travel cancellation reference

An earlier analysis in this project reported that no Finance exception block carried a `travel_cancellation_id`, and the design was written on that basis. That was wrong. The exception block states it on its own face, as a `Travel cancellation reference` line: C121 revision 2 names `TC121` and C19 revision 3 names `TC019`. The earlier analysis used a field-name whitelist when parsing the exception and filtered the line out before reading it.

The rule itself is unchanged and still enforced: the id is read from the exception and from nowhere else, and is never recovered from Review packets, which the policy states are not authorization. What changed is the outcome. TC121 and TC019 resolve from their own exceptions instead of waiting for Finance to supply a missing id, and C121 and C19 close legitimately. TC018 has no exception at all and remains `unresolved` with Finance named.

## Known gaps in the supplied package

- `requests[].status` allows `dispatched`, but no supplied Finance activity type attests dispatch and the skill does not send requests, so the value is unreachable and never written. `accepted` is used as the observable boundary wherever the policy says "after acceptance/dispatch".
- Every `Review ledger` row cites source revision `DW-D-2`, which no supplied artifact declares. Its value is identical on all 307 rows across every batch and both subject types, so it cannot distinguish a stale reply from a current one. The neighbouring `Affected fields` column is likewise a single constant value on all rows.
- The policy says to read a fixed source manifest before each run; no such artifact is supplied.
- A Finance `adjustment` or `resolution` event carries no expense reference and no claim revision, so it can be admitted and reported but not bound to a specific line.

## Checks not run, and implementation limits

Stated plainly because the task asks for it.

### Checks stated by the task that this run does not perform

- No independent re-computation of the policy text itself. The category sets, the director threshold and the filing rule are transcribed into `src/policy.py` with a citation per constant; the run validates that the policy page is the expected version and retains it, but it does not parse prose into rules.
- Reviewer discretion is never evaluated. The run reports what the supplied decisions say and what is missing, and forms no view on whether a decision was reasonable.
- No check that the supplied Finance amounts are arithmetically consistent with anything outside the claim they name. An `adjustment` or `resolution` event carries no expense reference or claim revision in the supplied schema, so it is admitted and reported but cannot be bound to a specific line.

### Implementation limits

- Fetching does not retry. Each source is fetched once with a 120-second timeout; a network error stops the run. This is deliberate -- falling back to a retained copy would break the guarantee that every run reads the sources fresh -- but it means a transient failure costs a full re-run.
- Batches must be processed in one invocation. The predecessor chain is built in-process, so `--batches 3` alone would write a snapshot with a null predecessor. Always pass the full ascending list.
- The closure assertion links an issue to a claim by exact `-` token in the issue's `record_id` plus a word-boundary match in its reason text. That is precise enough to separate C12, C120 and C121, but it depends on the issue naming convention rather than on a stored claim reference, because the snapshot schema's `issues[]` has no claim field and a shared gap such as a missing rate legitimately blocks several claims at once. `verify` prints this rather than leaving it implicit.
- `budget_position` is written into the snapshot as an extra top-level object. The published schema permits it, and it is how the ledger-level budget is made visible in a sealed artifact, but it is not a schema field.
- A replay reproduces every decision byte for byte, but `sources.json` and the two hashes derived from it necessarily differ between runs, because the task requires each source record to carry the time it was fetched.

### Boundaries that are deliberate, not gaps

- Approvals, exceptions, bookings and real money movement remain human-owned. The run never fabricates a reply, never recommends that a claim be approved or rejected, never sends a real request, never books travel and never moves money.
- Reviewer discretion is supplied by the scenario and never performed here.
- Instructions embedded in receipts, comments or imported records are treated as data, never as permission to change these rules.
