from django.contrib import admin

from .models import SupportTicket, SupportTicketAttachment


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ["id", "store", "subject", "name", "email", "status", "priority", "created_at"]
    list_filter = ["status", "priority", "category", "created_at"]
    search_fields = ["subject", "name", "email", "phone", "order_number", "message"]
    readonly_fields = ["created_at", "updated_at"]
    autocomplete_fields = ["store"]

    def has_add_permission(self, request):
        return False

@admin.register(SupportTicketAttachment)
class SupportTicketAttachmentAdmin(admin.ModelAdmin):
    list_display = ["id", "ticket", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["ticket__id"]
    autocomplete_fields = ["ticket"]
