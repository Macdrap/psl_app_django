from django.contrib import admin
from .models import MonthlyAward


@admin.register(MonthlyAward)
class MonthlyAwardAdmin(admin.ModelAdmin):
    list_display = [
        'job_number',
        'date',
        'get_client_name',
        'get_contact_name',
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
        'client__name',
        'client__contact__name',
        'client__contact__email',
        'client__contact__phone',
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
        ('Client', {
            'fields': ('client',)
        }),
        ('Location', {
            'fields': ('location',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_client_name(self, obj):
        return obj.client.name if obj.client else '-'
    get_client_name.short_description = 'Company'
    get_client_name.admin_order_field = 'client__name'

    def get_contact_name(self, obj):
        return obj.client.contact.name if obj.client else '-'
    get_contact_name.short_description = 'Contact'
    get_contact_name.admin_order_field = 'client__contact__name'

    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user if creating new award"""
        if not change:  # Only set during creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
