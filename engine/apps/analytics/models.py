from decimal import Decimal

from django.db import models

from engine.apps.stores.models import Store
from engine.core.ids import generate_public_id


class StoreAnalytics(models.Model):
    """Daily aggregated store metrics for reporting."""

    public_id = models.CharField(
        max_length=32, unique=True, db_index=True, editable=False,
        help_text="Non-sequential public identifier (e.g. anl_xxx).",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="analytics",
    )
    period_date = models.DateField(db_index=True)
    orders_count = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    cart_items_count = models.PositiveIntegerField(default=0)
    wishlist_items_count = models.PositiveIntegerField(default=0)
    page_views = models.PositiveIntegerField(default=0, null=True, blank=True)
    conversion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name_plural = "Store analytics"
        constraints = [
            models.UniqueConstraint(
                fields=["store", "period_date"],
                name="uniq_storeanalytics_store_period",
            )
        ]
        ordering = ["-period_date"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_public_id("analytics")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.store} - {self.period_date}"


class StoreDashboardStatsSnapshot(models.Model):
    """
    Cached snapshot for the home dashboard "stats overview" endpoint.

    This is intentionally separate from premium "advanced analytics" so that
    basic plan holders can view the same home cards/charts.
    """

    BUCKET_DAY = "day"
    BUCKET_WEEK = "week"
    BUCKET_MONTH = "month"

    BUCKET_CHOICES = (
        (BUCKET_DAY, "day"),
        (BUCKET_WEEK, "week"),
        (BUCKET_MONTH, "month"),
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="dashboard_stats_snapshots",
    )
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    bucket = models.CharField(max_length=10, choices=BUCKET_CHOICES, default=BUCKET_DAY, db_index=True)

    # Response payload: { summary, series, meta }
    payload = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["store", "start_date", "end_date", "bucket"],
                name="uniq_dashboardstatsnapshot_store_range_bucket",
            )
        ]
