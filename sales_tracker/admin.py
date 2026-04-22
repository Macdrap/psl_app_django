from django.contrib import admin
from .models import SalesEnquiry


@admin.register(SalesEnquiry)
class SalesEnquiryAdmin(admin.ModelAdmin):
    list_display = [
        'job_number',
        'date',
        'get_client_name',
        'get_contact_name',
        'value',
        'note',
        'feedback',
        'other_feedback',
        'status',
        'created_by',
        'created_at'
    ]

    list_filter = [
        'status',
        'date',
        'created_at',
        'created_by'
    ]

    search_fields = [
        'job_number',
        'client__name',
        'contact__name',
        'contact__email',
        'contact__phone',
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
        ('Job Information', {
            'fields': ('job_number', 'date', 'value', 'status')
        }),
        ('Client', {
            'fields': ('client', 'contact')
        }),
        ('Location', {
            'fields': ('location',)
        }),
        ('Optional', {
            'fields': ('note', 'feedback', 'other_feedback')
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
        return obj.contact.name if obj.contact else '-'
    get_contact_name.short_description = 'Contact'
    get_contact_name.admin_order_field = 'contact__name'

    def save_model(self, request, obj, form, change):
        """Automatically set created_by to current user if creating new enquiry"""
        if not change:  # Only set during creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # Optional: Add custom actions
    actions = ['mark_as_awarded', 'mark_as_rejected', 'mark_as_pending']

    @admin.action(description='Mark selected enquiries as Awarded')
    def mark_as_awarded(self, request, queryset):
        updated = queryset.update(status='Awarded')
        self.message_user(request, f'{updated} enquiry(ies) marked as Awarded.')

    @admin.action(description='Mark selected enquiries as Rejected')
    def mark_as_rejected(self, request, queryset):
        updated = queryset.update(status='Rejected')
        self.message_user(request, f'{updated} enquiry(ies) marked as Rejected.')

    @admin.action(description='Mark selected enquiries as Pending')
    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='Pending')
        self.message_user(request, f'{updated} enquiry(ies) marked as Pending.')
