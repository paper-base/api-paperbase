from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from engine.core.ids import generate_public_id


class ActiveDomainManager(models.Manager):
    """Domains that are not soft-deleted (default for app code)."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class Store(models.Model):
    """Tenant store for the BaaS platform. Includes branding for dashboard and storefront."""

    public_id = models.CharField(
        max_length=32, unique=True, db_index=True, editable=False,
        help_text="Non-sequential public identifier used in APIs and URLs (e.g. str_xxx).",
    )
    name = models.CharField(max_length=255)
    store_type = models.CharField(
        max_length=60,
        blank=True,
        help_text="Store type/category (e.g. Fashion, Retail, E-commerce). Max 4 words.",
    )
    domain = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Full domain or host used to route requests to this store. Set via Settings > Networking.",
    )
    is_active = models.BooleanField(default=True)
    # Owner info (always stored with the store)
    owner_name = models.CharField(
        max_length=255,
        help_text="Full name of the store owner.",
    )
    owner_email = models.EmailField(
        help_text="Email address of the store owner.",
    )
    # Branding (dashboard sidebar, storefront, invoices)
    logo = models.ImageField(upload_to="stores/logos/", blank=True, null=True)
    currency = models.CharField(max_length=8, default="BDT")
    currency_symbol = models.CharField(max_length=10, default="৳", blank=True)
    # Store info (for storefront, invoices, emails)
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["domain"]),
            models.Index(fields=["is_active", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id("store")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        from .services import store_primary_domain_host

        host = store_primary_domain_host(self)
        return f"{self.name}" + (f" ({host})" if host else "")


class Domain(models.Model):
    """
    HTTP/WebSocket tenant hostname for a store.

    Each store has exactly one generated subdomain (is_custom=False) and at most one
    custom domain (is_custom=True). Routing uses verified domains only.
    """

    objects = ActiveDomainManager()
    all_objects = models.Manager()

    public_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        help_text="External identifier (e.g. dom_xxx).",
    )
    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="domains",
    )
    domain = models.CharField(max_length=255)
    is_custom = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=64, null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["domain"],
                condition=models.Q(is_deleted=False),
                name="domain_unique_when_active",
            ),
            models.UniqueConstraint(
                fields=["store"],
                condition=models.Q(is_custom=True) & models.Q(is_deleted=False),
                name="one_custom_domain_per_store",
            ),
            models.UniqueConstraint(
                fields=["store"],
                condition=models.Q(is_custom=False) & models.Q(is_deleted=False),
                name="one_generated_domain_per_store",
            ),
            models.UniqueConstraint(
                fields=["store"],
                condition=models.Q(is_primary=True) & models.Q(is_deleted=False),
                name="one_primary_domain_per_store",
            ),
        ]
        indexes = [
            models.Index(fields=["domain"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id("domain")
        from .services import normalize_domain_host

        if self.domain:
            self.domain = normalize_domain_host(self.domain)
        if self.pk:
            prior = (
                Domain.all_objects.filter(pk=self.pk)
                .only("domain", "is_custom")
                .first()
            )
            if prior and not prior.is_custom:
                prior_norm = normalize_domain_host(prior.domain)
                if prior_norm != self.domain:
                    raise ValidationError("Generated store subdomain cannot be changed.")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.domain


class StoreSettings(models.Model):
    """Per-store configuration and feature flags."""

    store = models.OneToOneField(
        Store,
        on_delete=models.CASCADE,
        related_name="settings",
    )
    modules_enabled = models.JSONField(
        default=dict,
        blank=True,
        help_text="Feature/module flags for this store (e.g. products, orders, reviews).",
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Default low-stock alert threshold for inventory.",
    )
    extra_field_schema = models.JSONField(
        blank=True,
        default=list,
        help_text="Extra field definitions for product, customer, order: [{id, entityType, name, fieldType, required, order, options}]",
    )
    email_notify_owner_on_order_received = models.BooleanField(
        default=False,
        help_text="Premium: send email to store when a new order is placed.",
    )
    email_customer_on_order_confirmed = models.BooleanField(
        default=False,
        help_text="Premium: email customer when order is confirmed (send-to-courier).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Store settings"

    def __str__(self) -> str:
        return f"Settings for {self.store}"


class StoreMembership(models.Model):
    """Association between a user and a store, with a role."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"

    public_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Non-sequential public identifier used in APIs and URLs (e.g. mbr_xxx).",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="store_memberships",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "store"],
                name="uniq_store_membership_user_store",
            ),
        ]
        indexes = [
            models.Index(fields=["store", "role"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id("mbr")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user} @ {self.store} ({self.get_role_display()})"


class StoreDeletionJob(models.Model):
    """
    Track irreversible store deletion progress for the initiating user.

    IMPORTANT: this model intentionally stores store identifiers as snapshots
    (instead of FKs) so the job remains queryable even after the store is hard-deleted.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    public_id = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        editable=False,
        help_text="Non-sequential public identifier (e.g. dlj_xxx).",
    )

    # Step strings returned to the frontend (kept stable for UI).
    STEP_REMOVING_ORDERS = "Removing orders..."
    STEP_CLEARING_CUSTOMERS = "Clearing customer data..."
    STEP_DELETING_PRODUCTS = "Deleting products..."
    STEP_DELETING_ANALYTICS = "Deleting analytics..."
    STEP_FINALIZING = "Finalizing..."

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="store_deletion_jobs",
    )

    store_public_id_snapshot = models.CharField(
        max_length=32,
        db_index=True,
        help_text="Store public_id snapshot taken at deletion request time.",
    )
    store_id_snapshot = models.BigIntegerField(
        db_index=True,
        help_text="Store primary key snapshot taken at deletion request time.",
    )

    celery_task_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    current_step = models.CharField(max_length=120, blank=True, default="")

    redirect_route = models.CharField(
        max_length=64,
        default="/onboarding",
        help_text="Frontend route to redirect after deletion is finalized.",
    )
    next_store_public_id = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        help_text="Optional next active store public_id for the issuing JWTs.",
    )
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id("storedeletionjob")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"StoreDeletionJob({self.store_public_id_snapshot})[{self.status}]"

