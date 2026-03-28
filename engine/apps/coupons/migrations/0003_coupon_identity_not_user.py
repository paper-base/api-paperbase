# Coupon usage keyed by guest identity (phone / email / session), not User.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0002_promotion_models"),
    ]

    operations = [
        migrations.RenameField(
            model_name="coupon",
            old_name="per_user_max_uses",
            new_name="per_identity_max_uses",
        ),
        migrations.AlterField(
            model_name="coupon",
            name="per_identity_max_uses",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text=(
                    "Max successful usages per customer identity within this store. "
                    "Identity is resolved as: phone (digits) > email (normalized) > store_session_id."
                ),
            ),
        ),
        migrations.AddField(
            model_name="couponusage",
            name="store_session_id",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
        migrations.RemoveField(
            model_name="couponusage",
            name="user",
        ),
    ]
