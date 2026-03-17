from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'status', 'created_at']
    list_filter = ['status', 'rating']
    list_editable = ['status']
    search_fields = ['product__name', 'user__username', 'body']
