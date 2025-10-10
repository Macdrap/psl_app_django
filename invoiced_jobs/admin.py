from django.contrib import admin
from .models import InvoicedJob


@admin.register(InvoicedJob)
class InvoicedJobAdmin(admin.ModelAdmin):
    list_display = [
        'get_job_number',
        'get_client',
        'get_description_preview',  # NEW: Show description preview
        'date',
        'psl_value',
        'contractor_value',
        'status',
        'created_by',
        'created_at'
    ]

    list_filter = [
        'status',
        'date',
        'created_at',
        'created_by',
        ('description', admin.EmptyFieldListFilter),  # NEW: Filter by has/no description
    ]

    search_fields = [
        'award__job_number',
        'award__client',
        'award__location',
        'description',  # NEW: Search by description
    ]

    readonly_fields = [
        'psl_value',
        'created_by',
        'created_at',
        'updated_at'
    ]

    list_per_page = 25

    date_hierarchy = 'date'

    fieldsets = (
        ('Linked Award', {
            'fields': ('award',)
        }),
        ('Invoice Information', {
            'fields': ('date', 'status', 'description')  # NEW: Added description
        }),
        ('Value Breakdown', {
            'fields': ('utility_value', 'cad_value',
                       'topo_value', 'contractor_value', 'psl_value')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_job_number(self, obj):
        return obj.award.job_number if obj.award else 'N/A'

    get_job_number.short_description = 'Job Number'
    get_job_number.admin_order_field = 'award__job_number'

    def get_client(self, obj):
        return obj.award.client if obj.award else 'N/A'

    get_client.short_description = 'Client'
    get_client.admin_order_field = 'award__client'

    def get_description_preview(self, obj):
        """Show first 50 characters of description"""
        if obj.description:
            if len(obj.description) > 50:
                return f"{obj.description[:50]}..."
            return obj.description
        return "-"

    get_description_preview.short_description = 'Description'

    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user if creating new job"""
        if not change:  # Only set during creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)