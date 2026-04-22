from django.contrib import admin
from .models import Contact, Client


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 1
    fields = ['name', 'email', 'phone']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_contact_count']
    search_fields = ['name', 'contacts__name', 'contacts__email', 'contacts__phone']
    inlines = [ContactInline]

    def get_contact_count(self, obj):
        return obj.contacts.count()
    get_contact_count.short_description = 'Contacts'


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'client', 'email', 'phone']
    search_fields = ['name', 'email', 'phone', 'client__name']
    list_select_related = ['client']
