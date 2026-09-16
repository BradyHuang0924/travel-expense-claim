"""Line and claim evaluation, and the ledger-level budget position.

No rule in this module is keyed to a cost_id, claim_id or trip_id. Every decision is a
lookup against the normalised sources; a lookup miss is what produces `unresolved`.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from . import policy


def to_cents(amount: Decimal) -> int:
    """Decimal half-up to EUR cents. block 2: 'Round each converted line to EUR cents
    using decimal half-up; sum rounded line amounts.'"""
    return int(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)


def filing_deadline(trip_end: str) -> str:
    """block 4: two calendar months after trip end, inclusive, nonexistent day clamped
    to month end."""
    year, month, day = (int(p) for p in trip_end.split("-"))
    month += policy.FILING_MONTHS
    while month > 12:
        month -= 12
        year += 1
    day = min(day, calendar.monthrange(year, month)[1])
    return f"{year:04d}-{month:02d}-{day:02d}"


@dataclass
class Issue:
    """One missing fact.

    The four schema fields are what reaches the snapshot. The rest is the repair-queue
    context: an entry is one (subject, version, missing fact), so the subject and its
    version are recorded where the finding is raised rather than matched back later.
    """
    record_id: str
    reason: str
    owner: str
    resolution_needed: str
    subject_type: str = "claim"          # claim | permit | travel_cancellation | source
    subject_ref: str = ""
    subject_revision: int | None = None
    source_refs: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    kind: str = ""

    def as_record(self) -> dict:
        return {
            "record_id": self.record_id,
            "reason": self.reason,
            "owner": self.owner,
            "resolution_needed": self.resolution_needed,
        }


@dataclass
class LineResult:
    cost_id: str
    status: str                       # supported | excluded | unresolved
    allowed_cents: int | None
    reason: str
    source_ids: list[str]
    issues: list[Issue] = field(default_factory=list)


@dataclass
class ClaimResult:
    claim: object
    status: str
    lines: list[LineResult]
    allowed_cents: int | None
    paid_cents: int
    balance_cents: int | None
    decision_ids: list[str]
    next_owner: str | None
    reason: str
    issues: list[Issue] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    approvals_complete: bool = False
    missing_roles: list[str] = field(default_factory=list)
    request: dict | None = None


class Registers:
    """Indexed views over the normalised register tabs."""

    def __init__(self, tables: dict, norm):
        t = {name: norm.table(rows) for name, rows in tables.items()}
        self.people = {r["Employee ID"]: r for r in t["People"]}
        self.trips = {r["Trip reference"]: r for r in t["Trips"]}
        self.payments = {r["Expense reference"]: r for r in t["Merchant payments"]}
        self.fx = {(r["Rate date"], r["Currency"]): r for r in t["FX"]}
        self.caps = t["Caps"]
        self.budget = t["Budget"]
        self.review_ledger = t["Review ledger"]
        self.review_packets = {r["Decision reference"]: r for r in t["Review packets"]}
        self.finance_activity = t["Finance activity"]
        self.cancellations = t["Travel cancellations"]
        self._norm = norm

    # ---- reference lookups -------------------------------------------------
    def rate(self, currency: str, payment_date: str):
        """block 2: Finance's exact payment-date rate; EUR uses 1.

        Returns (rate, evidence_reference). EUR needs no supplied row, so its evidence
        reference is None -- the rate of 1 comes from the policy, not from the register.
        """
        if currency == policy.BASE_CURRENCY:
            return policy.BASE_RATE, None
        row = self.fx.get((payment_date, currency))
        if row is None:
            return None, None
        return Decimal(row["EUR per currency unit"]), row["Rate reference"]

    def cap(self, destination: str, category: str, currency: str, on: str):
        """block 2: caps are in the expense currency for the destination and the
        employee-payment date; date range inclusive. Returns the whole row so its
        reference can be recorded as evidence."""
        for row in self.caps:
            if (row["Destination"] == destination
                    and row["Category"] == category
                    and row["Currency"] == currency
                    and row["Effective from"] <= on <= row["Effective to"]):
                return row
        return None

    def decisions_for(self, subject_type: str, subject_ref: str, revision: int,
                      upto_batch: int) -> list[dict]:
        return [r for r in self.review_ledger
                if r["Subject type"] == subject_type
                and r["Subject reference"] == subject_ref
                and r["Revision"] == str(revision)
                and int(r["Arrival batch"]) <= upto_batch]


def approved_roles(rows: list[dict], people_row: dict) -> tuple[set[str], dict[str, str]]:
    """Collect roles that actually replied, and their outcomes.

    block 3: 'When budget owner and supervisor are the same stable person, one response
    with both roles satisfies those two positions.' The collapse is only honoured when
    the reply itself lists both roles AND the directory confirms one person holds both;
    it is never inferred from a single-role reply.
    """
    got: set[str] = set()
    outcomes: dict[str, str] = {}
    same_person = (people_row.get("Budget owner")
                   and people_row.get("Budget owner") == people_row.get("Supervisor"))
    for row in rows:
        roles = [r.strip() for r in row["Review roles"].split("\n") if r.strip()]
        if len(roles) > 1:
            if policy.NON_COLLAPSIBLE_ROLES & set(roles):
                continue  # administration/director never collapse into another role
            if set(roles) == {"budget_owner", "supervisor"} and not same_person:
                continue  # combined reply not supported by the directory
        for role in roles:
            got.add(role)
            outcomes[role] = row["Outcome"]
    return got, outcomes


def evaluate_line(line, receipt, reg: Registers, trip: dict | None,
                  exception, prior_settled_cost_ids: dict[str, str],
                  claim_id: str, revision: int) -> LineResult:
    """Decide one expense line.

    Evidence is collected before any decision is taken, so an early return never drops a
    reference the run actually holds. The decision order -- category, evidence, cap, rate
    -- still governs which reason is reported, because the cap and rate lookups are keyed
    on the employee-payment date and are undefined without a payment.
    """
    src = [line.cost_id]
    if receipt is not None:
        src.append(receipt.receipt_id)
    payment = reg.payments.get(line.cost_id)
    if payment is not None:
        # Held evidence is recorded whether or not it ends up supporting the line.
        src.append(payment["Transaction reference"])

    def result(status, cents, reason, issues=None):
        return LineResult(line.cost_id, status, cents, reason, sorted(set(src)),
                          issues or [])

    def issue(record_id, reason, owner, needed, kind, subject_type="claim",
              subject_ref=None, subject_revision=None):
        return Issue(record_id, reason, owner, needed,
                     subject_type=subject_type,
                     subject_ref=subject_ref if subject_ref is not None else claim_id,
                     subject_revision=(subject_revision if subject_ref is not None
                                       else revision),
                     source_refs=sorted(set(src)), blocks=[claim_id], kind=kind)

    # --- previously settled obligation (block 8) -----------------------------
    if line.cost_id in prior_settled_cost_ids:
        ref = prior_settled_cost_ids[line.cost_id]
        src.append(ref)
        return result("excluded", 0,
                      f"Previously settled obligation on {ref}; linked and excluded so "
                      f"the cost is not paid twice.")

    if receipt is None:
        return result("unresolved", None,
                      "No receipt record found for this expense reference.",
                      [issue(f"ISS-EVIDENCE-NO-RECEIPT-{line.cost_id}",
                             f"Claim line {line.cost_id} has no receipt record in the "
                             f"receipt binder.", "ADMIN-01",
                             "Supply the receipt for this expense reference, or withdraw "
                             "the line.", "evidence_no_receipt")])

    category = receipt.category

    # --- zero entitlement (block 1) ------------------------------------------
    if category in policy.ZERO_ENTITLEMENT_CATEGORIES:
        return result("excluded", 0,
                      f"Category '{category}' carries zero entitlement under the policy; "
                      f"known zero, not an unknown amount.")

    # --- unknown category (block 1) ------------------------------------------
    if category not in policy.REIMBURSABLE_CATEGORIES:
        return result("unresolved", None,
                      f"Unrecognised category '{category}'; unresolved, never an assumed "
                      f"zero.",
                      [issue(f"ISS-CATEGORY-UNRECOGNISED-{line.cost_id}",
                             f"Category '{category}' on {line.cost_id} is not a "
                             f"policy-recognised category and no cap exists for it.",
                             "ADMIN-01",
                             "Either a policy revision recognising this category with an "
                             "applicable cap, or an explicit Finance exception supplying "
                             "a replacement allowed original amount.",
                             "category_unrecognised")])

    # --- payment proof (block 1) ---------------------------------------------
    proof_ok = (
        payment is not None
        and payment.get("Payment status") == "settled"
        and payment.get("Employee ID") == receipt.employee_id
        and payment.get("Trip reference") == receipt.trip_id
        and payment.get("Currency") == receipt.currency
        and Decimal(payment.get("Gross amount", "0").replace(",", "")) == receipt.gross
    )
    if not proof_ok:
        detail = ("no settled merchant transaction" if payment is None
                  else "merchant transaction does not match on employee/trip/currency/gross")
        return result("unresolved", None,
                      f"Missing proof of payment ({detail}).",
                      [issue(f"ISS-EVIDENCE-MISSING-{line.cost_id}",
                             f"{line.cost_id} has a receipt but {detail}; a receipt alone "
                             f"does not prove employee payment.",
                             receipt.employee_id,
                             f"Supply the settled merchant transaction matching employee "
                             f"{receipt.employee_id}, trip {receipt.trip_id}, cost "
                             f"{line.cost_id}, currency {receipt.currency} and gross "
                             f"{receipt.gross}, or withdraw the line.",
                             "evidence_missing_payment")])
    paid_on = payment["Paid date"]

    # --- applicable cap (block 2) --------------------------------------------
    allowed_original = receipt.gross
    if category in policy.CAP_BEARING_CATEGORIES:
        destination = trip["Destination"] if trip else None
        cap_row = (reg.cap(destination, category, receipt.currency, paid_on)
                   if destination else None)
        if cap_row is None:
            return result("unresolved", None,
                          f"Missing applicable {category} cap for {destination} on "
                          f"{paid_on}.",
                          [issue(f"ISS-CAP-MISSING-{destination}-{category}-"
                                 f"{receipt.currency}-{paid_on}",
                                 f"No applicable {category} cap for destination "
                                 f"{destination} in {receipt.currency} effective on "
                                 f"payment date {paid_on}.",
                                 "FIN-01",
                                 f"Supply the Caps row: destination {destination}, "
                                 f"category {category}, currency {receipt.currency}, "
                                 f"effective range covering {paid_on}, and the amount "
                                 f"per unit.",
                                 "cap_missing", subject_type="source",
                                 subject_ref="registers.caps")])
        src.append(cap_row["Cap reference"])
        units = receipt.documented_units
        if units < 1:
            return result("unresolved", None,
                          "Documented units is not a positive integer.",
                          [issue(f"ISS-UNITS-INVALID-{line.cost_id}",
                                 f"Documented units on {line.cost_id} is {units}; units "
                                 f"must be a positive integer.", "ADMIN-01",
                                 "Supply a corrected receipt with positive integer units.",
                                 "units_invalid")])
        cap_amount = Decimal(cap_row["Amount per unit"].replace(",", ""))
        allowed_original = min(receipt.gross, cap_amount * units)

    # --- Finance exception replacing the allowed original amount (block 2) ----
    exception_note = ""
    if exception is not None and exception.cost_id == line.cost_id:
        allowed_original = exception.allowed_original
        exception_note = (f" Finance exception by {exception.actor} replaces the allowed "
                          f"original amount with {exception.allowed_original}.")

    # --- payment-date rate (block 2) -----------------------------------------
    rate, rate_ref = reg.rate(receipt.currency, paid_on)
    if rate is None:
        return result("unresolved", None,
                      f"Missing payment-date rate for {receipt.currency} on {paid_on}.",
                      [issue(f"ISS-FX-MISSING-{receipt.currency}-{paid_on}",
                             f"No Finance EUR-per-unit rate for {receipt.currency} on "
                             f"payment date {paid_on}.",
                             "FIN-01",
                             f"Supply the FX row: rate date {paid_on}, currency "
                             f"{receipt.currency}, EUR per currency unit.",
                             "fx_missing", subject_type="source",
                             subject_ref="registers.fx")])
    if rate_ref:
        src.append(rate_ref)

    cents = to_cents(allowed_original * rate)
    reason = (f"Supported: {category}, gross {receipt.gross} {receipt.currency} paid "
              f"{paid_on}, allowed original {allowed_original}, rate {rate}." +
              exception_note)
    return result("supported", cents, reason)


def budget_position(reg: Registers, accepted_commitments_cents: int,
                    net_settled_cents: int) -> dict:
    """block 5: 'Budget review receives the whole department/project/period ledger:
    allocation less net settled expenditure less remaining commitments. A commitment
    includes its settled portion; do not subtract the full commitment and its settled
    portion again. Include prior obligations outside the current batch and all accepted
    new requests.'

    Computed once per batch over the whole ledger. There is deliberately no per-claim
    variant: a single claim's budget position is not defined in this policy.
    """
    allocation = 0
    prior_commitment = 0
    prior_settled = 0
    prior_refunded = 0
    for row in reg.budget:
        amount = to_cents(Decimal(row["Allocation or commitment (EUR)"].replace(",", "")))
        settled = to_cents(Decimal(row["Settled (EUR)"].replace(",", "")))
        refunded = to_cents(Decimal(row["Refunded (EUR)"].replace(",", "")))
        if row["Entry type"] == "allocation":
            allocation += amount
        else:
            prior_commitment += amount
            prior_settled += settled
            prior_refunded += refunded
    # A commitment already includes its settled portion, so only the commitment is
    # subtracted; the settled column is reported, never subtracted a second time.
    remaining = allocation - prior_commitment - accepted_commitments_cents
    return {
        "allocation_cents": allocation,
        "prior_commitments_cents": prior_commitment,
        "prior_commitments_settled_cents": prior_settled,
        "prior_commitments_refunded_cents": prior_refunded,
        "accepted_new_commitments_cents": accepted_commitments_cents,
        "net_settled_this_run_cents": net_settled_cents,
        "remaining_cents": remaining,
        "note": ("Commitments include their settled portion; the settled figures are "
                 "reported but never subtracted again. Adequate funds alone are not a "
                 "budget approval."),
    }
