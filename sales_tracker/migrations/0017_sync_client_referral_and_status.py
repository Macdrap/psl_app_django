"""Make existing data follow the client-level rules (see sales_tracker/client_sync.py):

1. Every enquiry of a client gets the client's referral source. Where a client's
   enquiries disagree, the earliest enquiry's referral wins.
2. A client marked `new` with more than one enquiry becomes `current`.

Safe on a fresh DB (no rows → no-op) and re-runnable. Not reversible in data
terms; the reverse is a no-op so the migration can still be unapplied.
"""
from django.db import migrations
from django.db.models import Count


def sync_existing(apps, schema_editor):
    SalesEnquiry = apps.get_model('sales_tracker', 'SalesEnquiry')
    Client = apps.get_model('clients', 'Client')

    first_referral = {}
    rows = (SalesEnquiry.objects
            .exclude(client__isnull=True)
            .exclude(referral__isnull=True).exclude(referral='')
            .order_by('date', 'created_at', 'pk')
            .values_list('client_id', 'referral'))
    for client_id, referral in rows:
        first_referral.setdefault(client_id, referral)

    for client_id, referral in first_referral.items():
        SalesEnquiry.objects.filter(client_id=client_id).update(referral=referral)

    promote_ids = list(
        Client.objects
        .filter(client_status='new')
        .annotate(n=Count('sales_enquiries'))
        .filter(n__gt=1)
        .values_list('pk', flat=True)
    )
    Client.objects.filter(pk__in=promote_ids).update(client_status='current')


class Migration(migrations.Migration):

    dependencies = [
        ('sales_tracker', '0016_salesenquiry_referral'),
        ('clients', '0006_add_flood_consultancy_sector'),
    ]

    operations = [
        migrations.RunPython(sync_existing, migrations.RunPython.noop),
    ]
