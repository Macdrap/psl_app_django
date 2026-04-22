"""
Management command to clean up contact data after the multi-contact migration.

Problems it fixes:
1. Duplicate contacts with the same (client, name) — keeps the first, redirects
   any SalesEnquiry / MonthlyAward rows that point to the duplicate.
2. Reports how many enquiries / awards have no client or no contact linked.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count


class Command(BaseCommand):
    help = 'Deduplicate contacts and report unlinked enquiries/awards.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report without making changes.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        from clients.models import Client, Contact
        from sales_tracker.models import SalesEnquiry
        from monthly_awards.models import MonthlyAward

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes.\n'))

        # ── 1. Deduplicate contacts ──────────────────────────────────────────
        dupes_found = 0
        for client in Client.objects.all():
            # Find contact names that appear more than once for this client
            dup_names = (
                Contact.objects
                .filter(client=client)
                .values('name')
                .annotate(cnt=Count('id'))
                .filter(cnt__gt=1)
                .values_list('name', flat=True)
            )
            for name in dup_names:
                contacts = list(
                    Contact.objects.filter(client=client, name=name).order_by('id')
                )
                canonical = contacts[0]
                duplicates = contacts[1:]
                self.stdout.write(
                    f'  Duplicate contact "{name}" for client "{client.name}" '
                    f'— keeping id={canonical.id}, removing {[c.id for c in duplicates]}'
                )
                for dup in duplicates:
                    se = SalesEnquiry.objects.filter(contact=dup)
                    ma = MonthlyAward.objects.filter(contact=dup)
                    if se.exists():
                        self.stdout.write(
                            f'    Reassigning {se.count()} SalesEnquiry rows to contact {canonical.id}'
                        )
                        if not dry_run:
                            se.update(contact=canonical)
                    if ma.exists():
                        self.stdout.write(
                            f'    Reassigning {ma.count()} MonthlyAward rows to contact {canonical.id}'
                        )
                        if not dry_run:
                            ma.update(contact=canonical)
                    if not dry_run:
                        dup.delete()
                    dupes_found += 1

        if dupes_found:
            action = 'Would remove' if dry_run else 'Removed'
            self.stdout.write(self.style.SUCCESS(
                f'{action} {dupes_found} duplicate contact(s).'
            ))
        else:
            self.stdout.write('No duplicate contacts found.')

        # ── 2. Enquiries with no client ──────────────────────────────────────
        no_client = SalesEnquiry.objects.filter(client__isnull=True).count()
        no_contact = SalesEnquiry.objects.filter(contact__isnull=True).count()
        self.stdout.write(f'\nSalesEnquiry: {no_client} with no client, {no_contact} with no contact.')

        # ── 3. Awards with no client ─────────────────────────────────────────
        no_client_a = MonthlyAward.objects.filter(client__isnull=True).count()
        no_contact_a = MonthlyAward.objects.filter(contact__isnull=True).count()
        self.stdout.write(f'MonthlyAward: {no_client_a} with no client, {no_contact_a} with no contact.')

        # ── 4. Enquiries that have a client but no contact — try to auto-fix ─
        orphaned_se = SalesEnquiry.objects.filter(
            client__isnull=False, contact__isnull=True
        )
        if orphaned_se.exists():
            self.stdout.write(
                f'\n{orphaned_se.count()} SalesEnquiry rows have a client but no contact. '
                'Attempting to link to the client\'s first contact…'
            )
            fixed = 0
            for enquiry in orphaned_se:
                first_contact = enquiry.client.contacts.first()
                if first_contact:
                    if not dry_run:
                        enquiry.contact = first_contact
                        enquiry.save(update_fields=['contact'])
                    fixed += 1
            action = 'Would fix' if dry_run else 'Fixed'
            self.stdout.write(self.style.SUCCESS(f'  {action} {fixed} SalesEnquiry row(s).'))

        orphaned_ma = MonthlyAward.objects.filter(
            client__isnull=False, contact__isnull=True
        )
        if orphaned_ma.exists():
            self.stdout.write(
                f'\n{orphaned_ma.count()} MonthlyAward rows have a client but no contact. '
                'Attempting to link…'
            )
            fixed = 0
            for award in orphaned_ma:
                first_contact = award.client.contacts.first()
                if first_contact:
                    if not dry_run:
                        award.contact = first_contact
                        award.save(update_fields=['contact'])
                    fixed += 1
            action = 'Would fix' if dry_run else 'Fixed'
            self.stdout.write(self.style.SUCCESS(f'  {action} {fixed} MonthlyAward row(s).'))

        self.stdout.write(self.style.SUCCESS('\nDone.'))
