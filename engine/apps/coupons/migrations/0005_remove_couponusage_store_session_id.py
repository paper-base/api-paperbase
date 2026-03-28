from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("coupons", "0004_alter_coupon_per_identity_max_uses"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="couponusage",
            name="store_session_id",
        ),
    ]
