from django.core.management.base import BaseCommand
from django.db import transaction
from clients.models import Client, Contact


class Command(BaseCommand):
    help = 'Merge duplicate Client records (same company name) into one.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be merged without making any changes.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be saved.\n'))

        # Find all company names that have more than one Client row
        from django.db.models import Count
        duplicate_names = (
            Client.objects.values('name')
            .annotate(cnt=Count('id'))
            .filter(cnt__gt=1)
            .values_list('name', flat=True)
        )

        if not duplicate_names:
            self.stdout.write(self.style.SUCCESS('No duplicate clients found.'))
            return

        total_removed = 0

        for name in duplicate_names:
            clients = list(Client.objects.filter(name=name).order_by('id'))
            canonical = clients[0]
            duplicates = clients[1:]

            self.stdout.write(
                f'\nCompany: "{name}"  — keeping id={canonical.id}, '
                f'removing ids={[c.id for c in duplicates]}'
            )

            for dup in duplicates:
                # Re-point SalesEnquiry rows
                se_count = dup.sales_enquiries.count()
                if se_count:
                    self.stdout.write(f'  Reassigning {se_count} SalesEnquiry row(s) from client {dup.id} → {canonical.id}')
                    if not dry_run:
                        dup.sales_enquiries.update(client=canonical)

                # Re-point MonthlyAward rows
                ma_count = dup.monthly_awards.count()
                if ma_count:
                    self.stdout.write(f'  Reassigning {ma_count} MonthlyAward row(s) from client {dup.id} → {canonical.id}')
                    if not dry_run:
                        dup.monthly_awards.update(client=canonical)

                orphan_contact = dup.contact

                if not dry_run:
                    dup.delete()
                    # Delete the contact only if no other client still uses it
                    if not Client.objects.filter(contact=orphan_contact).exists():
                        orphan_contact.delete()
                        self.stdout.write(f'  Deleted orphaned contact id={orphan_contact.id} ("{orphan_contact.name}")')

                total_removed += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\nDry run complete — {total_removed} duplicate client(s) would be removed.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nDone — {total_removed} duplicate client(s) removed.'
            ))
