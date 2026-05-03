"""
premium/models.py
-----------------
Handles subscription plans, user subscriptions, and payment history.

Key design decisions:
  - SubscriptionPlan: `features` stored as JSONField (list of strings) rather
    than a separate PlanFeature table — plan features rarely change and do not
    need to be queried individually; JSON is the right trade-off here.
  - Subscription: `stripe_customer_id` stored on the subscription, not the
    user — a user could theoretically switch payment providers in the future.
    Keeping Stripe coupling here rather than polluting the Users model.
  - Subscription: billing_cycle is an explicit field (monthly / yearly) rather
    than inferred from start/end dates — makes price lookups unambiguous.
  - PaymentTransaction: deliberately append-only. Transactions are never
    updated — every Stripe event writes a new row. This gives a full audit log.
  - PaymentTransaction: `amount` is stored in the smallest currency unit
    (paise for INR, cents for USD) as an IntegerField, not DecimalField —
    avoids floating-point rounding errors in financial records. The `currency`
    field tells you how to display it.
  - All Stripe IDs are stored as CharField(max_length=255) to future-proof
    against Stripe changing their ID format.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# ─────────────────────────── Choices ────────────────────────────


class BillingCycleChoices(models.TextChoices):
    MONTHLY = 'monthly', 'Monthly'
    YEARLY = 'yearly', 'Yearly'


class SubscriptionStatusChoices(models.TextChoices):
    ACTIVE = 'active', 'Active'
    CANCELLED = 'cancelled', 'Cancelled'
    EXPIRED = 'expired', 'Expired'
    PAST_DUE = 'past_due', 'Past Due'
    TRIALING = 'trialing', 'Trialing'
    INCOMPLETE = 'incomplete', 'Incomplete'


class TransactionStatusChoices(models.TextChoices):
    SUCCEEDED = 'succeeded', 'Succeeded'
    FAILED = 'failed', 'Failed'
    PENDING = 'pending', 'Pending'
    REFUNDED = 'refunded', 'Refunded'
    DISPUTED = 'disputed', 'Disputed'


class CurrencyChoices(models.TextChoices):
    INR = 'INR', 'Indian Rupee'
    USD = 'USD', 'US Dollar'
    EUR = 'EUR', 'Euro'
    GBP = 'GBP', 'British Pound'


# ─────────────────────── Subscription Plan ───────────────────────


class SubscriptionPlan(models.Model):
    """
    Master list of available plans (e.g. Free, Monthly Premium, Yearly Premium).
    Plans are never deleted — only deactivated via `is_active = False`.
    Deleting a plan would break FK references on existing Subscription rows.

    `price_monthly` and `price_yearly` are stored in the smallest currency
    unit of the plan's base currency (paise if INR, cents if USD).
    Use the `display_price_*` properties for formatted output in templates.

    `stripe_price_id_monthly` / `stripe_price_id_yearly`: the Stripe Price
    object IDs used when creating Checkout Sessions. Kept here so the premium
    app can look them up without an extra API call.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True)
    price_monthly = models.PositiveIntegerField(
        help_text='Price in smallest currency unit (e.g. paise, cents). 0 for free plans.'
    )
    price_yearly = models.PositiveIntegerField(
        help_text='Price in smallest currency unit for a full year.'
    )
    currency = models.CharField(
        max_length=3,
        choices=CurrencyChoices.choices,
        default=CurrencyChoices.INR,
    )
    # Feature list shown on the pricing page: ['Unlimited problems', 'Mock interviews', ...]
    features = models.JSONField(
        default=list,
        help_text='List of feature strings shown on the pricing page.',
    )
    stripe_price_id_monthly = models.CharField(
        max_length=255,
        blank=True,
        help_text='Stripe Price ID for the monthly billing cycle.',
    )
    stripe_price_id_yearly = models.CharField(
        max_length=255,
        blank=True,
        help_text='Stripe Price ID for the yearly billing cycle.',
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text='Inactive plans are hidden from the pricing page but kept for historical FK integrity.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Subscription Plan'
        ordering = ['price_monthly']

    def clean(self):
        if self.price_yearly > self.price_monthly * 12:
            raise ValidationError(
                'Yearly price cannot be more expensive than 12× the monthly price. '
                'Yearly plans should offer a discount.'
            )

    @property
    def display_price_monthly(self) -> str:
        """Returns a human-readable price string, e.g. '₹499/mo'."""
        symbols = {'INR': '₹', 'USD': '$', 'EUR': '€', 'GBP': '£'}
        symbol = symbols.get(self.currency, self.currency)
        amount = self.price_monthly / 100
        return f"{symbol}{amount:,.0f}/mo"

    @property
    def display_price_yearly(self) -> str:
        symbols = {'INR': '₹', 'USD': '$', 'EUR': '€', 'GBP': '£'}
        symbol = symbols.get(self.currency, self.currency)
        amount = self.price_yearly / 100
        return f"{symbol}{amount:,.0f}/yr"

    @property
    def yearly_savings_percent(self) -> int:
        """Returns the % saved by choosing yearly over monthly × 12."""
        if self.price_monthly == 0:
            return 0
        monthly_total = self.price_monthly * 12
        savings = (monthly_total - self.price_yearly) / monthly_total * 100
        return max(0, int(savings))

    def __str__(self) -> str:
        return f"{self.name} | {self.display_price_monthly}"


# ─────────────────────── Subscription ───────────────────────────


class Subscription(models.Model):
    """
    One active subscription per user at any given time.
    When a user upgrades, the old subscription is set to 'cancelled'
    and a new row is written — never update the old row.

    `stripe_subscription_id` is unique — Stripe generates one per
    checkout, so there is a 1-to-1 mapping to this table's rows.

    `cancel_at_period_end`: mirrors the Stripe flag. When True, the
    subscription is still active but will not renew. The frontend shows
    a "Renews on / Cancels on" label based on this.
    """
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='subscriptions',
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,    # Never delete a plan that has subscriptions
        related_name='subscriptions',
    )
    billing_cycle = models.CharField(
        max_length=10,
        choices=BillingCycleChoices.choices,
        default=BillingCycleChoices.MONTHLY,
    )
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatusChoices.choices,
        default=SubscriptionStatusChoices.INCOMPLETE,
        db_index=True,
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='Stripe Subscription object ID (sub_xxxxx).',
    )
    stripe_customer_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text='Stripe Customer object ID (cus_xxxxx).',
    )
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text='True when the user has cancelled but the period has not expired yet.',
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Set when status transitions to cancelled.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Subscription'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'current_period_end']),
        ]

    def clean(self):
        if self.current_period_end and self.current_period_start:
            if self.current_period_end <= self.current_period_start:
                raise ValidationError('current_period_end must be after current_period_start.')

    @property
    def is_active(self) -> bool:
        """
        True only when status is active/trialing AND the period has not expired.
        Use this in templates and permission checks — not the raw `status` field.
        """
        active_statuses = {
            SubscriptionStatusChoices.ACTIVE,
            SubscriptionStatusChoices.TRIALING,
        }
        return (
            self.status in active_statuses
            and self.current_period_end > timezone.now()
        )

    @property
    def days_remaining(self) -> int:
        """Returns days left in the current billing period. 0 if expired."""
        if self.current_period_end < timezone.now():
            return 0
        return (self.current_period_end - timezone.now()).days

    def cancel(self):
        """
        Soft-cancel: marks cancel_at_period_end and sets cancelled_at.
        The subscription remains active until current_period_end.
        Call Stripe's API before calling this.
        """
        self.cancel_at_period_end = True
        self.cancelled_at = timezone.now()
        self.save(update_fields=['cancel_at_period_end', 'cancelled_at', 'updated_at'])

    def __str__(self) -> str:
        return (
            f"{self.user.user_name} | {self.plan.name} | "
            f"{self.billing_cycle} | {self.status}"
        )


# ─────────────────── Payment Transaction ─────────────────────────


class PaymentTransaction(models.Model):
    """
    Append-only ledger of every Stripe payment event.
    One row per Stripe PaymentIntent / Invoice event.
    Never update existing rows — each Stripe webhook event writes a new one.

    `amount` is stored in the smallest currency unit (paise / cents) as a
    PositiveIntegerField. Do not use DecimalField for money — floating-point
    representation errors will cause accounting bugs.

    `stripe_payment_intent_id` maps 1-to-1 with a Stripe PaymentIntent.
    `stripe_invoice_id` is set for subscription renewals (Stripe invoices
    are distinct from one-time PaymentIntents).
    """
    user = models.ForeignKey(
        'users.Users',
        on_delete=models.CASCADE,
        related_name='payment_transactions',
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='transactions',
        null=True,
        blank=True,
        help_text='Null for one-off charges not tied to a subscription.',
    )
    amount = models.PositiveIntegerField(
        help_text='Amount in smallest currency unit (paise, cents). Never store floats for money.'
    )
    currency = models.CharField(
        max_length=3,
        choices=CurrencyChoices.choices,
        default=CurrencyChoices.INR,
    )
    status = models.CharField(
        max_length=20,
        choices=TransactionStatusChoices.choices,
        default=TransactionStatusChoices.PENDING,
        db_index=True,
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text='Stripe PaymentIntent ID (pi_xxxxx).',
    )
    stripe_invoice_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text='Stripe Invoice ID (in_xxxxx). Set for subscription renewal payments.',
    )
    failure_reason = models.TextField(
        blank=True,
        help_text='Populated from Stripe on failed charges. Empty on success.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Payment Transaction'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['subscription', 'created_at']),
        ]

    @property
    def display_amount(self) -> str:
        """Returns a human-readable amount string, e.g. '₹499.00'."""
        symbols = {'INR': '₹', 'USD': '$', 'EUR': '€', 'GBP': '£'}
        symbol = symbols.get(self.currency, self.currency)
        return f"{symbol}{self.amount / 100:,.2f}"

    def __str__(self) -> str:
        return (
            f"{self.user.user_name} | {self.display_amount} | "
            f"{self.status} | {self.stripe_payment_intent_id}"
        )