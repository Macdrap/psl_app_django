"""Promote `new` clients that already have more than one enquiry to `current`.

Referral sources are NOT touched: they are stored per enquiry and existing
values stay exactly as they are. (An earlier draft of this migration copied
each client's referral onto all its enquiries; that was removed before
release so production referral data is left unchanged.)

Safe on a fresh DB (no rows → no-op) and re-runnable. The reverse is a no-op
so the migration can still be unapplied.
"""
from django.db import migrations
from django.db.models import Count


def sync_existing(apps, schema_editor):
    Client = apps.get_model('clients', 'Client')

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
