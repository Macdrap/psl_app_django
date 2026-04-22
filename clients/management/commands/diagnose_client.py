"""
Usage:
    python manage.py diagnose_client "Simpson TWS"

Shows every Client record whose name contains the search term (case-insensitive),
plus how many enquiries and awards are linked to each, and how many awards/enquiries
have client=NULL in total.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Diagnose client record variants and NULL links for a name fragment.'

    def add_arguments(self, parser):
        parser.add_argument('name', help='Company name fragment to search for')

    def handle(self, *args, **options):
        from clients.models import Client
        from sales_tracker.models import SalesEnquiry
        from monthly_awards.models import MonthlyAward

        term = options['name']

        # ── Matching client records ───────────────────────────────────────────
        matches = Client.objects.filter(name__icontains=term).order_by('name')
        self.stdout.write(f'\nClient records matching "{term}":')
        self.stdout.write('─' * 60)
        if not matches:
            self.stdout.write('  (none found)')
        for client in matches:
            eq = SalesEnquiry.objects.filter(client=client).count()
            aw = MonthlyAward.objects.filter(client=client).count()
            ct = client.contacts.count()
            self.stdout.write(
                f'  id={client.pk:>5}  name="{client.name}"'
                f'  contacts={ct}  enquiries={eq}  awards={aw}'
            )

        # ── NULL-client rows ──────────────────────────────────────────────────
        null_eq = SalesEnquiry.objects.filter(client__isnull=True).count()
        null_aw = MonthlyAward.objects.filter(client__isnull=True).count()
        self.stdout.write(f'\nRows with client=NULL:')
        self.stdout.write(f'  SalesEnquiry: {null_eq}')
        self.stdout.write(f'  MonthlyAward: {null_aw}')

        # ── Awards whose enquiry client differs from the award client ─────────
        mismatch = MonthlyAward.objects.filter(
            sale__isnull=False,
            sale__client__isnull=False,
        ).exclude(client=None).exclude(client=__import__('django.db.models', fromlist=['F']).F('sale__client')).count()
        self.stdout.write(f'\nAwards where award.client != award.sale.client: {mismatch}')
        self.stdout.write('')
