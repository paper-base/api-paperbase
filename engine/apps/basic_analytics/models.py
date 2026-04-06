from django.db import models

from engine.apps.stores.models import Store


class StoreDashboardStatsSnapshot(models.Model):
    """
    Cached snapshot for the home dashboard stats overview endpoint.

    Kept separate from premium analytics so basic plan holders can use the same
    home cards/charts.
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
    bucket = models.CharField(
        max_length=10, choices=BUCKET_CHOICES, default=BUCKET_DAY, db_index=True
    )

    # Response payload: { summary, series, meta }
    payload = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_storedashboardstatssnapshot"
        constraints = [
            models.UniqueConstraint(
                fields=["store", "start_date", "end_date", "bucket"],
                name="uniq_dashboardstatsnapshot_store_range_bucket",
            )
        ]
