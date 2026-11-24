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
        'utility_value': '100', 'mbs_value': '50', 'topo_value': '25', 'contractor_value': '25',
        'status': 'Pending', 'follow_up_status': 'n_a', 'followed_up_date': '',
    }
    data.update(overrides)
    return data


class InvoicedJobModelTests(LoggedInTestCase):
    def test_psl_value_is_everything_except_contractor(self):
        award = self.make_award(value='1000')
        inv = self.make_invoice(award, utility='300', mbs='200', topo='100', contractor='400')
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
        self.make_invoice(award, mbs='700', topo='300', status='Pending', invoice_date=may)
        self.make_invoice(award, utility='9999', invoice_date=date(2026, 6, 1))  # other month

        resp = self.client.get(reverse('invoiced_jobs_list'), {'year': 2026, 'month': 5})
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context
        self.assertEqual(ctx['jobs_count'], 2)
        self.assertEqual(ctx['total_invoiced'], Decimal('1500'))
        self.assertEqual(ctx['total_pending'], Decimal('1000'))
        self.assertEqual(ctx['total_value'], Decimal('2500'))
        self.assertEqual(ctx['total_psl_value'], Decimal('2000'))  # total - contractor
        by_code = ctx['department_total_by_code']
        self.assertEqual((by_code['utility']['total'], by_code['mbs']['total'], by_code['topo']['total'],
                          by_code['contractor']['total'], by_code['drone']['total']),
                         (Decimal('1000'), Decimal('700'), Decimal('300'), Decimal('500'), 0))
        self.assertEqual((by_code['utility']['count'], by_code['mbs']['count']), (1, 1))
        self.assertEqual([d['code'] for d in ctx['department_totals']][:4],
                         ['utility', 'mbs', 'topo', 'contractor'])

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


class DepartmentTests(LoggedInTestCase):
    """CAD -> MBS, five new departments, and invoices feeding survey types."""

    def test_new_departments_count_towards_psl_total_and_mismatch(self):
        award = self.make_award(value='1000')
        inv = self.make_invoice(award, mbs='100', contractor='300', watercourse_value=Decimal('100'),
                                cctv_drainage_value=Decimal('100'), modelling_3d_value=Decimal('100'),
                                drone_value=Decimal('100'), engineering_value=Decimal('200'))
        self.assertEqual(inv.get_total_invoice_value(), Decimal('1000'))
        self.assertEqual(inv.psl_value, Decimal('700'))
        self.assertFalse(award.has_value_mismatch())

    def test_invoice_value_adds_department_to_award_survey_types_only(self):
        sale = self.make_enquiry(status='Awarded', survey_types=['topo'])
        award = self.make_award(sale=sale, survey_types=['topo'])
        self.make_invoice(award, mbs='10', drone_value=Decimal('5'))
        award.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(award.survey_types, ['mbs', 'topo', 'drone'])
        self.assertEqual(sale.survey_types, ['topo'])  # the quote is left alone

    def test_zero_value_invoice_does_not_add_survey_types(self):
        award = self.make_award(survey_types=['utility'])
        self.make_invoice(award)
        award.refresh_from_db()
        self.assertEqual(award.survey_types, ['utility'])

    def test_invoice_form_has_all_departments_and_blank_means_zero(self):
        award = self.make_award(value='300')
        resp = self.client.get(reverse('add_invoiced_job'))
        for label in ('Utility', 'MBS', 'Topo', 'Contractor', 'Watercourse', 'CCTV Drainage',
                      '3D Modelling', 'Drone Survey', 'Engineering'):
            self.assertContains(resp, f'{label} Value (£)')
        self.assertNotContains(resp, 'CAD Value')
        data = invoice_payload(award, utility_value='', mbs_value='', topo_value='', contractor_value='',
                               engineering_value='300')
        self.client.post(reverse('add_invoiced_job'), data)
        inv = InvoicedJob.objects.get()
        self.assertEqual((inv.utility_value, inv.engineering_value), (Decimal('0'), Decimal('300')))

    def test_list_shows_survey_types_and_new_department_cards(self):
        award = self.make_award(survey_types=['watercourse'])
        self.make_invoice(award, watercourse_value=Decimal('250'), invoice_date=date(2026, 5, 2))
        resp = self.client.get(reverse('invoiced_jobs_list'), {'year': 2026, 'month': 5})
        self.assertContains(resp, '<th>Survey Type</th>', html=True)
        self.assertContains(resp, 'data-survey-type="watercourse"')
        self.assertContains(resp, 'title="Watercourse £250.00"')  # department split tooltip
        self.assertContains(resp, '<h3>Watercourse</h3>', html=True)
        self.assertContains(resp, '<h3>MBS</h3>', html=True)
        self.assertNotContains(resp, '<h3>Engineering</h3>', html=True)  # no value this month

    def test_migration_0011_backfills_survey_types_from_invoice_values(self):
        from django.apps import apps
        from monthly_awards.models import MonthlyAward
        from sales_tracker.models import SalesEnquiry
        migration = importlib.import_module('invoiced_jobs.migrations.0011_backfill_survey_types')
        sale = self.make_enquiry(job_number='1', status='Awarded')
        award = self.make_award(sale=sale)
        self.make_invoice(award, mbs='500')                  # was a CAD value before 0010
        self.make_invoice(award, topo='200')
        manual = self.make_award(job_number='2')
        self.make_invoice(manual, utility='100')
        never_awarded = self.make_enquiry(job_number='3')
        # Pretend the data predates survey types
        MonthlyAward.objects.filter(pk=award.pk).update(survey_types=[])
        MonthlyAward.objects.filter(pk=manual.pk).update(survey_types=['drone'])
        SalesEnquiry.objects.update(survey_types=[])

        migration.backfill(apps, None)
        migration.backfill(apps, None)  # re-runnable
        for obj in (award, manual, sale, never_awarded):
            obj.refresh_from_db()
        self.assertEqual(award.survey_types, ['mbs', 'topo'])
        self.assertEqual(sale.survey_types, ['mbs', 'topo'])
        self.assertEqual(manual.survey_types, ['utility', 'drone'])  # keeps what it had
        self.assertEqual(never_awarded.survey_types, [])

    def test_every_survey_type_has_an_invoice_field_and_a_distinct_colour(self):
        from sales_tracker.survey_types import SURVEY_TYPES
        model_fields = {f.name for f in InvoicedJob._meta.get_fields()}
        for code, _, field, _ in SURVEY_TYPES:
            self.assertIn(field, model_fields, code)
        colours = [c for _, _, _, c in SURVEY_TYPES]
        self.assertEqual(len(set(colours)), len(colours))
        self.assertNotIn('cad_value', model_fields)
