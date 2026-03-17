from django.contrib import admin
from .models import PaymentMethod, Payment, Transaction


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'method_type', 'is_active', 'order']
    list_editable = ['is_active', 'order']


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    readonly_fields = ['transaction_reference', 'status', 'created_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'payment_method', 'amount', 'currency', 'status', 'created_at']
    list_filter = ['status']
    inlines = [TransactionInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'payment', 'transaction_reference', 'status', 'created_at']
    list_filter = ['status']
