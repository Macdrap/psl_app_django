"""Regression tests for Invoiced Jobs: PSL value, mismatch checks and monthly totals."""
import importlib
from datetime import date
from decimal import Decimal

from django.urls import reverse

from invoiced_jobs.models import InvoicedJob
from psl_app_project.test_utils import LoggedInTestCase


def invoice_payload(award, **overrides):
    data = {
        'award': award.pk, 'description': '', 'date': '2026-05-20',
        'utility_value': '100', 'cad_value': '50', 'topo_value': '25', 'contractor_value': '25',
        'status': 'Pending', 'follow_up_status': 'n_a', 'followed_up_date': '',
    }
    data.update(overrides)
    return data


class InvoicedJobModelTests(LoggedInTestCase):
    def test_psl_value_is_utility_plus_cad_plus_topo(self):
        award = self.make_award(value='1000')
        inv = self.make_invoice(award, utility='300', cad='200', topo='100', contractor='400')
        self.assertEqual(inv.psl_value, Decimal('600'))
        self.assertEqual(inv.get_total_invoice_value(), Decimal('1000'))

    def test_follow_up_status_defaults_to_valid_choice(self):
        inv = self.make_invoice(self.make_award())
        self.assertEqual(inv.follow_up_status, 'n_a')
        self.assertEqual(inv.get_follow_up_status_display(), 'N/A')

    def test_migration_0009_converts_old_na_values(self):
        from django.apps import apps
        migration = importlib.import_module('invoiced_jobs.migrations.0009_fix_follow_up_status_default')
        award = self.make_award()
        bad = self.make_invoice(award, follow_up_status='N/A')
        good = self.make_invoice(award, follow_up_status='to_follow')
        migration.fix_invalid_follow_up_status(apps, None)
        bad.refresh_from_db()
        good.refresh_from_db()
        self.assertEqual((bad.follow_up_status, good.follow_up_status), ('n_a', 'to_follow'))

    def test_mismatch_compares_sum_of_all_invoices_to_award_value(self):
        award = self.make_award(value='1000')
        self.make_invoice(award, utility='600')
        self.assertTrue(award.has_value_mismatch())
        self.make_invoice(award, contractor='400')  # multiple invoices per award are allowed
        self.assertFalse(award.has_value_mismatch())
        self.assertEqual(award.get_total_invoiced(), Decimal('1000'))


class InvoicedJobListTests(LoggedInTestCase):
    def test_monthly_totals(self):
        award = self.make_award(value='3000')
        may = date(2026, 5, 10)
        self.make_invoice(award, utility='1000', contractor='500', status='Invoiced', invoice_date=may)
        self.make_invoice(award, cad='700', topo='300', status='Pending', invoice_date=may)
        self.make_invoice(award, utility='9999', invoice_date=date(2026, 6, 1))  # other month

        resp = self.client.get(reverse('invoiced_jobs_list'), {'year': 2026, 'month': 5})
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        self.assertEqual(ctx['jobs_count'], 2)
        self.assertEqual(ctx['total_invoiced'], Decimal('1500'))
        self.assertEqual(ctx['total_pending'], Decimal('1000'))
        self.assertEqual(ctx['total_value'], Decimal('2500'))
        self.assertEqual(ctx['total_psl_value'], Decimal('2000'))  # total - contractor
        self.assertEqual((ctx['total_utils'], ctx['total_cad'], ctx['total_topo']),
                         (Decimal('1000'), Decimal('700'), Decimal('300')))

    def test_search_by_contact_name(self):
        client = self.make_client('Acme Ltd')
        contact = self.make_contact(client, 'Zed Smith')
        award = self.make_award(client=client, contact=contact)
        self.make_invoice(award)
        self.make_invoice(self.make_award(client=self.make_client('Other')))
        today = date.today()
        resp = self.client.get(reverse('invoiced_jobs_list'),
                               {'year': today.year, 'month': today.month, 'search': 'Zed'})
        self.assertEqual(resp.context['jobs_count'], 1)


class InvoicedJobCrudTests(LoggedInTestCase):
    def test_add_invoice_to_award_forces_award_and_returns_to_awards(self):
        award = self.make_award()
        other = self.make_award(job_number='other')
        resp = self.client.post(reverse('add_invoice_to_award', args=[award.pk]) + '?year=2026&month=5',
                                invoice_payload(other))
        self.assertIn(reverse('monthly_awards_list'), resp['Location'])
        self.assertEqual(InvoicedJob.objects.get().award, award)

    def test_edit_invoice_keeps_scroll_position(self):
        award = self.make_award()
        inv = self.make_invoice(award)
        resp = self.client.post(reverse('edit_invoiced_job', args=[inv.pk]),
                                invoice_payload(award, status='Invoiced', scroll='640'))
        self.assertIn('scroll=640', resp['Location'])
        inv.refresh_from_db()
        self.assertEqual(inv.status, 'Invoiced')
        self.assertEqual(inv.psl_value, Decimal('175'))

    def test_edit_page_renders(self):
        inv = self.make_invoice(self.make_award(location='12 High St'))
        resp = self.client.get(reverse('edit_invoiced_job', args=[inv.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '12 High St')

    def test_deleting_last_invoice_warns(self):
        award = self.make_award()
        inv = self.make_invoice(award)
        resp = self.client.post(reverse('delete_invoiced_job', args=[inv.pk]))
        self.assertTrue(any('no invoices' in m for m in self.messages_of(resp)))
        self.assertTrue(type(award).objects.filter(pk=award.pk).exists())
