# File Tree: api-paperbase

**Generated:** 4/26/2026, 2:19:45 PM
**Root Path:** `/home/mahi/Projects/personal/paperbase/api-paperbase`

```
├── 📁 .github
│   └── 📁 workflows
│       └── ⚙️ deploy.yml
├── 📁 backup
│   ├── 📄 backup-base.sh
│   └── 📄 lib.sh
├── 📁 config
│   ├── 📁 settings
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 base.py
│   │   ├── 🐍 development.py
│   │   ├── 🐍 production.py
│   │   └── 🐍 runtime.py
│   ├── 🐍 __init__.py
│   ├── 🐍 admin_api.py
│   ├── 🐍 admin_notifications_summary.py
│   ├── 🐍 admin_urls.py
│   ├── 🐍 asgi.py
│   ├── 🐍 celery.py
│   ├── 🐍 health_views.py
│   ├── 🐍 inngest.py
│   ├── 🐍 inngest_functions.py
│   ├── 🐍 permissions.py
│   ├── 🐍 qstash_views.py
│   ├── 🐍 urls.py
│   └── 🐍 wsgi.py
├── 📁 docs
│   ├── 📝 backup-restore.md
│   └── 📝 rules.md
├── 📁 engine
│   ├── 📁 apps
│   │   ├── 📁 accounts
│   │   │   ├── 📁 management
│   │   │   │   └── 📁 commands
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 avatar_url.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 services.py
│   │   │   ├── 🐍 throttles.py
│   │   │   ├── 🐍 turnstile.py
│   │   │   ├── 🐍 two_factor_service.py
│   │   │   ├── 🐍 urls.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 backup
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 prune.py
│   │   │   └── 🐍 tasks.py
│   │   ├── 📁 banners
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 admin_serializers.py
│   │   │   ├── 🐍 admin_views.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 services.py
│   │   │   ├── 🐍 urls.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 basic_analytics
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 models.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 billing
│   │   │   ├── 📁 management
│   │   │   │   └── 📁 commands
│   │   │   │       └── 🐍 seed_plans.py
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   ├── 🐍 0002_alter_plan_is_default.py
│   │   │   │   ├── 🐍 0003_payment_pending_status_and_plan_fk.py
│   │   │   │   ├── 🐍 0004_alter_subscription_status.py
│   │   │   │   ├── 🐍 0005_remove_payment_providers_stripe_paddle_sslcommerz.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 feature_gate.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 pricing.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 services.py
│   │   │   ├── 🐍 subscription_status.py
│   │   │   ├── 🐍 urls.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 blogs
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   ├── 🐍 0002_remove_blog_status_and_scheduled_at.py
│   │   │   │   ├── 🐍 0003_remove_blog_category_model.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 admin_serializers.py
│   │   │   ├── 🐍 admin_views.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 services.py
│   │   │   ├── 🐍 urls.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 couriers
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 📁 services
│   │   │   │   ├── 🐍 __init__.py
│   │   │   │   └── 🐍 steadfast_service.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin_views.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 models.py
│   │   │   └── 🐍 serializers.py
│   │   ├── 📁 customers
│   │   │   ├── 📁 management
│   │   │   │   └── 📁 commands
│   │   │   │       └── 🐍 rebuild_customer_total_spent.py
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   ├── 🐍 0002_customer_minimal_schema.py
│   │   │   │   ├── 🐍 0003_customer_denormalized_metrics.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 📁 services
│   │   │   │   ├── 🐍 __init__.py
│   │   │   │   ├── 🐍 consistency_check.py
│   │   │   │   └── 🐍 purchase_service.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 admin_serializers.py
│   │   │   ├── 🐍 admin_views.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 signals.py
│   │   │   ├── 🐍 urls.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 emails
│   │   │   ├── 📁 management
│   │   │   │   ├── 📁 commands
│   │   │   │   │   ├── 🐍 __init__.py
│   │   │   │   │   └── 🐍 seed_email_templates.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   ├── 🐍 0002_emaillog_store.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 📁 providers
│   │   │   │   ├── 🐍 __init__.py
│   │   │   │   ├── 🐍 base.py
│   │   │   │   ├── 🐍 django_mail.py
│   │   │   │   └── 🐍 resend.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 constants.py
│   │   │   ├── 🐍 exceptions.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 router.py
│   │   │   ├── 🐍 services.py
│   │   │   ├── 🐍 tasks.py
│   │   │   ├── 🐍 template_catalog.py
│   │   │   └── 🐍 triggers.py
│   │   ├── 📁 fraud_check
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   ├── 🐍 0002_rename_fraud_check_store_norm_phone_idx_fraud_check_store_i_9d7b97_idx.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 services.py
│   │   │   ├── 🐍 urls.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 inventory
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 admin_serializers.py
│   │   │   ├── 🐍 admin_views.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 cache_sync.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 services.py
│   │   │   ├── 🐍 tasks.py
│   │   │   ├── 🐍 utils.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 marketing_integrations
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   ├── 🐍 0002_update_event_settings_flags.py
│   │   │   │   ├── 🐍 0003_hard_meta_standard_events.py
│   │   │   │   ├── 🐍 0004_store_event_log.py
│   │   │   │   ├── 🐍 0005_rename_marketing_in_store_i_7d1a11_marketing_i_store_i_3c7fcc_idx_and_more.py
│   │   │   │   ├── 🐍 0006_integrationeventsettings_track_add_to_cart.py
│   │   │   │   ├── 🐍 0007_remove_track_search.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 📁 services
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 admin_views.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 models.py
│   │   │   └── 🐍 serializers.py
│   │   ├── 📁 notifications
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 admin_serializers.py
│   │   │   ├── 🐍 admin_views.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 services.py
│   │   │   ├── 🐍 system_urls.py
│   │   │   ├── 🐍 system_views.py
│   │   │   ├── 🐍 urls.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 orders
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   ├── 🐍 0002_order_flag.py
│   │   │   │   ├── 🐍 0003_order_payment_fields.py
│   │   │   │   ├── 🐍 0004_orderexportjob.py
│   │   │   │   ├── 🐍 0005_rename_ordexp_store_status_orders_orde_store_i_5f7c90_idx_and_more.py
│   │   │   │   ├── 🐍 0006_order_composite_indexes.py
│   │   │   │   ├── 🐍 0007_order_index_consolidation.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 admin_serializers.py
│   │   │   ├── 🐍 admin_views.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 courier_dispatch.py
│   │   │   ├── 🐍 export_cleanup.py
│   │   │   ├── 🐍 export_csv_format.py
│   │   │   ├── 🐍 export_queryset.py
│   │   │   ├── 🐍 export_tasks.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 order_export_views.py
│   │   │   ├── 🐍 order_financials.py
│   │   │   ├── 🐍 order_summary_formatting.py
│   │   │   ├── 🐍 pricing.py
│   │   │   ├── 🐍 pricing_breakdown_views.py
│   │   │   ├── 🐍 pricing_preview_views.py
│   │   │   ├── 🐍 pricing_urls.py
│   │   │   ├── 🐍 purchase_ledger_service.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 services.py
│   │   │   ├── 🐍 signals.py
│   │   │   ├── 🐍 stock.py
│   │   │   ├── 🐍 tasks.py
│   │   │   ├── 🐍 throttles.py
│   │   │   ├── 🐍 urls.py
│   │   │   ├── 🐍 utils.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 products
│   │   │   ├── 📁 management
│   │   │   │   ├── 📁 commands
│   │   │   │   │   ├── 🐍 __init__.py
│   │   │   │   │   ├── 🐍 seed_apparel_demo.py
│   │   │   │   │   └── 🐍 seed_products.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   ├── 🐍 0002_product_display_order.py
│   │   │   │   ├── 🐍 0003_alter_product_options.py
│   │   │   │   ├── 🐍 0004_product_prepayment_type.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 admin_forms.py
│   │   │   ├── 🐍 admin_serializers.py
│   │   │   ├── 🐍 admin_views.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 catalog_urls.py
│   │   │   ├── 🐍 category_tree.py
│   │   │   ├── 🐍 constants.py
│   │   │   ├── 🐍 extra_schema.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 product_search.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 services.py
│   │   │   ├── 🐍 signals.py
│   │   │   ├── 🐍 sku_generation.py
│   │   │   ├── 🐍 stock_signals.py
│   │   │   ├── 🐍 stock_sync.py
│   │   │   ├── 🐍 urls.py
│   │   │   ├── 🐍 variant_utils.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 shipping
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 admin_serializers.py
│   │   │   ├── 🐍 admin_views.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 service.py
│   │   │   ├── 🐍 urls.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 stores
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   ├── 🐍 0002_add_started_at_and_already_missing_action.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 network_urls.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 services.py
│   │   │   ├── 🐍 signals.py
│   │   │   ├── 🐍 social_links.py
│   │   │   ├── 🐍 store_activity.py
│   │   │   ├── 🐍 storefront_urls.py
│   │   │   ├── 🐍 storefront_views.py
│   │   │   ├── 🐍 tasks.py
│   │   │   ├── 🐍 urls.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 support
│   │   │   ├── 📁 migrations
│   │   │   │   ├── 🐍 0001_initial.py
│   │   │   │   └── 🐍 __init__.py
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 admin.py
│   │   │   ├── 🐍 admin_serializers.py
│   │   │   ├── 🐍 admin_views.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 models.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 signals.py
│   │   │   ├── 🐍 urls.py
│   │   │   └── 🐍 views.py
│   │   ├── 📁 tracking
│   │   │   ├── 📁 static
│   │   │   │   └── 📄 tracker.js
│   │   │   ├── 📝 VERIFYING.md
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 apps.py
│   │   │   ├── 🐍 capi_payload.py
│   │   │   ├── 🐍 contract.py
│   │   │   ├── 🐍 ip.py
│   │   │   ├── 🐍 serializers.py
│   │   │   ├── 🐍 tasks.py
│   │   │   ├── 🐍 throttles.py
│   │   │   ├── 🐍 urls.py
│   │   │   └── 🐍 views.py
│   │   └── 🐍 __init__.py
│   ├── 📁 core
│   │   ├── 📁 admin
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 filters.py
│   │   │   └── 🐍 mixins.py
│   │   ├── 📁 authz
│   │   │   └── 🐍 __init__.py
│   │   ├── 📁 middleware
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 internal_override_middleware.py
│   │   │   ├── 🐍 request_scoped_cache_middleware.py
│   │   │   ├── 🐍 subscription_enforcement_middleware.py
│   │   │   └── 🐍 tenant_context_middleware.py
│   │   ├── 📁 migrations
│   │   │   ├── 🐍 0001_initial.py
│   │   │   └── 🐍 __init__.py
│   │   ├── 📁 safety
│   │   │   ├── 🐍 __init__.py
│   │   │   └── 🐍 tenant_safety.py
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 activity.py
│   │   ├── 🐍 admin_dashboard_cache.py
│   │   ├── 🐍 admin_notifications_cache.py
│   │   ├── 🐍 admin_serializers.py
│   │   ├── 🐍 admin_trash_views.py
│   │   ├── 🐍 admin_views.py
│   │   ├── 🐍 apps.py
│   │   ├── 🐍 authentication.py
│   │   ├── 🐍 cache_service.py
│   │   ├── 🐍 client_ip.py
│   │   ├── 🐍 consumers.py
│   │   ├── 🐍 encryption.py
│   │   ├── 🐍 ids.py
│   │   ├── 🐍 media_deletion_service.py
│   │   ├── 🐍 media_upload_paths.py
│   │   ├── 🐍 media_urls.py
│   │   ├── 🐍 migration_safety.py
│   │   ├── 🐍 models.py
│   │   ├── 🐍 pagination.py
│   │   ├── 🐍 permissions.py
│   │   ├── 🐍 query_params.py
│   │   ├── 🐍 rate_limit.py
│   │   ├── 🐍 rate_limit_service.py
│   │   ├── 🐍 realtime.py
│   │   ├── 🐍 redis_fixed_window.py
│   │   ├── 🐍 request_context.py
│   │   ├── 🐍 routing.py
│   │   ├── 🐍 search_serializers.py
│   │   ├── 🐍 search_services.py
│   │   ├── 🐍 search_views.py
│   │   ├── 🐍 serializers.py
│   │   ├── 🐍 store_api_key_auth.py
│   │   ├── 🐍 storefront_search_views.py
│   │   ├── 🐍 tasks.py
│   │   ├── 🐍 tenancy.py
│   │   ├── 🐍 tenant_context.py
│   │   ├── 🐍 tenant_drf.py
│   │   ├── 🐍 tenant_execution.py
│   │   ├── 🐍 tenant_guard.py
│   │   ├── 🐍 tenant_queryset.py
│   │   ├── 🐍 trash_service.py
│   │   ├── 🐍 utils.py
│   │   └── 🐍 ws_api_key.py
│   ├── 📁 utils
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 bd_query.py
│   │   └── 🐍 time.py
│   └── 🐍 __init__.py
├── 📁 scripts
│   └── 📄 restore.sh
├── 📁 seeds
│   ├── 📁 products
│   │   ├── ⚙️ seed_apparel_demo.json
│   │   └── ⚙️ seed_products.json
│   └── 📝 README.md
├── 📁 tests
│   ├── 📁 apps
│   │   ├── 📁 accounts
│   │   │   ├── 🐍 __init__.py
│   │   │   └── 🐍 test_2fa.py
│   │   ├── 📁 backup
│   │   │   └── 🐍 test_prune.py
│   │   ├── 📁 banners
│   │   │   └── 🐍 __init__.py
│   │   ├── 📁 basic_analytics
│   │   │   └── 🐍 test_admin_basic_analytics_tenant_required.py
│   │   ├── 📁 billing
│   │   │   ├── 🐍 __init__.py
│   │   │   └── 🐍 test_billing.py
│   │   ├── 📁 couriers
│   │   │   ├── 🐍 __init__.py
│   │   │   └── 🐍 test_steadfast_service.py
│   │   ├── 📁 customers
│   │   ├── 📁 emails
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 test_email_log.py
│   │   │   ├── 🐍 test_email_router.py
│   │   │   ├── 🐍 test_send_order_email_task.py
│   │   │   └── 🐍 test_triggers.py
│   │   ├── 📁 fraud_check
│   │   │   └── 🐍 test_fraud_check.py
│   │   ├── 📁 notifications
│   │   │   └── 🐍 test_system_notifications.py
│   │   ├── 📁 orders
│   │   │   ├── 🐍 test_admin_courier_dispatch.py
│   │   │   ├── 🐍 test_admin_orders_list_filters.py
│   │   │   ├── 🐍 test_confirmed_purchases.py
│   │   │   ├── 🐍 test_export_csv_format.py
│   │   │   ├── 🐍 test_order_export_api.py
│   │   │   ├── 🐍 test_order_item_snapshots.py
│   │   │   ├── 🐍 test_order_summary_formatting.py
│   │   │   ├── 🐍 test_prepayment_flow.py
│   │   │   └── 🐍 test_purchase_ledger.py
│   │   ├── 📁 products
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 test_admin_product_image_remove.py
│   │   │   ├── 🐍 test_inactive_variant_enforcement.py
│   │   │   ├── 🐍 test_inventory_auto_creation.py
│   │   │   ├── 🐍 test_product_attribute_slug.py
│   │   │   ├── 🐍 test_product_plan_limits.py
│   │   │   ├── 🐍 test_product_reorder.py
│   │   │   ├── 🐍 test_sku_hardening.py
│   │   │   └── 🐍 test_storefront_completeness.py
│   │   ├── 📁 reviews
│   │   ├── 📁 stores
│   │   │   ├── 🐍 __init__.py
│   │   │   ├── 🐍 test_api_keys.py
│   │   │   └── 🐍 test_stores.py
│   │   ├── 📁 tracking
│   │   │   ├── 🐍 __init__.py
│   │   │   └── 🐍 test_tracking_ingest.py
│   │   └── 🐍 __init__.py
│   ├── 📁 core
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 test_core.py
│   │   ├── 🐍 test_rate_limit_day2.py
│   │   └── 🐍 test_trash.py
│   ├── 📁 security
│   │   ├── 🐍 test_access_control_strict.py
│   │   ├── 🐍 test_tenant_hardening.py
│   │   └── 🐍 test_tenant_zero_trust.py
│   ├── 📁 seeds
│   │   └── ⚙️ .gitkeep
│   ├── 📁 test_helpers
│   │   ├── 🐍 __init__.py
│   │   └── 🐍 jwt_auth.py
│   └── 🐍 __init__.py
├── ⚙️ .dockerignore
├── ⚙️ .env.example
├── ⚙️ .gitignore
├── 🐳 Dockerfile
├── 📝 README.md
├── ⚙️ docker-compose.yml
├── 📄 entrypoint.sh
├── 🐍 gunicorn.conf.py
├── 🐍 manage.py
├── ⚙️ pytest.ini
└── 📄 requirements.txt
```

---
*Generated by FileTree Pro Extension*