from django.contrib import admin
from .models import Contact, Client


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone']
    search_fields = ['name', 'email', 'phone']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_contact_name', 'get_email', 'get_phone']
    search_fields = ['name', 'contact__name', 'contact__email', 'contact__phone']

    def get_contact_name(self, obj):
        return obj.contact.name
    get_contact_name.short_description = 'Contact Name'
    get_contact_name.admin_order_field = 'contact__name'

    def get_email(self, obj):
        return obj.contact.email or '-'
    get_email.short_description = 'Email'

    def get_phone(self, obj):
        return obj.contact.phone or '-'
    get_phone.short_description = 'Phone'
