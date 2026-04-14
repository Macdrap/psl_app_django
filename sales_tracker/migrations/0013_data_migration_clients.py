from django.db import migrations


def migrate_client_data(apps, schema_editor):
    """
    Populate clients.Contact and clients.Client from existing char fields,
    then set client_ref FK on all SalesEnquiry and MonthlyAward rows.
    """
    Contact = apps.get_model('clients', 'Contact')
    Client = apps.get_model('clients', 'Client')
    SalesEnquiry = apps.get_model('sales_tracker', 'SalesEnquiry')
    MonthlyAward = apps.get_model('monthly_awards', 'MonthlyAward')

    # Cache: (company_name, contact_name, email, phone) -> Client instance
    client_cache = {}

    def get_or_create_client(company, contact_name, email, phone):
        # Normalise empty strings to None for nullable fields
        email = email.strip() if email else None
        phone = phone.strip() if phone else None
        company = company.strip() if company else ''
        contact_name = contact_name.strip() if contact_name else ''

        key = (company, contact_name, email or '', phone or '')
        if key in client_cache:
            return client_cache[key]

        # Find or create a matching Contact
        contact_qs = Contact.objects.filter(
            name=contact_name,
            email=email,
            phone=phone,
        )
        if contact_qs.exists():
            contact = contact_qs.first()
        else:
            contact = Contact.objects.create(
                name=contact_name,
                email=email,
                phone=phone,
            )

        # Find or create a matching Client
        client_qs = Client.objects.filter(name=company, contact=contact)
        if client_qs.exists():
            client = client_qs.first()
        else:
            client = Client.objects.create(name=company, contact=contact)

        client_cache[key] = client
        return client

    # Migrate SalesEnquiry records
    for enquiry in SalesEnquiry.objects.all():
        company = enquiry.client or ''
        contact_name = enquiry.client_contact or ''
        if not company and not contact_name:
            continue
        client = get_or_create_client(company, contact_name, enquiry.email, enquiry.phone)
        enquiry.client_ref = client
        enquiry.save(update_fields=['client_ref'])

    # Migrate MonthlyAward records
    for award in MonthlyAward.objects.all():
        company = award.client or ''
        contact_name = award.client_contact or ''
        if not company and not contact_name:
            continue
        client = get_or_create_client(company, contact_name, award.email, award.phone)
        award.client_ref = client
        award.save(update_fields=['client_ref'])


def reverse_migrate(apps, schema_editor):
    """Reverse: copy client data back to char fields from FK."""
    SalesEnquiry = apps.get_model('sales_tracker', 'SalesEnquiry')
    MonthlyAward = apps.get_model('monthly_awards', 'MonthlyAward')

    for enquiry in SalesEnquiry.objects.select_related('client_ref__contact').all():
        if enquiry.client_ref:
            enquiry.client = enquiry.client_ref.name
            enquiry.client_contact = enquiry.client_ref.contact.name
            enquiry.email = enquiry.client_ref.contact.email
            enquiry.phone = enquiry.client_ref.contact.phone
            enquiry.save(update_fields=['client', 'client_contact', 'email', 'phone'])

    for award in MonthlyAward.objects.select_related('client_ref__contact').all():
        if award.client_ref:
            award.client = award.client_ref.name
            award.client_contact = award.client_ref.contact.name
            award.email = award.client_ref.contact.email
            award.phone = award.client_ref.contact.phone
            award.save(update_fields=['client', 'client_contact', 'email', 'phone'])


class Migration(migrations.Migration):

    dependencies = [
        ('sales_tracker', '0012_salesenquiry_add_client_ref'),
        ('monthly_awards', '0004_monthlyaward_add_client_ref'),
    ]

    operations = [
        migrations.RunPython(migrate_client_data, reverse_code=reverse_migrate),
    ]
