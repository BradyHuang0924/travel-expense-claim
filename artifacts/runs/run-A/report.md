# Travel expense claim run `run-A`

Batches processed: 1, 2, 3, 4. Case clock 2026-11-15 Europe/Amsterdam; the machine's date is used only to name the run directory.

## Outcome

| status | claims | allowed | net paid |
|---|---:|---:|---:|
| closed-reimbursed | 103 | 11,934.15 | 11,934.15 |
| held | 16 | 1,520.01 (+6 unknown) | 100.00 |
| rejected | 1 | 40.00 | 0.00 |
| withdrawn | 1 | 50.00 | 0.00 |
| **total** | **121** | | **12,034.15** |

### Financial completion

A claim is recorded `closed-reimbursed` only when all five hold together: every required approval for the current revision is present and approves; the authorized obligation equals the sum of the current supported lines; net paid equals that obligation exactly; every Finance resolution the policy requires is admitted; and no issue against the claim is open.

Two things explicitly do not count as complete:

- **Partial settlement is not completion.** none in this run stay `pending`; the obligation is not closed by a part payment.
- **A negative balance is not completion.** none in this run is an overpayment requiring explicit Finance resolution, so it is `held` and owned by Finance, not closed.

Nothing is closed to make the totals look complete, and no Finance resolution is invented.

## What this run could not resolve

These are reported, not solved. Each is a missing fact in a supplied source; the skill records it and names an owner rather than assuming a value.

| kind | entries | owner(s) | claims blocked |
|---|---:|---|---:|
| cancel_no_bound_disposition | 1 | FIN-01 | 1 |
| cap_missing | 2 | FIN-01 | 2 |
| category_unrecognised | 1 | ADMIN-01 | 1 |
| evidence_missing_payment | 2 | EMP-01, EMP-03 | 2 |
| fx_missing | 1 | FIN-01 | 2 |
| late_filing | 1 | FIN-01 | 1 |
| permit_unapproved | 1 | ADMIN-01 | 1 |
| request_unauthorized | 1 | ADMIN-01 | 1 |
| review_missing | 16 | ADMIN-01, DIR-01 | 16 |
| review_returned | 1 | ADMIN-01 | 1 |
| transfer_after_cancellation | 1 | FIN-01 | 1 |

## Money

- net paid this run: **12,034.15 EUR**
- allocation 20,000.00, prior commitments 5,000.00 (of which 2,000.00 already settled and not subtracted twice), accepted new commitments 12,034.15, remaining **2,965.85**
- the budget position is computed once per batch over the whole department/project/period ledger. There is no per-claim budget figure, because the policy does not define one. A held claim that already carries an accepted commitment still counts against the pool.
- admitted transfers are never reduced by a hold, a withdrawal or a closure.

## Travel cancellations

| id | target | status | financial status | claims | owner |
|---|---|---|---|---|---|
| TC122 | trip | confirmed | no-financial-effect | -- | -- |
| TC121 | permit | confirmed | resolved | C121 | -- |
| TC018 | trip | confirmed | unresolved | C18 | FIN-01 |
| TC019 | trip | confirmed | resolved | C19 | -- |

An exception covering `travel_cancellation` must itself carry the exact `travel_cancellation_id`, and it is read from the exception and nowhere else. Review packets also expose cancellation ids, but the policy states that a packet is not authorization, so the link is never recovered from them. A process whose exception does not name it stays `unresolved` with Finance named.

## Per batch

| batch | claims | admitted events | requests | issues | net paid |
|---|---:|---:|---:|---:|---:|
| 1 | 120 | 100 | 100 | 28 | 0.00 |
| 2 | 120 | 200 | 100 | 36 | 11,539.15 |
| 3 | 121 | 210 | 104 | 32 | 11,634.15 |
| 4 | 121 | 219 | 104 | 28 | 12,034.15 |

Each snapshot binds its predecessor by relative path and SHA-256, and binds this run's `sources.json` by path and SHA-256. A sealed batch file is never rewritten: a later correction produces a new snapshot rather than editing history. No file hashes itself.

## Sources

All five are read fresh over the network on every run; nothing is served from a cache. Only the policy carries a version string, so the observed version of the four business sources is the SHA-256 of the retained bytes. No version number is invented.

| source | locator | observed version | count |
|---|---|---|---|
| `policy` | notion `3d80b700…` | `eaefc34b6add` | content_blocks=16, chunks=1 |
| `registers.people` | tab `People` | `a228b55f381b` | csv_rows=18 |
| `registers.trips` | tab `Trips` | `949e7e9737ea` | csv_rows=124 |
| `registers.merchant_payments` | tab `Merchant payments` | `c2c476c7b2f7` | csv_rows=202 |
| `registers.fx` | tab `FX` | `63d57b2e0a62` | csv_rows=3 |
| `registers.caps` | tab `Caps` | `a74cb95e3d57` | csv_rows=3 |
| `registers.budget` | tab `Budget` | `01c418150b54` | csv_rows=4 |
| `registers.review_ledger` | tab `Review ledger` | `fdc5908547e4` | csv_rows=308 |
| `registers.review_packets` | tab `Review packets` | `534d0abf759b` | csv_rows=308 |
| `registers.finance_activity` | tab `Finance activity` | `c9cec4208b19` | csv_rows=221 |
| `registers.travel_cancellations` | tab `Travel cancellations` | `961de2ba41fe` | csv_rows=10 |
| `binder.initial_claims` | drive `13sRj6s_kM…` | `b42a28754b18` | pages=120 |
| `binder.claim_updates` | drive `16829RwrGr…` | `03c15787d18e` | pages=7 |
| `binder.receipts` | drive `1Ynn1VLH-f…` | `4c3dc47f187c` | pages=102 |

## Known gaps in the supplied package

- A cancellation whose exception does not name its `travel_cancellation_id` cannot be resolved from the supplied package; the id is never recovered from review packets, which the policy says are not authorization.
- `requests[].status` allows `dispatched`, but no supplied Finance activity type attests dispatch and the skill does not send requests, so the value is unreachable and never written.
- Every `Review ledger` row cites source revision `DW-D-2`, which no supplied artifact declares. Its value is identical on all rows across all batches, so it cannot distinguish a stale reply from a current one.
- The policy says to read a fixed source manifest before each run; no such artifact is supplied.

## Not done in this revision

- Reviewer discretion is supplied by the scenario and never performed here.
- Approvals, exceptions, bookings and money movement remain human-owned.
- Instructions embedded in receipts, comments or imported records are treated as data, never as permission to change these rules.
