"""Regression tests for Monthly Awards and their sync back to Sales Enquiries."""
from datetime import date
from decimal import Decimal

from django.urls import reverse

from invoiced_jobs.models import InvoicedJob
from monthly_awards.models import MonthlyAward
from psl_app_project.test_utils import LoggedInTestCase


def award_payload(**overrides):
    data = {
        'job_number': '8000', 'date': '2026-05-10', 'location': 'Leeds', 'value': '1200',
        'company_name': 'Acme Ltd', 'contact_name': 'John Doe', 'email': '', 'phone': '',
        'sector': '', 'client_status': '',
    }
    data.update(overrides)
    return data


class MonthlyAwardListTests(LoggedInTestCase):
    def test_list_filters_by_month_and_flags_problems(self):
        no_invoice = self.make_award(job_number='1', award_date=date(2026, 5, 3))
        mismatch = self.make_award(job_number='2', value='1000', award_date=date(2026, 5, 4))
        self.make_invoice(mismatch, utility='400')
        matched = self.make_award(job_number='3', value='1000', award_date=date(2026, 5, 5))
        self.make_invoice(matched, utility='600', contractor='400')
        self.make_award(job_number='other-month', award_date=date(2026, 6, 1))

        resp = self.client.get(reverse('monthly_awards_list'), {'year': 2026, 'month': 5})
        self.assertEqual(resp.status_code, 200)
        rows = {a.job_number: a for a in resp.context['awards']}
        self.assertEqual(set(rows), {'1', '2', '3'})
        self.assertTrue(rows['1'].is_missing_invoice)
        self.assertTrue(rows['2'].has_mismatch)
        self.assertFalse(rows['3'].has_mismatch)
        self.assertEqual(resp.context['total_value'], Decimal('3000'))

    def test_bad_year_month_falls_back_to_current(self):
        resp = self.client.get(reverse('monthly_awards_list'), {'year': 'x', 'month': 'y'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['selected_year'], date.today().year)


class MonthlyAwardCrudTests(LoggedInTestCase):
    def test_manual_award_creates_client_but_no_invoice(self):
        resp = self.client.post(reverse('add_monthly_award'), award_payload())
        self.assertEqual(resp.status_code, 302)
        award = MonthlyAward.objects.get(job_number='8000')
        self.assertIsNone(award.sale)
        self.assertEqual(award.client.name, 'Acme Ltd')
        self.assertFalse(InvoicedJob.objects.exists())

    def test_editing_award_syncs_back_to_sale(self):
        sale = self.make_enquiry(job_number='8000', value='1200', status='Awarded')
        award = self.make_award(sale=sale, job_number='8000', value='1200')
        self.client.post(reverse('edit_monthly_award', args=[award.pk]),
                         award_payload(job_number='8000.1', value='1300', location='Hull',
                                       company_name='Bravo Ltd'))
        sale.refresh_from_db()
        self.assertEqual((sale.job_number, sale.value, sale.location, sale.client.name),
                         ('8000.1', Decimal('1300'), 'Hull', 'Bravo Ltd'))
        self.assertEqual(sale.status, 'Awarded')

    def test_deleting_award_reverts_sale_and_cascades_invoices(self):
        sale = self.make_enquiry(status='Awarded')
        award = self.make_award(sale=sale)
        self.make_invoice(award, utility='10')
        resp = self.client.post(reverse('delete_monthly_award', args=[award.pk]))
        self.assertEqual(resp.status_code, 302)
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'Pending')
        self.assertFalse(MonthlyAward.objects.exists())
        self.assertFalse(InvoicedJob.objects.exists())
