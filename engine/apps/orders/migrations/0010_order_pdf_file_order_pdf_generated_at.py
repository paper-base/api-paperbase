import engine.core.media_upload_paths
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_alter_order_order_number_alter_order_unique_together'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE orders_order ADD COLUMN IF NOT EXISTS pdf_file VARCHAR(100) NULL;
                        ALTER TABLE orders_order ADD COLUMN IF NOT EXISTS pdf_generated_at TIMESTAMP WITH TIME ZONE NULL;
                    """,
                    reverse_sql="""
                        ALTER TABLE orders_order DROP COLUMN IF EXISTS pdf_file;
                        ALTER TABLE orders_order DROP COLUMN IF EXISTS pdf_generated_at;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='order',
                    name='pdf_file',
                    field=models.FileField(blank=True, null=True, upload_to=engine.core.media_upload_paths.tenant_order_invoice_upload_to),
                ),
                migrations.AddField(
                    model_name='order',
                    name='pdf_generated_at',
                    field=models.DateTimeField(blank=True, null=True),
                ),
            ],
        ),
    ]