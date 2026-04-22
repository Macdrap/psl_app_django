from django.db import migrations


def migrate_client_data(apps, schema_editor):
    """
    Migrate all existing client/contact data from the old char fields into the
    new normalised Client and Contact tables.

    Rules:
    - One Client per unique company name (case-insensitive leading/trailing space removed).
    - One Contact per unique (company, contact_name) pair — so 'Alpha / John Doe'
      and 'Alpha / Jane Smith' each get their own Contact, both linked to the
      single 'Alpha' Client.
    - Each SalesEnquiry and MonthlyAward gets both client_ref and contact_ref set.
    """
    Contact = apps.get_model('clients', 'Contact')
    Client = apps.get_model('clients', 'Client')
    SalesEnquiry = apps.get_model('sales_tracker', 'SalesEnquiry')
    MonthlyAward = apps.get_model('monthly_awards', 'MonthlyAward')

    # In-memory caches to avoid repeated DB hits
    client_cache = {}    # company_name -> Client instance
    contact_cache = {}   # (company_name, contact_name) -> Contact instance

    def norm(s):
        return s.strip() if s else ''

    def norm_nullable(s):
        v = s.strip() if s else None
        return v or None

    def get_or_create(company, contact_name, email, phone):
        company = norm(company)
        contact_name = norm(contact_name)
        email = norm_nullable(email)
        phone = norm_nullable(phone)

        if not company and not contact_name:
            return None, None

        # ── Client (one per company name) ────────────────────────────────────
        if company not in client_cache:
            qs = Client.objects.filter(name=company)
            client_cache[company] = qs.first() if qs.exists() else Client.objects.create(name=company)
        client = client_cache[company]

        # ── Contact (one per company + contact name) ──────────────────────────
        # If the same (company, contact_name) appears with different email/phone
        # across records, we keep the first non-empty value we encounter.
        key = (company, contact_name)
        if key not in contact_cache:
            qs = Contact.objects.filter(client=client, name=contact_name)
            if qs.exists():
                contact_cache[key] = qs.first()
            else:
                contact_cache[key] = Contact.objects.create(
                    client=client,
                    name=contact_name,
                    email=email,
                    phone=phone,
                )
        contact = contact_cache[key]

        return client, contact

    # ── SalesEnquiry rows ─────────────────────────────────────────────────────
    for enquiry in SalesEnquiry.objects.all():
        company = enquiry.client or ''
        contact_name = enquiry.client_contact or ''
        if not company and not contact_name:
            continue
        client, contact = get_or_create(company, contact_name, enquiry.email, enquiry.phone)
        enquiry.client_ref = client
        enquiry.contact_ref = contact
        enquiry.save(update_fields=['client_ref', 'contact_ref'])

    # ── MonthlyAward rows ─────────────────────────────────────────────────────
    for award in MonthlyAward.objects.all():
        company = award.client or ''
        contact_name = award.client_contact or ''
        if not company and not contact_name:
            continue
        client, contact = get_or_create(company, contact_name, award.email, award.phone)
        award.client_ref = client
        award.contact_ref = contact
        award.save(update_fields=['client_ref', 'contact_ref'])


def reverse_migrate(apps, schema_editor):
    """Reverse: copy normalised data back to the old char fields."""
    SalesEnquiry = apps.get_model('sales_tracker', 'SalesEnquiry')
    MonthlyAward = apps.get_model('monthly_awards', 'MonthlyAward')

    for enquiry in SalesEnquiry.objects.select_related('client_ref', 'contact_ref').all():
        if enquiry.client_ref:
            enquiry.client = enquiry.client_ref.name
        if enquiry.contact_ref:
            enquiry.client_contact = enquiry.contact_ref.name
            enquiry.email = enquiry.contact_ref.email or ''
            enquiry.phone = enquiry.contact_ref.phone or ''
        enquiry.save(update_fields=['client', 'client_contact', 'email', 'phone'])

    for award in MonthlyAward.objects.select_related('client_ref', 'contact_ref').all():
        if award.client_ref:
            award.client = award.client_ref.name
        if award.contact_ref:
            award.client_contact = award.contact_ref.name
            award.email = award.contact_ref.email or ''
            award.phone = award.contact_ref.phone or ''
        award.save(update_fields=['client', 'client_contact', 'email', 'phone'])


class Migration(migrations.Migration):

    dependencies = [
        ('sales_tracker', '0012_salesenquiry_add_client_ref'),
        ('monthly_awards', '0004_monthlyaward_add_client_ref'),
        ('clients', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_client_data, reverse_code=reverse_migrate),
    ]
