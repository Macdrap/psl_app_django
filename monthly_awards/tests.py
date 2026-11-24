"""Regression tests for Monthly Awards and their sync back to Sales Enquiries."""
from datetime import date
from decimal import Decimal

from django.urls import reverse

from invoiced_jobs.models import InvoicedJob
from monthly_awards.models import MonthlyAward
from psl_app_project.test_utils import LoggedInTestCase


def award_payload(**overrides):
    """A valid award form POST. Unless the test passes its own value_<code>
    fields, the whole `value` goes to the first survey type (Topo by default)."""
    data = {
        'job_number': '8000', 'date': '2026-05-10', 'location': 'Leeds', 'value': '1200',
        'company_name': 'Acme Ltd', 'contact_name': 'John Doe', 'email': '', 'phone': '',
        'sector': '', 'client_status': '', 'survey_types': ['topo'],
    }
    data.update(overrides)
    if data['survey_types'] and not any(k.startswith('value_') for k in overrides):
        data[f"value_{data['survey_types'][0]}"] = data['value']
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

    def test_editing_award_syncs_job_details_but_not_value_back_to_sale(self):
        sale = self.make_enquiry(job_number='8000', value='1200', status='Awarded')
        award = self.make_award(sale=sale, job_number='8000', value='1200')
        self.client.post(reverse('edit_monthly_award', args=[award.pk]),
                         award_payload(job_number='8000.1', value='1300', location='Hull',
                                       company_name='Bravo Ltd'))
        sale.refresh_from_db()
        award.refresh_from_db()
        self.assertEqual((sale.job_number, sale.location, sale.client.name), ('8000.1', 'Hull', 'Bravo Ltd'))
        self.assertEqual(sale.value, Decimal('1200'))   # the quote
        self.assertEqual(award.value, Decimal('1300'))  # what was awarded
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


class MonthlyAwardSurveyTypeTests(LoggedInTestCase):
    def test_manual_award_saves_survey_types(self):
        self.client.post(reverse('add_monthly_award'), award_payload(survey_types=['engineering', 'topo']))
        self.assertEqual(MonthlyAward.objects.get(job_number='8000').survey_types, ['topo', 'engineering'])

    def test_editing_award_survey_types_leaves_the_sale_alone(self):
        sale = self.make_enquiry(job_number='8000', value='1200', status='Awarded', survey_types=['utility'])
        award = self.make_award(sale=sale, job_number='8000', value='1200', survey_types=['utility'])
        self.client.post(reverse('edit_monthly_award', args=[award.pk]),
                         award_payload(survey_types=['utility', 'modelling_3d']))
        sale.refresh_from_db()
        award.refresh_from_db()
        self.assertEqual(sale.survey_types, ['utility'])
        self.assertEqual(award.survey_types, ['utility', 'modelling_3d'])

    def test_list_shows_survey_type_column(self):
        self.make_award(job_number='8001', award_date=date(2026, 5, 3), survey_types=['drone'])
        resp = self.client.get(reverse('monthly_awards_list'), {'year': 2026, 'month': 5})
        self.assertContains(resp, '<th>Survey Type</th>', html=True)
        self.assertContains(resp, 'Drone Survey')

    def test_edit_form_shows_current_survey_types_ticked(self):
        award = self.make_award(survey_types=['mbs'])
        resp = self.client.get(reverse('edit_monthly_award', args=[award.pk]))
        self.assertEqual(resp.context['award_form']['survey_types'].value(), ['mbs'])


class MonthlyAwardValueBySurveyTypeTests(LoggedInTestCase):
    """Awards are allocated by survey type too, and stay identical to their sale."""

    def edit(self, award, **overrides):
        resp = self.client.post(reverse('edit_monthly_award', args=[award.pk]), award_payload(**overrides))
        self.assertEqual(resp.status_code, 302, getattr(resp, 'context', None) and resp.context['award_form'].errors)
        award.refresh_from_db()
        return award

    def test_new_award_total_is_the_sum_of_its_survey_type_values(self):
        self.client.post(reverse('add_monthly_award'), award_payload(
            survey_types=['mbs', 'drone'], value='1', value_mbs='700', value_drone='300.50'))
        award = MonthlyAward.objects.get(job_number='8000')
        self.assertEqual(award.value, Decimal('1000.50'))
        self.assertEqual(award.get_survey_type_values(), {'mbs': Decimal('700'), 'drone': Decimal('300.50')})

    def test_new_award_needs_a_survey_type(self):
        resp = self.client.post(reverse('add_monthly_award'), award_payload(survey_types=[]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('survey_types', resp.context['award_form'].errors)
        self.assertFalse(MonthlyAward.objects.exists())

    def test_old_unsplit_award_can_still_be_edited_with_a_typed_total(self):
        award = self.make_award(value='500')
        award = self.edit(award, survey_types=[], value='650')
        self.assertEqual((award.value, award.survey_type_values), (Decimal('650'), {}))

    def test_awarded_value_can_differ_from_the_quote(self):
        split = {'topo': '1200.00'}
        sale = self.make_enquiry(job_number='8000', value='1200', status='Awarded', survey_types=['topo'],
                                 survey_type_values=split)
        award = self.make_award(sale=sale, job_number='8000', value='1200', survey_types=['topo'],
                                survey_type_values=split)
        award = self.edit(award, survey_types=['topo', 'engineering'], value_topo='800', value_engineering='150')
        self.assertEqual((award.value, award.survey_type_values),
                         (Decimal('950'), {'topo': '800.00', 'engineering': '150.00'}))
        sale.refresh_from_db()
        self.assertEqual((sale.value, sale.survey_types, sale.survey_type_values),
                         (Decimal('1200'), ['topo'], split))

    def test_linked_award_form_shows_the_quote(self):
        sale = self.make_enquiry(value='1200', status='Awarded', survey_types=['topo'],
                                 survey_type_values={'topo': '1200.00'})
        award = self.make_award(sale=sale, value='900', survey_types=['topo'], survey_type_values={'topo': '900.00'})
        resp = self.client.get(reverse('edit_monthly_award', args=[award.pk]))
        self.assertContains(resp, 'Quoted on the enquiry: <strong>£1,200.00</strong> (Topo £1,200.00)', html=False)

    def test_changed_split_updates_a_single_invoice(self):
        award = self.make_award(value='1200', survey_types=['topo'], survey_type_values={'topo': '1200.00'})
        invoice = self.make_invoice(award, topo='1200')
        self.edit(award, survey_types=['topo', 'mbs'], value_topo='800', value_mbs='400')
        invoice.refresh_from_db()
        self.assertEqual((invoice.topo_value, invoice.mbs_value), (Decimal('800'), Decimal('400')))
        self.assertFalse(award.has_value_mismatch())

    def test_staged_invoices_are_left_alone(self):
        award = self.make_award(value='1200', survey_types=['topo'], survey_type_values={'topo': '1200.00'})
        first = self.make_invoice(award, topo='600')
        second = self.make_invoice(award, topo='600')
        self.edit(award, survey_types=['topo'], value_topo='1500')
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.topo_value, second.topo_value), (Decimal('600'), Decimal('600')))
        self.assertTrue(award.has_value_mismatch())  # flagged, as before

    def test_award_form_shows_value_inputs_with_the_split(self):
        award = self.make_award(value='900', survey_types=['utility', 'drone'],
                                survey_type_values={'utility': '600.00', 'drone': '300.00'})
        resp = self.client.get(reverse('edit_monthly_award', args=[award.pk]))
        form = resp.context['award_form']
        self.assertEqual((form['value_utility'].value(), form['value_drone'].value()),
                         (Decimal('600.00'), Decimal('300.00')))
        self.assertContains(resp, 'Value by Survey Type')
        self.assertContains(resp, 'Total Award Value')

    def test_migration_0009_copies_sale_split_and_splits_manual_awards(self):
        import importlib
        from django.apps import apps
        migration = importlib.import_module('monthly_awards.migrations.0009_backfill_survey_type_values')
        sale = self.make_enquiry(job_number='1', value='1000', status='Awarded', survey_types=['mbs', 'topo'],
                                 survey_type_values={'mbs': '600.00', 'topo': '400.00'})
        linked = self.make_award(sale=sale, value='1000', survey_types=['mbs', 'topo'])
        single = self.make_award(job_number='2', value='300', survey_types=['drone'])
        multi = self.make_award(job_number='3', value='500', survey_types=['utility', 'topo'])
        self.make_invoice(multi, utility='200')
        self.make_invoice(multi, topo='300')
        unknown = self.make_award(job_number='4', value='800', survey_types=['utility', 'topo'])
        MonthlyAward.objects.update(survey_type_values={})

        migration.backfill(apps, None)
        migration.backfill(apps, None)  # re-runnable
        for a in (linked, single, multi, unknown):
            a.refresh_from_db()
        self.assertEqual(linked.survey_type_values, {'mbs': '600.00', 'topo': '400.00'})
        self.assertEqual(single.survey_type_values, {'drone': '300.00'})
        self.assertEqual(multi.survey_type_values, {'utility': '200.00', 'topo': '300.00'})
        self.assertEqual(unknown.survey_type_values, {})
