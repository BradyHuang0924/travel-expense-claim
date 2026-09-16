"""Constants read off POL-2026.2. Every entry cites the policy block it comes from.

Nothing here is keyed to a cost_id, claim_id or trip_id: these are the category and
threshold names the policy itself states. All record-level behaviour is derived by
lookup against the normalised sources, never by listing identifiers.
"""
from decimal import Decimal

# block 1: "Employees claim actual paid transport, conference, lodging and meal costs."
REIMBURSABLE_CATEGORIES = frozenset({"transport", "conference", "lodging", "meals"})

# block 1: "Personal purchases have zero entitlement."
ZERO_ENTITLEMENT_CATEGORIES = frozenset({"personal"})

# block 2: "Transport and conference have no category cap. Lodging uses the supplied cap
#          per night; meals use the supplied cap per day."
CAP_BEARING_CATEGORIES = frozenset({"lodging", "meals"})
UNCAPPED_CATEGORIES = frozenset({"transport", "conference"})

# block 3: "A director additionally reviews amounts strictly above EUR 1,000.00 ...
#          Exactly EUR 1,000.00 does not require a director."
DIRECTOR_THRESHOLD_CENTS = 100_000

# block 3: claim and permit review positions.
CLAIM_REQUIRED_ROLES = ("administration", "budget_owner", "supervisor")
PERMIT_REQUIRED_ROLES = ("administration", "budget_owner", "supervisor")
# block 3: "Administration and director never collapse into another role."
NON_COLLAPSIBLE_ROLES = frozenset({"administration", "director"})

# block 2: "EUR uses 1."
BASE_CURRENCY = "EUR"
BASE_RATE = Decimal("1")

# block 4: "The latest ordinary filing date is two calendar months after trip end, inclusive"
FILING_MONTHS = 2

# block 0: "Case clock: 2026-11-15, Europe/Amsterdam."
CASE_CLOCK_DATE = "2026-11-15"
CASE_CLOCK_TZ = "Europe/Amsterdam"

# block 2: the findings an exception may explicitly resolve via covered_issues.
COVERABLE_FINDINGS = frozenset(
    {"late_filing", "late_permit", "permit_unapproved", "travel_cancellation"}
)

# block 14: "A Finance exception covering travel_cancellation must also supply the exact
#           travel_cancellation_id, bound actor, claim/revision, expense, replacement
#           allowed original amount and reason. An amount-only or unrelated exception
#           does not resolve it."
# block 14 also states: "Review packets expose trip/permit revisions and relevant
#           travel_cancellation_ids; a pre-confirmation packet is not post-cancellation
#           authorization." -- so the id may NOT be recovered from Review packets or any
# other source. block 2: "neither the employee nor automation invents one."
FINDINGS_REQUIRING_BOUND_CANCELLATION_ID = frozenset({"travel_cancellation"})

# block 9: Finance activity types that establish outcomes.
FINANCE_ACTIVITY_TYPES = frozenset({
    "accepted", "settled", "failed", "retry_authorized",
    "cancellation_requested", "cancelled", "adjustment", "refund", "resolution",
})

# No supplied Finance activity type denotes dispatch (block 9: "Only supplied Finance
# outcomes establish pending, failed, settled, cancellation, refund and resolution
# facts"), so requests[].status never takes the value below.
UNREACHABLE_REQUEST_STATUSES = frozenset({"dispatched"})
