from django.contrib import admin

from .models import Notification, SystemNotification


@admin.register(SystemNotification)
class SystemNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'message_type', 'user', 'is_read', 'created_at']
    list_filter = ['message_type', 'is_read']
    list_editable = ['is_read']
    readonly_fields = ['created_at']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['text', 'notification_type', 'is_active', 'order', 'start_date', 'end_date', 'created_at']
    list_filter = ['notification_type', 'is_active', 'created_at']
    search_fields = ['text']
    fieldsets = (
        ('Content', {
            'fields': ('text', 'notification_type', 'is_active', 'order')
        }),
        ('Link (Optional)', {
            'fields': ('link', 'link_text'),
            'classes': ('collapse',)
        }),
        ('Scheduling (Optional)', {
            'fields': ('start_date', 'end_date'),
            'classes': ('collapse',)
        }),
    )
