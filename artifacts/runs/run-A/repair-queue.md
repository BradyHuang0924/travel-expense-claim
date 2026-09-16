# Repair queue -- state after batch 4

28 open entries. One entry is one (subject, version, missing fact); a claim blocked by three different gaps appears three times, once per owner and per fact.

A response resolves only the entry it names. It does not close a sibling entry on the same claim and does not by itself move a claim to a new status; the claim is re-derived from the sources in the next batch.

## By owner

| owner | entries | claims blocked |
|---|---:|---:|
| ADMIN-01 | 19 | 16 |
| DIR-01 | 1 | 1 |
| EMP-01 | 1 | 1 |
| EMP-03 | 1 | 1 |
| FIN-01 | 6 | 5 |

## ADMIN-01

### `ISS-REVIEW-MISSING-C08-1`

- **subject**: claim `C08` rev 1
- **kind**: review_missing
- **missing fact**: C08 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C08`
- **blocks claims**: `C08`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C10-1`

- **subject**: claim `C10` rev 1
- **kind**: review_missing
- **missing fact**: C10 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C10`
- **blocks claims**: `C10`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C112-1`

- **subject**: claim `C112` rev 1
- **kind**: review_missing
- **missing fact**: C112 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C112`
- **blocks claims**: `C112`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C113-1`

- **subject**: claim `C113` rev 1
- **kind**: review_missing
- **missing fact**: C113 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C113`
- **blocks claims**: `C113`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C114-1`

- **subject**: claim `C114` rev 1
- **kind**: review_missing
- **missing fact**: C114 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C114`
- **blocks claims**: `C114`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C116-1`

- **subject**: claim `C116` rev 1
- **kind**: review_missing
- **missing fact**: C116 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C116`
- **blocks claims**: `C116`
- **first seen**: batch 1

### `ISS-CATEGORY-UNRECOGNISED-COST-117-1`

- **subject**: claim `C117` rev 1
- **kind**: category_unrecognised
- **missing fact**: Category 'entertainment' on COST-117-1 is not a policy-recognised category and no cap exists for it.
- **next action**: Either a policy revision recognising this category with an applicable cap, or an explicit Finance exception supplying a replacement allowed original amount.
- **source references**: `COST-117-1`, `M-COST-117-1`, `R-COST-117-1`
- **blocks claims**: `C117`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C117-1`

- **subject**: claim `C117` rev 1
- **kind**: review_missing
- **missing fact**: C117 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C117`
- **blocks claims**: `C117`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C118-1`

- **subject**: claim `C118` rev 1
- **kind**: review_missing
- **missing fact**: C118 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C118`
- **blocks claims**: `C118`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C13-1`

- **subject**: claim `C13` rev 1
- **kind**: review_missing
- **missing fact**: C13 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C13`
- **blocks claims**: `C13`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C15-1`

- **subject**: claim `C15` rev 1
- **kind**: review_missing
- **missing fact**: C15 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C15`
- **blocks claims**: `C15`
- **first seen**: batch 1

### `ISS-REQUEST-UNAUTHORIZED-C18-2`

- **subject**: claim `C18` rev 2
- **kind**: request_unauthorized
- **missing fact**: Finance has acted on REQ-C18 but C18 rev 2 is missing required approval(s) administration, budget_owner, supervisor. The accepted commitment is retained and the request is held; it is not treated as authorized.
- **next action**: Supply the missing review response(s) for administration, budget_owner, supervisor on this claim revision, or Finance direction on the accepted commitment.
- **source references**: `REQ-C18`
- **blocks claims**: `C18`
- **first seen**: batch 3

### `ISS-REVIEW-MISSING-C18-2`

- **subject**: claim `C18` rev 2
- **kind**: review_missing
- **missing fact**: C18 rev 2 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C18`
- **blocks claims**: `C18`
- **first seen**: batch 3

### `ISS-REVIEW-RETURNED-C21-1`

- **subject**: claim `C21` rev 1
- **kind**: review_returned
- **missing fact**: C21 rev 1 was returned by budget_owner with a repair request.
- **next action**: Supply the repaired claim revision addressing the recorded repair request.
- **source references**: `D-C21-1-claim-administration-1`, `D-C21-1-claim-budget_owner-1`
- **blocks claims**: `C21`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C22-1`

- **subject**: claim `C22` rev 1
- **kind**: review_missing
- **missing fact**: C22 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C22`
- **blocks claims**: `C22`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C23-1`

- **subject**: claim `C23` rev 1
- **kind**: review_missing
- **missing fact**: C23 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C23`
- **blocks claims**: `C23`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C25-1`

- **subject**: claim `C25` rev 1
- **kind**: review_missing
- **missing fact**: C25 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C25`
- **blocks claims**: `C25`
- **first seen**: batch 1

### `ISS-REVIEW-MISSING-C26-1`

- **subject**: claim `C26` rev 1
- **kind**: review_missing
- **missing fact**: C26 rev 1 has no reply for required role(s) administration, budget_owner, supervisor.
- **next action**: Supply the review response for administration, budget_owner, supervisor on this claim revision.
- **source references**: `C26`
- **blocks claims**: `C26`
- **first seen**: batch 1

### `ISS-PERMIT-UNAPPROVED-P25`

- **subject**: permit `P25` rev 1
- **kind**: permit_unapproved
- **missing fact**: International trip T25 needs an approved permit before the first arrangement or payment commitment; P25 is missing approvals from administration, budget_owner, supervisor.
- **next action**: Supply the missing permit review responses, or an explicit Finance exception covering permit_unapproved.
- **source references**: `P25`, `T25`
- **blocks claims**: `C25`
- **first seen**: batch 1

## DIR-01

### `ISS-REVIEW-MISSING-C119-1`

- **subject**: claim `C119` rev 1
- **kind**: review_missing
- **missing fact**: C119 rev 1 has no reply for required role(s) director.
- **next action**: Supply the review response for director on this claim revision.
- **source references**: `D-C119-1-claim-administration-1`, `D-C119-1-claim-budget_owner-1`, `D-C119-1-claim-supervisor-1`
- **blocks claims**: `C119`
- **first seen**: batch 1

## EMP-01

### `ISS-EVIDENCE-MISSING-COST-08`

- **subject**: claim `C08` rev 1
- **kind**: evidence_missing_payment
- **missing fact**: COST-08 has a receipt but no settled merchant transaction; a receipt alone does not prove employee payment.
- **next action**: Supply the settled merchant transaction matching employee EMP-01, trip T08, cost COST-08, currency EUR and gross 120.00, or withdraw the line.
- **source references**: `COST-08`, `R-COST-08`
- **blocks claims**: `C08`
- **first seen**: batch 1

## EMP-03

### `ISS-EVIDENCE-MISSING-COST-114-2`

- **subject**: claim `C114` rev 1
- **kind**: evidence_missing_payment
- **missing fact**: COST-114-2 has a receipt but no settled merchant transaction; a receipt alone does not prove employee payment.
- **next action**: Supply the settled merchant transaction matching employee EMP-03, trip T114, cost COST-114-2, currency EUR and gross 15.00, or withdraw the line.
- **source references**: `COST-114-2`, `R-COST-114-2`
- **blocks claims**: `C114`
- **first seen**: batch 1

## FIN-01

### `ISS-LATE-FILING-C112-1`

- **subject**: claim `C112` rev 1
- **kind**: late_filing
- **missing fact**: Claim C112 rev 1 was submitted 2026-09-02, after the ordinary filing deadline 2026-09-01 for a trip ending 2026-07-01.
- **next action**: Supply an explicit Finance exception covering late_filing, or the claim remains held.
- **source references**: `C112`, `T112`
- **blocks claims**: `C112`
- **first seen**: batch 1

### `ISS-TRANSFER-AFTER-CANCELLATION-C18`

- **subject**: claim `C18` rev 2
- **kind**: transfer_after_cancellation
- **missing fact**: Finance cancelled REQ-C18 and a confirmed transfer of 10000 cents is nonetheless admitted. A later transfer reopens reconciliation and closure needs explicit resolution.
- **next action**: Supply the Finance resolution reconciling the cancelled request with the admitted transfer.
- **source references**: `F-C18-1`, `F-C18-2`, `F-C18-3`, `F-C18-accepted`
- **blocks claims**: `C18`
- **first seen**: batch 4

### `ISS-CAP-MISSING-BE-lodging-EUR-2026-09-01`

- **subject**: source `registers.caps`
- **kind**: cap_missing
- **missing fact**: No applicable lodging cap for destination BE in EUR effective on payment date 2026-09-01.
- **next action**: Supply the Caps row: destination BE, category lodging, currency EUR, effective range covering 2026-09-01, and the amount per unit.
- **source references**: `COST-23`, `M-COST-23`, `R-COST-23`
- **blocks claims**: `C23`
- **first seen**: batch 1

### `ISS-CAP-MISSING-NL-lodging-USD-2026-09-01`

- **subject**: source `registers.caps`
- **kind**: cap_missing
- **missing fact**: No applicable lodging cap for destination NL in USD effective on payment date 2026-09-01.
- **next action**: Supply the Caps row: destination NL, category lodging, currency USD, effective range covering 2026-09-01, and the amount per unit.
- **source references**: `COST-116-1`, `M-COST-116-1`, `R-COST-116-1`
- **blocks claims**: `C116`
- **first seen**: batch 1

### `ISS-FX-MISSING-GBP-2026-09-01`

- **subject**: source `registers.fx`
- **kind**: fx_missing
- **missing fact**: No Finance EUR-per-unit rate for GBP on payment date 2026-09-01.
- **next action**: Supply the FX row: rate date 2026-09-01, currency GBP, EUR per currency unit.
- **source references**: `COST-116-2`, `COST-22`, `M-COST-116-2`, `M-COST-22`, `R-COST-116-2`, `R-COST-22`
- **blocks claims**: `C116`, `C22`
- **first seen**: batch 1

### `ISS-CANCEL-NO-BOUND-DISPOSITION-TC018`

- **subject**: travel_cancellation `TC018` rev 1
- **kind**: cancel_no_bound_disposition
- **missing fact**: Confirmed cancellation TC018 affects C18 but no Finance cost disposition names this travel_cancellation_id. The supplied exception does not carry a travel_cancellation_id, and the link is not recovered from any other source.
- **next action**: Supply an explicit Finance exception that itself states the exact travel_cancellation_id TC018, bound actor, claim/revision, expense, replacement allowed original amount and reason.
- **source references**: `TC018-confirmed`, `TC018-requested`
- **blocks claims**: `C18`
- **first seen**: batch 2

