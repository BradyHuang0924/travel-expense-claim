# Conventions for fields the sources do not supply

The snapshot schema requires four things no business source provides. Each convention
below states its policy basis and how it behaves on a rerun.

## `requests[].request_id`

`"REQ-" + claim_id`. A pure function of the claim id: no run id, no timestamp, no
counter, so the same obligation yields the same id on every rerun.

The obligation is the **claim**, not the claim revision. Basis: POL-2026.2 block 8, "Use
a stable request ID for the same obligation; replay cannot create another request or
reimbursement of a previously committed/settled cost." The supplied Finance register
confirms the shape empirically -- every one of the 104 claims Finance has acted on
carries exactly `REQ-<claim_id>`, and a claim with three revisions keeps one request
reference across all of them.

Before minting, the admitted Finance events are consulted. If the id already exists, it
is the same obligation continuing; a second id is never created. If our computed payee,
currency or claim disagrees with the admitted events for that id, nothing is overwritten:
the request is held and an issue is raised (block 9, "Validate request, payee, currency,
positive integer cents, time and actor before admission").

## `requests[].revision`

The claim revision whose reviewed entitlement the proposal is built from. It advances
only when both hold:

1. a material change under block 7 is detected, and
2. the required review responses for the new revision have arrived and approve.

It does **not** advance on: our own re-derivation under full recheck, an exact replay, an
arriving Finance event, or a batch boundary. Advancing the revision never mints a new
`request_id`.

## `requests[].status`

| status | entered when | left when |
|---|---|---|
| `proposed` | the claim is ready and no Finance event references the request | Finance `accepted` arrives, or a conflicting fact holds it |
| `accepted` | a Finance `accepted` event is admitted | `cancellation_requested`, `cancelled`, or full settlement |
| `dispatched` | never -- see below | -- |
| `cancel-pending` | Finance `cancellation_requested` | Finance `cancelled` or a resolution |
| `cancelled` | Finance `cancelled` | a later admitted transfer reopens reconciliation |
| `settled` | admitted transfers net to the current obligation | a later refund or adjustment |
| `held` | a conflicting replay, or a competing replacement after acceptance | the named Finance fact arrives |

`dispatched` is never written. The supplied Finance activity vocabulary is `accepted`,
`settled`, `failed`, `retry_authorized`, `cancellation_requested`, `cancelled`,
`adjustment`, `refund`, `resolution` -- none of which denotes dispatch. Block 9 limits
established facts to supplied Finance outcomes, and the skill itself must not send real
requests. `accepted` is therefore used as the observable boundary wherever the policy
says "after acceptance/dispatch". `verify.py` asserts the value never appears.

Partial settlement stays pending (block 10); it does not become `settled`.

## `travel_cancellations[].financial_status`

* `no-financial-effect` -- the process is confirmed and no claim, cost or obligation is
  attached (block 14: "recorded as a no-financial-effect trip/permit process, without
  inventing a claim").
* `resolved` -- the process is confirmed **and** a Finance exception that itself states
  the exact `travel_cancellation_id`, bound actor, claim/revision, expense, replacement
  allowed original amount and reason is supplied **and** the required reviews for that
  claim revision approve. Where the cancellation followed Finance acceptance, an admitted
  Finance `resolution` event is required as well (block 10).
* `unresolved` -- everything else, including a process that is only requested.

The `travel_cancellation_id` is read from the exception and from nowhere else. Block 14
requires the exception to supply it and adds, in the same block, that "Review packets
expose trip/permit revisions and relevant travel_cancellation_ids; **a pre-confirmation
packet is not post-cancellation authorization**". Recovering the id by joining Review
packets on (claim, revision) would be automation supplying an authorisation link Finance
did not give, which block 2 forbids: "neither the employee nor automation invents one".

### Recorded consequence on the supplied package

No Finance exception block in either claim binder has a `travel_cancellation_id` field at
all. Exceptions that declare `Covered issues: Travel cancellation` therefore do not
resolve the finding. They remain valid as amount-only exceptions -- their replacement
allowed original amount is applied, which is exactly the case block 14 describes when it
says "an amount-only or unrelated exception does not resolve it". The affected claims stay
held with an issue owned by Finance.

## Derived facts versus derived authority

Deriving a **fact** from the sources is required: which cost was already settled, which
destination a trip has, whether a rate exists. Deriving an **authorisation** is
forbidden: an approval that was not given, an exception that was not issued, a dispatch
that was not attested, or a binding that a required field does not carry.
