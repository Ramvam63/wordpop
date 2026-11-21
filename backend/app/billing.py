"""WordPop Plus: the natural voices as a paid feature (Stripe subscriptions).

- Everyone gets a free trial (PLUS_TRIAL_DAYS, default 7) that starts the first time they
  listen with a natural voice - no card needed.
- After that, Plus is active while the Stripe subscription is active (or trialing/past due).
- Admins (ADMIN_EMAILS) always have Plus.
- Until Stripe is configured, the voices are free for everyone.

Stripe hosts the payment page (Checkout) and the "manage subscription" page (Customer
Portal), so card details never reach this server. A webhook keeps the user's status in sync.
"""

import logging
from datetime import UTC, datetime, timedelta

import stripe

from .config import get_settings
from .models import User
from .srs import as_utc

ACTIVE_STATUSES = {"active", "trialing", "past_due"}


def enabled() -> bool:
    s = get_settings()
    return bool(s.stripe_secret_key and s.stripe_price_monthly and s.stripe_price_yearly)


def client() -> stripe.StripeClient:
    return stripe.StripeClient(get_settings().stripe_secret_key)


def price_id(plan: str) -> str:
    s = get_settings()
    return {"monthly": s.stripe_price_monthly, "yearly": s.stripe_price_yearly}[plan]


def trial_ends_at(user: User) -> datetime | None:
    started = as_utc(user.voice_trial_started_at)
    return started + timedelta(days=get_settings().plus_trial_days) if started else None


def has_subscription(user: User) -> bool:
    return user.plus_status in ACTIVE_STATUSES


def plus_reason(user: User, now: datetime | None = None) -> str | None:
    """Why this user can use the natural voices ("free", "admin", "subscription", "trial"),
    or None if they can't."""
    now = now or datetime.now(UTC)
    if not enabled():
        return "free"
    if user.email.lower() in get_settings().admin_emails:
        return "admin"
    if has_subscription(user):
        return "subscription"
    ends = trial_ends_at(user)
    if ends and now < ends:
        return "trial"
    return None


def start_trial_if_new(user: User, now: datetime | None = None) -> bool:
    if user.voice_trial_started_at is None and enabled():
        user.voice_trial_started_at = now or datetime.now(UTC)
        return True
    return False


def _get(obj, key, default=None):
    try:
        return obj[key]
    except (KeyError, TypeError, IndexError):
        return getattr(obj, key, default)


def apply_subscription(user: User, sub) -> None:
    """Copy a Stripe subscription's state onto the user."""
    s = get_settings()
    items = _get(_get(sub, "items", {}), "data", []) or []
    first = items[0] if items else {}
    price = _get(_get(first, "price", {}), "id")
    # Newer Stripe API versions keep the period end on the item, older ones on the subscription.
    period_end = _get(sub, "current_period_end") or _get(first, "current_period_end")

    user.stripe_customer_id = _get(sub, "customer") or user.stripe_customer_id
    user.plus_status = _get(sub, "status")
    user.plus_plan = {s.stripe_price_monthly: "monthly", s.stripe_price_yearly: "yearly"}.get(price)
    user.plus_until = datetime.fromtimestamp(period_end, UTC) if period_end else None
    user.plus_cancel_at_period_end = bool(_get(sub, "cancel_at_period_end"))


def status(user: User) -> dict:
    s = get_settings()
    reason = plus_reason(user)
    trial_end = trial_ends_at(user)
    subscribed = has_subscription(user)
    renews = as_utc(user.plus_until) if user.plus_until and subscribed else None
    return {
        "billing_enabled": enabled(),
        "plus": reason is not None,
        "reason": reason,
        "trial_days": s.plus_trial_days,
        "trial_started": user.voice_trial_started_at is not None,
        "trial_ends_at": trial_end.isoformat() if trial_end else None,
        "plan": user.plus_plan if subscribed else None,
        "renews_at": renews.isoformat() if renews else None,
        "cancel_at_period_end": bool(user.plus_cancel_at_period_end) if subscribed else False,
        "can_manage": bool(user.stripe_customer_id) and enabled(),
        "prices": {"monthly": s.plus_price_monthly_label, "yearly": s.plus_price_yearly_label},
    }


def cancel_everything(user: User) -> None:
    """Cancel the user's Stripe subscriptions right away (used when an account is deleted).
    Best effort: a Stripe problem must never block deleting an account."""
    if not (enabled() and user.stripe_customer_id):
        return
    try:
        client_ = client()
        for sub in client_.v1.subscriptions.list({"customer": user.stripe_customer_id, "status": "all"}):
            if sub["status"] not in ("canceled", "incomplete_expired"):
                client_.v1.subscriptions.cancel(sub["id"])
    except stripe.StripeError as exc:  # logged for follow-up
        logging.getLogger(__name__).warning(
            "Couldn't cancel Stripe subscription for user %s: %s", user.id, exc
        )
