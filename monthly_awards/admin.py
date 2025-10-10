from django.contrib import admin
from .models import MonthlyAward


@admin.register(MonthlyAward)
class MonthlyAwardAdmin(admin.ModelAdmin):
    list_display = [
        'job_number',
        'date',
        'client',
        'client_contact',
        'value',
        'sale',
        'created_by',
        'created_at'
    ]

    list_filter = [
        'date',
        'created_at',
        'created_by'
    ]

    search_fields = [
        'job_number',
        'client',
        'client_contact',
        'email',
        'phone',
        'location'
    ]

    readonly_fields = [
        'created_by',
        'created_at',
        'updated_at'
    ]

    list_per_page = 25

    date_hierarchy = 'date'

    fieldsets = (
        ('Link to Sales Enquiry', {
            'fields': ('sale',),
            'description': 'Optional: Link this award to an existing sales enquiry'
        }),
        ('Award Information', {
            'fields': ('job_number', 'date', 'value')
        }),
        ('Company Details', {
            'fields': ('client', 'client_contact', 'email', 'phone')
        }),
        ('Location', {
            'fields': ('location',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user if creating new award"""
        if not change:  # Only set during creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)